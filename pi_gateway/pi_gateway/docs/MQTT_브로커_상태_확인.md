# MQTT 브로커 상태 확인 가이드

Docker 없이 Mosquitto가 실행 중인지 확인하고 테스트하는 방법입니다.

---

## ✅ 현재 상태

**Mosquitto가 이미 실행 중입니다!**

- 프로세스: `/usr/sbin/mosquitto`
- 설정 파일: `/etc/mosquitto/mosquitto.conf`
- 포트: 1883 (기본)

---

## 🧪 연결 테스트

### 방법 1: mosquitto 클라이언트로 테스트

```bash
# 터미널 1: 구독자
mosquitto_sub -h localhost -p 1883 -t "test/topic"

# 터미널 2: 발행자
mosquitto_pub -h localhost -p 1883 -t "test/topic" -m "Hello MQTT"
```

**예상 결과:**
- 터미널 1에서 "Hello MQTT" 메시지가 표시되면 성공!

### 방법 2: Pi Gateway MQTT 브릿지로 테스트

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway

export PI_GATEWAY_URL=http://localhost:8000
export MQTT_HOST=localhost
export MQTT_PORT=1883

python3 scripts/mqtt_pi_bridge.py
```

**확인:**
- 콘솔에 `[MQTT] ✅ 연결 성공!` 메시지 확인
- `[STATUS] Publishing to /sub/robot/status` 로그 확인

---

## 🔍 상태 확인 명령어

### Mosquitto 프로세스 확인

```bash
# 실행 중인지 확인
ps aux | grep mosquitto | grep -v grep

# 프로세스 ID 확인
pgrep -x mosquitto
```

### 포트 확인

```bash
# 포트 1883 사용 확인
netstat -tlnp | grep 1883
# 또는
ss -tlnp | grep 1883
```

### 로그 확인

```bash
# Mosquitto 로그 확인
sudo tail -f /var/log/mosquitto/mosquitto.log

# 또는 (systemd 사용 시)
sudo journalctl -u mosquitto -f
```

---

## 🚀 다음 단계

1. **Pi Gateway 실행**
   ```bash
   cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
   export PYTHONPATH="$(pwd):$PYTHONPATH"
   export DEMO_MODE=1
   python3 src/main.py
   ```

2. **MQTT 브릿지 실행** (새 터미널)
   ```bash
   cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
   export PI_GATEWAY_URL=http://localhost:8000
   export MQTT_HOST=localhost
   export MQTT_PORT=1883
   python3 scripts/mqtt_pi_bridge.py
   ```

3. **BE 서버 실행** (새 터미널)
   ```bash
   cd "/home/ssafy/Downloads/S14P11C203-FE,BE,Infra(2)/S14P11C203-FE,BE,Infra/server"
   ./gradlew bootRun
   ```

4. **FE 웹 실행** (새 터미널)
   ```bash
   cd "/home/ssafy/Downloads/S14P11C203-FE,BE,Infra(2)/S14P11C203-FE,BE,Infra/client"
   npm run dev
   ```

---

## ⚠️ 문제 해결

### Mosquitto가 실행되지 않을 때

```bash
# 수동 실행
mosquitto -c /etc/mosquitto/mosquitto.conf -d

# 또는 스크립트 사용
/home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway/scripts/start_mosquitto.sh
```

### 포트 충돌

```bash
# 포트 1883을 사용하는 프로세스 확인
sudo lsof -i :1883

# 기존 프로세스 종료
sudo pkill mosquitto
```

### 연결 실패

```bash
# 방화벽 확인 (필요시)
sudo ufw status
sudo ufw allow 1883/tcp
```

---

## 💡 Docker vs 직접 설치

**현재 상황:**
- ✅ Mosquitto가 직접 설치되어 실행 중
- ❌ Docker 권한 문제로 Docker 사용 불가

**권장:**
- 현재 상태 그대로 사용 (Docker 불필요)
- MQTT 브릿지는 `localhost:1883`로 연결하면 됩니다
