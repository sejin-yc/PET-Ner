from __future__ import annotations

import struct
from typing import Any, Dict

# ---------- UART ID (SBC↔STM) ----------
# SBC -> STM32
ID_CMD_VEL   = 0x01   # 이동: float32×3 (vx, vy, wz)
ID_HEARTBEAT = 0x02   # heartbeat: payload 없음, STM N초 미수신 시 워치독 정지
ID_FEED      = 0x05   # 급식: uint8 (level: 1~3) - 사용자가 웹 UI에서 직접 급식 (서보모터로 개폐통 열어서 급식)
ID_ARM_START = 0x06   # 로봇팔 동작 시작: uint8 (action_id: 0=정지, 1=변 치우기, 2+=기타) - 젯슨의 모방학습 로봇팔이 제어
ID_ARM_POSITION_CORRECT = 0x07  # 로봇 위치 보정: float32×3 (dx, dy, dz) - 바퀴 이동만 (STM32가 로봇팔 제어 안 함)
ID_CHURU     = 0x08   # 츄르 주기: uint8 (enable: 0=정지, 1=츄르 주기) - 사용자가 웹 UI에서 직접 츄르 주기 (주사기 밀기)
ID_ARM_WATER = 0x09   # 급수: uint8 (action: 0=위치 이동/정지, 1=물그릇 집기, 2=물 버리기, 3=물 받기, 4=물그릇 두기) - 젯슨의 모방학습 로봇팔이 제어
ID_ESTOP     = 0x10   # 비상정지: uint8 (0/1)
# STM32 -> SBC
ID_BATTERY   = 0x81   # 전압(uint16 mV), 잔량(uint8 %), 충전중(uint8), 에러(uint8)
ID_ENCODER   = 0x82   # enc_fl,enc_fr,enc_rl,enc_rr (각 int32, 16B) — 앞좌/앞우/뒤좌/뒤우 메카넘 4륜 누적 틱
ID_IMU       = 0x83   # yaw,pitch,roll(rad) + 가속도 x,y,z, float32×6
ID_STATUS    = 0x84   # 상태/작업 완료: uint8 status_type, uint8 status_code, uint8 flags (3B)

class UartId:
    BATTERY = 0x81
    ENCODER = 0x82
    IMU     = 0x83
    STATUS  = 0x84

# STATUS 타입 (status_type)
STATUS_TYPE_JOB_COMPLETE = 0x01   # 작업 완료
STATUS_TYPE_JOB_FAILED   = 0x02   # 작업 실패
STATUS_TYPE_ERROR         = 0x03   # 에러 발생
STATUS_TYPE_STATE         = 0x04   # 상태 변경

# 작업 완료 코드 (status_code, status_type=0x01)
# 주의: STM32가 직접 제어하는 작업만 STATUS로 보냄 (급식, 츄르)
# 변 치우기/급수는 젯슨이 제어하므로 젯슨이 arm/job_complete로 완료 신호 보냄
JOB_FEED_COMPLETE         = 0x01   # 급식 완료 (STM32가 서보 제어)
JOB_CHURU_COMPLETE        = 0x02   # 츄르 주기 완료 (STM32가 서보 제어)

# 작업 실패 코드 (status_code, status_type=0x02)
JOB_FEED_FAILED           = 0x01   # 급식 실패 (STM32가 감지)
JOB_CHURU_FAILED          = 0x02   # 츄르 주기 실패 (STM32가 감지)

# 에러 코드 (status_code, status_type=0x03)
ERROR_MOTOR_FAULT         = 0x01   # 모터 오류
ERROR_SENSOR_FAULT        = 0x02   # 센서 오류
ERROR_COMM_TIMEOUT        = 0x03   # 통신 타임아웃
ERROR_OVERLOAD            = 0x04   # 과부하

# 상태 플래그 (flags, bitmask)
FLAG_ARM_ACTIVE           = 0x01   # 로봇팔 동작 중
FLAG_WHEELS_LOCKED        = 0x02   # 바퀴 잠금
FLAG_EMERGENCY_STOP       = 0x04   # 비상정지 활성화

# ---------- 프레임 만들기/파싱 ----------
STX1 = 0xAA
STX2 = 0x55

