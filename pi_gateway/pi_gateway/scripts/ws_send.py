import asyncio, json, time
import websockets

URL = "ws://127.0.0.1:8000/ws/teleop"

async def main():
    async with websockets.connect(URL) as ws:
        print("[OK] connected:", URL)
        print("[OK] connected:", URL)

        # 1) auto 모드로 전환
        await ws.send(json.dumps({"type":"mode","mode":"auto"}))
        print("[TX] mode=auto")

        # 2) joy 입력(전진)
        await ws.send(json.dumps({
            "type":"joy",
            "joy_x": 0.5, "joy_y": 0.0,
            "joy_active": True,
            "timestamp": time.time()
        }))
        print("[TX] joy forward")

        # 3) e-stop 걸기
        await ws.send(json.dumps({"type":"estop","value": True}))
        print("[TX] estop=true")

        # 4) e-stop 해제 + teleop 복귀
        await asyncio.sleep(0.2)
        await ws.send(json.dumps({"type":"estop","value": False}))
        await ws.send(json.dumps({"type":"mode","mode":"teleop"}))
        print("[TX] estop=false, mode=teleop")

        # 서버가 보내는 메시지가 있으면 받아보기(없으면 그냥 타임아웃)
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                print("[RX]", msg)
        except asyncio.TimeoutError:
            print("[DONE] no more messages (server may be one-way).")

if __name__ == "__main__":
    asyncio.run(main())

