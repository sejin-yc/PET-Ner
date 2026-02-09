# UART 통신 확인 가이드 (ROS 없이)

실기기 연결 후 UART 통신이 제대로 되는지 확인하는 방법입니다.

---

## 📤 시리얼로 “잘 보내고 있다” 확인하는 방법

### 1. `UART_DEBUG_TX=1` 로그 (가장 간단)

Gateway 실행 시 **TX마다 로그**를 남기게 할 수 있습니다.

```bash
export UART_DEBUG_TX=1
./scripts/run_gateway.sh
```

- `uart.enabled: true` (실기기 전송) 여도 **매 TX마다** `[UART TX] aa5502...` 형태로 로그 출력
- HEARTBEAT(5Hz), CMD_VEL(20Hz) 등이 계속 찍혀서 **시리얼로 잘 나가고 있는지** 확인 가능

**RX도 로그로 보고 싶을 때:**
```bash
export UART_DEBUG_TX=1
export UART_DEBUG_RX=1
./scripts/run_gateway.sh
```

- `[UART RX] aa5581...`: STM32에서 들어오는 텔레메트리(배터리/엔코더/IMU) 로그

### 2. 데모 모드(dry-run)에서 TX 로그

`uart.enabled: false`(기본 데모)이면 **전송하지 않고** hex만 출력합니다.

```bash
# params.yaml: uart.enabled: false 인 상태
./scripts/run_gateway.sh
```

- `[UART SEND] aa5502...` 가 주기적으로 찍힘 (HEARTBEAT, CMD_VEL 등)
- 실제 시리얼 전송은 **안 함** → “로그로 형식 확인”용

### 3. STM32 쪽에서 간접 확인

- Gateway가 HEARTBEAT / CMD_VEL 보내면, STM32가 **워치독 만족** → 모터 구동 등 정상 동작
- STM32가 **텔레메트리(0x81/0x82/0x83)** 를 보내면, Gateway `on_frame`에서 수신
- `UART_DEBUG_RX=1` 이면 `[UART RX] ...` 로 수신 hex 확인 가능 → **TX 잘 나가고 있다는 간접 증거** (STM32가 살아 있어 응답하는 경우)

### 4. 루프백 테스트 (TX↔RX 짧게 연결)

Pi **TX**와 **RX**를 점퍼로 연결한 뒤, 테스트 스크립트로 송신 hex = 수신 hex 인지 확인.

```bash
# TX–RX 연결 후 (동일 보드 UART)
python3 scripts/test_uart_simple.py /dev/ttyAMA0 115200   # Pi GPIO: ttyAMA0 또는 serial0
# 등으로 송신 → 수신 hex 비교
```

- 같은 포트로 TX/RX 돌리므로 **다른 터미널/스크립트**에서 수신만 해도 됨 (예: `hexdump -C /dev/ttyAMA0` 또는 `/dev/serial0` + `test_send_uart` 등).  
- **주의:** Gateway와 동시에 같은 포트 열면 충돌. Gateway 끄고 테스트 스크립트만 실행.

### 5. USB–UART 동글로 TX 스니핑

- Pi TX → 동글 RX 연결, 동글은 PC에 연결
- PC에서 `minicom` / `screen` / `python serial` 등으로 **동글 포트** 열고 수신
- Gateway `UART_DEBUG_TX=1` 없이도, **별도 장치**로 Pi TX 전송 내용 확인 가능

---

## 🚀 빠른 확인 방법

### 방법 1: 스크립트 사용 (가장 편함)

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway

# 기본 포트 (Pi GPIO: /dev/ttyAMA0 또는 /dev/serial0)
./scripts/test_uart.sh

# 포트 지정
./scripts/test_uart.sh /dev/ttyAMA0 115200
# ./scripts/test_uart.sh /dev/ttyUSB0 115200   # USB-UART 동글
```

### 방법 2: Python 스크립트 (프레임 파싱 포함)

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway

# 기본 포트
python3 scripts/test_uart_simple.py

# 포트 지정
python3 scripts/test_uart_simple.py /dev/ttyUSB0 115200
```

---

## 📋 터미널 명령어로 직접 확인

### 1. 포트 확인