def xor_checksum(msg_id: int, length: int, payload: bytes) -> int:
    chk = (msg_id & 0xFF) ^ (length & 0xFF)
    for b in payload:
        chk ^= b
    return chk & 0xFF

def make_frame(msg_id: int, payload: bytes) -> bytes:
    length = len(payload) & 0xFF
    chk = xor_checksum(msg_id, length, payload)
    return bytes([STX1, STX2, msg_id & 0xFF, length]) + payload + bytes([chk])

# ---------- SBC -> STM32 ----------

def make_cmd_vel_frame(vx: float, vy: float, wz: float) -> bytes:
    payload = struct.pack("<fff", float(vx), float(vy), float(wz))  # 12B
    return make_frame(0x01, payload)

def make_heartbeat_frame() -> bytes:
    """payload 없음. STM이 N초간 미수신 시 워치독으로 정지 등."""
    return make_frame(ID_HEARTBEAT, b"")

def make_feed_frame(level: int) -> bytes:
    """
    급식 프레임 생성.
    
    Args:
        level: 급식 레벨 (1~3) - 서보모터로 개폐통 열어서 급식
    
    Returns:
        UART 프레임 바이트
    
    Note:
        - STM32가 서보모터로 개폐통을 열어서 급식
        - level에 따라 개폐 시간이 조절될 수 있음 (STM32 구현에 따라)
    """
    level = max(1, min(3, level))  # 1~3 범위로 제한
    payload = bytes([level & 0xFF])  # 1B
    return make_frame(ID_FEED, payload)

def make_estop_frame(value: int) -> bytes:
    payload = bytes([1 if value else 0])  # 1B
    return make_frame(0x10, payload)

# ---------- 로봇팔 제어 (SBC -> STM32) ----------

def make_arm_start_frame(action_id: int) -> bytes:
    """
    로봇팔 동작 시작/정지 프레임 생성.
    
    Args:
        action_id: 
            - 0 = 로봇팔 정지 (변 치우기 완료 또는 중지)
            - 1 = 변 치우기 시작 (젯슨의 모방학습 로봇팔이 자율로 4구역 처리)
            - 2+ = 기타 로봇팔 동작 시작
    
    Returns:
        UART 프레임 바이트
    
    Note:
        - action_id = 1: 변 치우기 시작 → STM32가 바퀴 모터를 잠금 (로봇팔이 변 치우는 동안 바퀴 움직임 방지)
        - action_id = 0: 변 치우기 완료/정지 → STM32가 바퀴 모터를 해제 (이동 가능)
        - STM32는 로봇팔을 직접 제어하지 않음 (젯슨이 모방학습 모델로 제어)
        
    동작 흐름:
        1. 젯슨이 arm/start (action_id=1) 발행 → 변 치우기 시작
        2. 젯슨의 모방학습 로봇팔이 변 치우기 작업 수행 (자율로 처리)
        3. 젯슨이 arm/start (action_id=0) 발행 → 변 치우기 완료, 로봇팔 정지
    """
    payload = bytes([action_id & 0xFF])  # 1B
    return make_frame(ID_ARM_START, payload)

def make_arm_position_correct_frame(dx: float, dy: float, dz: float) -> bytes:
    """
    로봇 위치 보정 프레임 생성.
    
    Args:
        dx: x축 이동 거리 (m), 양수=앞, 음수=뒤
        dy: y축 이동 거리 (m), 양수=왼, 음수=오
        dz: z축 이동 거리 (m), 양수=위, 음수=아래 (현재 사용 안 함)
    
    Returns:
        UART 프레임 바이트
    
    Note:
        - STM32는 바퀴 이동만 제어 (dx, dy)
        - 로봇팔 제어는 STM32가 하지 않음 (젯슨이 모방학습 모델로 제어)
    """
    payload = struct.pack("<fff", float(dx), float(dy), float(dz))  # 12B
    return make_frame(ID_ARM_POSITION_CORRECT, payload)

