#!/usr/bin/env python3
"""
UART 통신 간단 확인 스크립트 (ROS 없이)
사용법: python3 scripts/test_uart_simple.py [포트] [보드레이트]
"""

import sys
import time
import serial
from src.uart_frames import FrameParser, decode_telemetry

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/serial0"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
    
    print("=" * 50)
    print("UART 통신 확인")
    print("=" * 50)
    print(f"포트: {port}")
    print(f"보드레이트: {baud}")
    print("=" * 50)
    print()
    
    try:
        ser = serial.Serial(port, baud, timeout=1.0)
        print(f"✅ UART 연결 성공: {port}")
        print()
        print("데이터 수신 중... (Ctrl+C로 종료)")
        print("-" * 50)
        
        parser = FrameParser()
        count = 0
        
        while True:
            data = ser.read(256)
            if not data:
                continue
            
            # 프레임 파싱
            for msg_id, payload in parser.feed(data):
                count += 1
                decoded = decode_telemetry(msg_id, payload)
                
                print(f"[{count}] MSG_ID=0x{msg_id:02X} ({msg_id})")
                print(f"      Payload: {payload.hex()}")
                print(f"      Decoded: {decoded}")
                print()
                
                # 타입별 상세 출력
                if decoded.get("type") == "battery":
                    print(f"      🔋 배터리: {decoded.get('soc_percent', 'N/A')}%, "
                          f"{decoded.get('vbat_V', 'N/A')}V, "
                          f"충전중: {decoded.get('charging', False)}")
                elif decoded.get("type") == "encoder":
                    print(f"      ⚙️  엔코더: FL={decoded.get('enc_fl', 'N/A')}, "
                          f"FR={decoded.get('enc_fr', 'N/A')}, "
                          f"RL={decoded.get('enc_rl', 'N/A')}, "
                          f"RR={decoded.get('enc_rr', 'N/A')}")
                elif decoded.get("type") == "imu":
                    print(f"      📐 IMU: yaw={decoded.get('yaw', 'N/A'):.3f}rad, "
                          f"pitch={decoded.get('pitch', 'N/A'):.3f}, "
                          f"roll={decoded.get('roll', 'N/A'):.3f}")
                print()
                
    except serial.SerialException as e:
        print(f"❌ 오류: UART 연결 실패")
        print(f"   {e}")
        print()
        print("확인 사항:")
        print(f"  1. 포트 존재 확인: ls -la {port}")
        print(f"  2. 권한 확인: sudo chmod 666 {port}")
        print(f"  3. 사용 중인지 확인: lsof {port}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("종료됨")
    finally:
        if 'ser' in locals():
            ser.close()
            print("UART 연결 종료")

if __name__ == "__main__":
    main()