```bash
# 사용 가능한 시리얼 포트 확인
ls -la /dev/serial* /dev/ttyUSB* /dev/ttyACM*

# GPIO 직결 (Raspberry Pi)
ls -la /dev/serial0

# USB-UART 동글
ls -la /dev/ttyUSB0
```

### 2. Raw 데이터 읽기 (hexdump)

```bash
# 5초간 데이터 읽기
timeout 5 hexdump -C /dev/serial0

# 또는 od 사용
timeout 5 od -An -tx1 /dev/serial0
```

**출력 예시:**
```
00000000  aa 55 81 05 00 00 00 00  00 00 00 00 00 00 00 00  |.U..............|
00000010  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
```

- `aa 55`: STX (프레임 시작)
- `81`: MSG_ID (배터리 = 0x81)
- `05`: LENGTH
- 마지막 바이트: CHECKSUM

### 3. 실시간 데이터 확인

```bash
# hexdump로 실시간 확인 (Ctrl+C로 종료)
sudo hexdump -C /dev/serial0

# 또는 cat + hexdump
sudo cat /dev/serial0 | hexdump -C
```

### 4. minicom 사용 (시리얼 터미널)

```bash
# 설치
sudo apt install minicom

# 실행
sudo minicom -D /dev/serial0 -b 115200

# 종료: Ctrl+A, X
```

### 5. screen 사용

```bash
# 실행
sudo screen /dev/serial0 115200

# 종료: Ctrl+A, K, Y
```

---

## 🔍 데이터 해석

### 프레임 구조

```
[STX1] [STX2] [MSG_ID] [LENGTH] [PAYLOAD...] [CHECKSUM]
 0xAA   0x55    1바이트   1바이트    N바이트      1바이트
```

### MSG_ID 확인

- `0x81` (129): 배터리 데이터
- `0x82` (130): 엔코더 데이터
- `0x83` (131): IMU 데이터

### 예시: 배터리 데이터

```
aa 55 81 05 88 13 52 00 00
│  │  │  │  │  │  │  │  │
│  │  │  │  │  │  │  │  └─ CHECKSUM
│  │  │  │  │  │  │  └─ charging (0)
│  │  │  │  │  │  └─ soc (82%)
│  │  │  │  │  └─ vbat_mV (5000 = 5.0V)
│  │  │  │  └─ LENGTH (5)
│  │  │  └─ MSG_ID (0x81 = 배터리)
│  │  └─ STX2 (0x55)
│  └─ STX1 (0xAA)
```

---

## ⚠️ 문제 해결

### 포트를 찾을 수 없음

```bash
# 포트 확인
ls -la /dev/serial* /dev/ttyUSB* /dev/ttyACM*

# dmesg로 최근 연결 확인
dmesg | tail -20
```

### 권한 오류

```bash
# 권한 부여
sudo chmod 666 /dev/serial0

# 또는 사용자를 dialout 그룹에 추가
sudo usermod -aG dialout $USER
# 로그아웃 후 다시 로그인 필요
```

### 포트가 사용 중

```bash
# 사용 중인 프로세스 확인
sudo lsof /dev/serial0

# 프로세스 종료
sudo kill -9 <PID>
```

### 데이터가 안 보임

1. **STM32가 켜져 있는지 확인**
2. **보드레이트 확인** (115200)
3. **TX/RX 핀 연결 확인**
4. **GND 연결 확인**

---

## 📊 Python으로 간단 확인

```python
import serial
import time

port = "/dev/serial0"
baud = 115200

ser = serial.Serial(port, baud, timeout=1.0)
print(f"연결: {port} @ {baud}")

try:
    while True:
        data = ser.read(256)
        if data:
            print(data.hex())
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    ser.close()
```

---

## 💡 추천 방법

1. **빠른 확인**: `./scripts/test_uart.sh`
2. **상세 확인**: `python3 scripts/test_uart_simple.py`
3. **디버깅**: `sudo hexdump -C /dev/serial0`

---

## 📝 참고

- **포트**: GPIO 직결이면 `/dev/serial0`, USB-UART면 `/dev/ttyUSB0`
- **보드레이트**: 115200 (기본값)
- **프레임 형식**: STX(0xAA 0x55) + MSG_ID + LENGTH + PAYLOAD + CHECKSUM