def make_arm_water_frame(water_action: int) -> bytes:
    """
    로봇팔 급수 프레임 생성.
    
    급수 동작은 모방학습 로봇팔이 자율로 수행합니다:
    - 물그릇 위치로 이동 (바퀴 필요, 잠금 해제)
    - 물그릇 집기 (로봇팔 동작, 바퀴 해제 - 위치 이동 중)
    - 화장실 위치로 이동 (바퀴 필요, 잠금 해제)
    - 아루코 마커로 정밀 위치 조정 (바퀴 해제)
    - 물 버리기 (로봇팔 동작, 바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
    - 서스펜서 위치로 이동 (바퀴 필요, 잠금 해제)
    - 아루코 마커로 정밀 위치 조정 (바퀴 해제)
    - 물 받기 (로봇팔 동작, 바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
    - 물그릇 위치로 이동 (바퀴 필요, 잠금 해제)
    - 물그릇 두기 (로봇팔 동작, 바퀴 잠금)
    
    Args:
        water_action:
            - 0 = 위치 이동/정지 (바퀴 해제, 이동 가능)
            - 1 = 물그릇 집기 (바퀴 해제 - 위치 이동 중)
            - 2 = 물 버리기 (바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
            - 3 = 물 받기 (바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
            - 4 = 물그릇 두기 (바퀴 잠금 - 로봇팔 동작 중)
    
    Returns:
        UART 프레임 바이트
    
    Note:
        - STM32는 로봇팔을 직접 제어하지 않음 (젯슨이 모방학습 모델로 제어)
        - water_action = 2, 3, 4: 바퀴 모터 잠금 (로봇팔 동작 중)
        - water_action = 0, 1: 바퀴 모터 해제 (위치 이동 가능)
        - water_action = 2 (물 버리기)와 water_action = 3 (물 받기)는 아루코 마커로 정밀 위치 조정 완료 후 시작하므로 바퀴 잠금
        
    동작 흐름:
        1. 젯슨이 arm/water (water_action=0) 발행 → 위치 이동 시작 (바퀴 해제)
        2. 물그릇 위치 도착 → 젯슨이 arm/water (water_action=1) 발행 → 물그릇 집기 (바퀴 해제)
        3. 젯슨이 arm/water (water_action=0) 발행 → 화장실로 이동 (바퀴 해제)
        4. 화장실 도착 → 아루코 마커로 정밀 위치 조정 (바퀴 해제)
        5. 정밀 위치 조정 완료 → 젯슨이 arm/water (water_action=2) 발행 → 물 버리기 (바퀴 잠금)
        6. 젯슨이 arm/water (water_action=0) 발행 → 서스펜서로 이동 (바퀴 해제)
        7. 서스펜서 도착 → 아루코 마커로 정밀 위치 조정 (바퀴 해제)
        8. 정밀 위치 조정 완료 → 젯슨이 arm/water (water_action=3) 발행 → 물 받기 (바퀴 잠금)
        9. 젯슨이 arm/water (water_action=0) 발행 → 물그릇 위치로 이동 (바퀴 해제)
        10. 물그릇 위치 도착 → 젯슨이 arm/water (water_action=4) 발행 → 물그릇 두기 (바퀴 잠금)
        11. 젯슨이 arm/water (water_action=0) 발행 → 완료 (바퀴 해제)
    """
    payload = bytes([water_action & 0xFF])  # 1B
    return make_frame(ID_ARM_WATER, payload)

# ---------- 츄르 주기 (SBC -> STM32) ----------

def make_churu_frame(enable: int) -> bytes:
    """
    츄르 주기 프레임 생성.
    
    Args:
        enable: 0=정지, 1=츄르 주기 (주사기 밀기)
    
    Returns:
        UART 프레임 바이트
    
    Note:
        - STM32가 서보모터로 주사기를 밀어서 츄르를 배출
    """
    enable = max(0, min(1, enable))  # 0~1 범위로 제한
    payload = bytes([enable & 0xFF])  # 1B
    return make_frame(ID_CHURU, payload)

# ---------- STM32 -> SBC parsing (minimal) ----------

