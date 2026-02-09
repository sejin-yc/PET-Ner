#!/usr/bin/env python3
"""
UART 통신 테스트 스크립트 (ROS 없이)

사용법:
    python3 scripts/test_uart.py --port /dev/serial0 --baud 115200
"""

import argparse
import sys
import time
import json
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.uart_link import UartLink, UartConfig
from src.uart_frames import decode_telemetry, make_heartbeat_frame, make_cmd_vel_frame


def test_uart_read(port: str, baud: int, duration: float = 10.0):
    """UART 읽기 테스트 - STM32에서 오는 텔레메트리 확인"""
    print("=" * 60)
    print("UART 읽기 테스트")
    print("=" * 60)
    print(f"포트: {port}")
    print(f"보드레이트: {baud}")
    print(f"테스트 시간: {duration}초")
    print("=" * 60)
    print()
    
    config = UartConfig(port=port, baudrate=baud, enabled=True, rx_thread=True)
    uart = UartLink(config)
    
    received_count = {"battery": 0, "encoder": 0, "imu": 0, "unknown": 0}
    
    def on_frame(msg_id: int, payload: bytes):
        """프레임 수신 콜백"""
        try:
            data = decode_telemetry(msg_id, payload)
            msg_type = data.get("type", "unknown")
            received_count[msg_type] = received_count.get(msg_type, 0) + 1
            
            # JSON 출력
            print(f"[{time.time():.3f}] {msg_type.upper()}: {json.dumps(data, ensure_ascii=False)}")
            
            # 상세 정보 출력
            if msg_type == "battery":
                print(f"  → 전압: {data.get('vbat_V', 0):.2f}V, "
                      f"잔량: {data.get('soc_percent', 0)}%, "
                      f"충전중: {data.get('charging', False)}")
            elif msg_type == "encoder":
                print(f"  → FL: {data.get('enc_fl')}, FR: {data.get('enc_fr')}, "
                      f"RL: {data.get('enc_rl')}, RR: {data.get('enc_rr')}")
            elif msg_type == "imu":
                print(f"  → Yaw: {data.get('yaw', 0):.3f}rad ({data.get('yaw', 0)*180/3.14159:.1f}°), "
                      f"Pitch: {data.get('pitch', 0):.3f}rad, Roll: {data.get('roll', 0):.3f}rad")
            print()
        except Exception as e:
            print(f"[ERROR] 프레임 파싱 실패: {e}")
            received_count["unknown"] += 1
    
    uart.set_on_frame(on_frame)
    
    try:
        print("UART 연결 중...")
        uart.open()
        print("✅ UART 연결 성공!")
        print()
        print("텔레메트리 수신 대기 중... (Ctrl+C로 중지)")
        print()
        
        start_time = time.time()
        while time.time() - start_time < duration:
            time.sleep(0.1)
            
            # 주기적으로 통계 출력
            elapsed = time.time() - start_time
            if int(elapsed) % 5 == 0 and elapsed > 0:
                total = sum(received_count.values())
                print(f"\n[통계] {elapsed:.1f}초 경과 - "
                      f"총 {total}개 수신 (Battery: {received_count['battery']}, "
                      f"Encoder: {received_count['encoder']}, "
                      f"IMU: {received_count['imu']})")
        
    except KeyboardInterrupt:
        print("\n\n테스트 중지됨")
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        uart.close()
        print()
        print("=" * 60)
        print("최종 통계")
        print("=" * 60)
        total = sum(received_count.values())
        for msg_type, count in received_count.items():
            if count > 0:
                print(f"  {msg_type}: {count}개")
        print(f"  총: {total}개")
        print("=" * 60)


def test_uart_write(port: str, baud: int):
    """UART 쓰기 테스트 - STM32로 명령 전송"""
    print("=" * 60)
    print("UART 쓰기 테스트")
    print("=" * 60)
    print(f"포트: {port}")
    print(f"보드레이트: {baud}")
    print("=" * 60)
    print()
    
    config = UartConfig(port=port, baudrate=baud, enabled=True, rx_thread=False)
    uart = UartLink(config)
    
    try:
        print("UART 연결 중...")
        uart.open()
        print("✅ UART 연결 성공!")
        print()
        
        # Heartbeat 전송 테스트
        print("1. Heartbeat 전송 테스트...")
        for i in range(5):
            frame = make_heartbeat_frame()
            uart.send(frame)
            print(f"   Heartbeat {i+1}/5 전송: {frame.hex()}")
            time.sleep(0.5)
        
        print()
        print("2. CMD_VEL 전송 테스트...")
        # 전진
        print("   전진 명령 전송...")
        frame = make_cmd_vel_frame(0.2, 0.0, 0.0)
        uart.send(frame)
        print(f"   프레임: {frame.hex()}")
        time.sleep(1.0)
        
        # 정지
        print("   정지 명령 전송...")
        frame = make_cmd_vel_frame(0.0, 0.0, 0.0)
        uart.send(frame)
        print(f"   프레임: {frame.hex()}")
        time.sleep(0.5)
        
        print()
        print("✅ 쓰기 테스트 완료!")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        uart.close()


def check_uart_port(port: str):
    """UART 포트 확인"""
    import os
    
    print("=" * 60)
    print("UART 포트 확인")
    print("=" * 60)
    
    if not os.path.exists(port):
        print(f"❌ 포트가 존재하지 않습니다: {port}")
        print()
        print("사용 가능한 시리얼 포트 확인:")
        print("  ls -l /dev/tty* | grep -E 'USB|serial|ACM'")
        return False
    
    print(f"✅ 포트 존재: {port}")
    
    # 권한 확인
    if os.access(port, os.R_OK | os.W_OK):
        print(f"✅ 읽기/쓰기 권한 있음")
    else:
        print(f"⚠️  읽기/쓰기 권한 없음 (sudo 필요할 수 있음)")
    
    # 포트 정보
    try:
        import stat
        stat_info = os.stat(port)
        print(f"   소유자: {stat_info.st_uid}")
        print(f"   그룹: {stat_info.st_gid}")
    except:
        pass
    
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(description="UART 통신 테스트 (ROS 없이)")
    parser.add_argument("--port", default="/dev/serial0", help="UART 포트 (기본: /dev/serial0)")
    parser.add_argument("--baud", type=int, default=115200, help="보드레이트 (기본: 115200)")
    parser.add_argument("--mode", choices=["read", "write", "check"], default="read",
                       help="테스트 모드: read(읽기), write(쓰기), check(포트 확인)")
    parser.add_argument("--duration", type=float, default=10.0,
                       help="읽기 테스트 시간(초) (기본: 10초)")
    
    args = parser.parse_args()
    
    if args.mode == "check":
        check_uart_port(args.port)
    elif args.mode == "read":
        if not check_uart_port(args.port):
            return
        test_uart_read(args.port, args.baud, args.duration)
    elif args.mode == "write":
        if not check_uart_port(args.port):
            return
        test_uart_write(args.port, args.baud)


if __name__ == "__main__":
    main()
