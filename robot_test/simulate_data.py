import time
import json
import random
import paho.mqtt.client as mqtt

# --- 설정 ---
BROKER_ADDRESS = "localhost"  # Mosquitto 주소
PORT = 1883
TOPIC_STATUS = "/robot/status"
TOPIC_POSE = "/robot/pose"

# --- MQTT 연결 설정 ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ MQTT 브로커 연결 성공!")
    else:
        print(f"❌ 연결 실패, 코드: {rc}")

client.on_connect = on_connect

# --- 메인 로직 ---
try:
    client.connect(BROKER_ADDRESS, PORT, 60)
    client.loop_start() # 백그라운드에서 통신 시작

    # 가짜 로봇 상태
    battery = 100.0
    x = 0.0
    y = 0.0
    
    print("🚀 데이터 전송 시작 (Ctrl+C로 종료)...")
    
    while True:
        # 1. 데이터 생성 (랜덤 시뮬레이션)
        battery = max(0, battery - 0.1) # 배터리 감소
        x += random.uniform(-1, 1)      # 위치 랜덤 이동
        y += random.uniform(-1, 1)

        # 2. JSON 데이터 만들기 (RobotStatus 엔티티 필드명과 일치해야 함!)
        # MqttService.java에서 읽는 필드명을 기준으로 작성
        status_data = {
            "batteryLevel": int(battery),
            "temperature": round(random.uniform(30.0, 45.0), 1),
            "isCharging": False,
            "x": round(x, 2), # Controller용 좌표도 같이 보냄
            "y": round(y, 2),
            "mode": "simulation"
        }

        # 3. 데이터 전송 (Publish)
        payload = json.dumps(status_data)
        client.publish(TOPIC_STATUS, payload)
        
        print(f"📤 보냄: {payload}")
        
        time.sleep(1) # 1초마다 전송

except KeyboardInterrupt:
    print("\n🛑 시뮬레이션 종료")
    client.loop_stop()
    client.disconnect()