class FrameParser:
    """
    아주 단순한 상태머신 파서:
    - feed(data)로 바이트 넣으면,
    - 완성된 frame (msg_id, payload) 튜플을 yield
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = 0
        self.msg_id = 0
        self.length = 0
        self.payload = bytearray()
        self.chk = 0

    def feed(self, data: bytes):
        for b in data:
            if self.state == 0:
                if b == STX1:
                    self.state = 1
            elif self.state == 1:
                if b == STX2:
                    self.state = 2
                else:
                    self.state = 0
            elif self.state == 2:
                self.msg_id = b
                self.state = 3
            elif self.state == 3:
                self.length = b
                self.payload = bytearray()
                self.state = 4 if self.length > 0 else 5
            elif self.state == 4:
                self.payload.append(b)
                if len(self.payload) >= self.length:
                    self.state = 5
            elif self.state == 5:
                # checksum 검사
                exp = xor_checksum(self.msg_id, self.length, bytes(self.payload))
                if exp == b:
                    yield (self.msg_id, bytes(self.payload))
                # 다음 프레임 위해 초기화
                self.reset()


# ---------- STM→Pi 텔레메트리 payload → dict ----------
def _hex(b: bytes) -> str:
    return b.hex()

def decode_telemetry(msg_id: int, payload: bytes) -> Dict[str, Any]:
    """JSON으로 쓸 수 있는 dict 반환."""
    d: Dict[str, Any] = {
        "msg_id": int(msg_id),
        "raw_hex": _hex(payload),
        "len": len(payload),
    }
    if msg_id == ID_BATTERY:
        d["type"] = "battery"
        if len(payload) >= 5:
            vbat_mV, soc, chg, err = struct.unpack_from("<HBBB", payload, 0)
            d.update({
                "vbat_mV": int(vbat_mV),
                "vbat_V": float(vbat_mV) / 1000.0,
                "soc_percent": int(soc),
                "charging": bool(chg),
                "error_code": int(err),
            })
        return d
    if msg_id == ID_ENCODER:
        d["type"] = "encoder"
        if len(payload) >= 16:
            enc_fl, enc_fr, enc_rl, enc_rr = struct.unpack_from("<iiii", payload, 0)
            d.update({
                "enc_fl": int(enc_fl), "enc_fr": int(enc_fr),
                "enc_rl": int(enc_rl), "enc_rr": int(enc_rr),
            })
        return d
    if msg_id == ID_IMU:
        d["type"] = "imu"
        if len(payload) >= 24:
            yaw, pitch, roll, ax, ay, az = struct.unpack_from("<ffffff", payload, 0)
            d.update({
                "yaw": float(yaw), "pitch": float(pitch), "roll": float(roll),
                "acc_x": float(ax), "acc_y": float(ay), "acc_z": float(az),
            })
        return d
    if msg_id == ID_STATUS:
        d["type"] = "status"
        if len(payload) >= 3:
            status_type, status_code, flags = struct.unpack_from("<BBB", payload, 0)
            d.update({
                "status_type": int(status_type),
                "status_code": int(status_code),
                "flags": int(flags),
                # 편의 필드
                "arm_active": bool(flags & FLAG_ARM_ACTIVE),
                "wheels_locked": bool(flags & FLAG_WHEELS_LOCKED),
                "emergency_stop": bool(flags & FLAG_EMERGENCY_STOP),
            })
            # 작업 완료/실패 매핑
            if status_type == STATUS_TYPE_JOB_COMPLETE:
                job_map = {
                    JOB_FEED_COMPLETE: "feed",
                    JOB_CHURU_COMPLETE: "churu",
                }
                d["job_type"] = job_map.get(status_code, "unknown")
                d["job_status"] = "success"
            elif status_type == STATUS_TYPE_JOB_FAILED:
                job_map = {
                    JOB_FEED_FAILED: "feed",
                    JOB_CHURU_FAILED: "churu",
                }
                d["job_type"] = job_map.get(status_code, "unknown")
                d["job_status"] = "failed"
            elif status_type == STATUS_TYPE_ERROR:
                error_map = {
                    ERROR_MOTOR_FAULT: "motor_fault",
                    ERROR_SENSOR_FAULT: "sensor_fault",
                    ERROR_COMM_TIMEOUT: "comm_timeout",
                    ERROR_OVERLOAD: "overload",
                }
                d["error_type"] = error_map.get(status_code, "unknown")
        return d
    d["type"] = "unknown"
    return d
