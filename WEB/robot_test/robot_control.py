import asyncio
import aiohttp
import json
import logging
import serial  # ✅ 시리얼 통신 라이브러리 추가

# ✅ [설정] 웹소켓 서버 주소
WS_URL = "wss://i14c203.p.ssafy.io/ws"

# ✅ [설정] STM32 시리얼 통신 설정
SERIAL_PORT = '/dev/ttyAMA0'
BAUD_RATE = 115200

# 로깅 설정
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("RobotControl")

# -----------------------------------------------------
# 🔌 시리얼 포트 초기화
# -----------------------------------------------------
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    log.info(f"✅ STM32 Serial Connected: {SERIAL_PORT} @ {BAUD_RATE}")
except Exception as e:
    ser = None
    log.error(f"❌ STM32 Serial Connection Failed: {e}")

# -----------------------------------------------------
# 🎮 실제 동작 함수 (STM32로 명령어 전송)
# -----------------------------------------------------
def action_give_churu():
    if ser and ser.is_open:
        # 'k' 문자를 바이트로 변환하여 전송
        ser.write(b'k\n') 
        ser.flush()
        log.info("🐟 [전송] STM32로 'k' 전송 완료 (츄르)")
    else:
        log.error("❌ 시리얼 포트가 열려있지 않습니다.")

def action_give_food():
    if ser and ser.is_open:
        # 'i' 문자를 바이트로 변환하여 전송
        ser.write(b'i\n')
        ser.flush()
        log.info("🍚 [전송] STM32로 'i' 전송 완료 (밥)")
    else:
        log.error("❌ 시리얼 포트가 열려있지 않습니다.")

# -----------------------------------------------------
# 📡 통신 로직 (WebSocket)
# -----------------------------------------------------
async def run_control_client():
    while True:
        session = None
        ws = None
        try:
            log.info(f"🔄 서버 연결 시도: {WS_URL}")
            session = aiohttp.ClientSession()
            ws = await session.ws_connect(WS_URL, ssl=False)
            log.info("✅ 제어 소켓 연결 성공!")

            # STOMP 연결
            await ws.send_str("CONNECT\naccept-version:1.1,1.0\nheart-beat:10000,10000\n\n\x00")
            
            # 구독 (웹에서 보낸 명령을 받는 주소)
            await ws.send_str("SUBSCRIBE\nid:sub-ctrl\ndestination:/sub/robot/control\n\n\x00")
            log.info("🎧 명령 대기 중... (/sub/robot/control)")

            while not ws.closed:
                msg = await ws.receive()
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.data
                    # 메시지 수신 (MESSAGE 프레임)
                    if "MESSAGE" in data and "/sub/robot/control" in data:
                        try:
                            # Body 파싱
                            parts = data.split("\n\n")
                            if len(parts) > 1:
                                body = parts[-1].replace("\x00", "")
                                command_json = json.loads(body)
                                key = command_json.get("command")

                                if key == 'k':
                                    action_give_churu()
                                elif key == 'i':
                                    action_give_food()
                                else:
                                    log.warning(f"알 수 없는 명령: {key}")

                        except Exception as e:
                            log.error(f"메시지 처리 실패: {e}")

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    log.error("❌ 소켓 끊김")
                    break

        except Exception as e:
            log.error(f"연결 에러 (3초 후 재시도): {e}")
        finally:
            if ws: await ws.close()
            if session: await session.close()
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(run_control_client())
    except KeyboardInterrupt:
        # 프로그램 종료 시 시리얼 포트 닫기
        if ser and ser.is_open:
            ser.close()
            print("🔒 Serial Port Closed")