# 테스트 가이드: 통신 vs 기능

문제가 생겼을 때 **통신 문제인지**, **기능/로직 문제인지** 구분해서 확인하는 방법입니다.

---

## 1. 역할 구분

| 구분 | 담당 스크립트 | 역할 |
|------|---------------|------|
| **통신** | `mqtt_pi_bridge.py` | MQTT ↔ Pi Gateway, Spring 연동 |
| **기능** | `cat_detection_service.py` | 고양이 탐지, 액션/감정 분석, 15초 영상 저장 |
| **핵심** | `main.py` (Pi Gateway) | UART, ROS, HTTP API |

---

## 2. 통신만 테스트 (기능 제외)

MQTT, Spring, Pi Gateway 연동이 정상인지 확인할 때 사용합니다.

### 2.1 Pi Gateway + MQTT 브릿지

```bash
# 터미널 1
./scripts/run_gateway.sh

# 터미널 2 (로컬 Mosquitto)
export MQTT_HOST=localhost
export MQTT_PORT=1883
export PI_GATEWAY_URL=http://localhost:8000
python3 scripts/mqtt_pi_bridge.py
```

### 2.2 제어 명령 전송

```bash
# 터미널 3
mosquitto_pub -h localhost -p 1883 -t "/pub/robot/control" \
  -m '{"type":"MOVE","linear":0.5,"angular":0}'
```

### 2.3 결과 확인

```bash
curl http://localhost:8000/debug/state
# pressed에 "up" 있으면 통신 정상
```

**정리**: 위 흐름이 되면 **통신은 정상**. 문제가 있다면 MQTT, Pi Gateway, 포트 확인.

---

## 3. 기능만 테스트 (통신 제외)

고양이 탐지, 액션/감정 분석, 15초 저장이 정상인지 확인할 때 사용합니다.

### 3.1 Cat Detection 단독 실행 (MQTT·Spring 미사용)

```bash
# BE_SERVER_URL, MQTT_HOST 비우고 실행
unset BE_SERVER_URL
unset MQTT_HOST
./scripts/run_cat_detection.sh
```

또는:

```bash
python3 scripts/cat_detection_service.py \
  --ckpt ./models/swin_tiny_best/best.pt \
  --yolo_pose ./models/yolo_pose.pt \
  --camera 0 \
  --show
```

### 3.2 확인 포인트

| 확인 | 방법 |
|------|------|
| 카메라 출력 | `--show` 시 창에 영상 표시 |
| 고양이 탐지 | 화면에 "CAT!" 표시 |
| 액션/감정 | Action, Emotion 텍스트 변경 |
| 15초 저장 | `./cat_clips/` 에 mp4 생성 |

**정리**: 위가 되면 **기능은 정상**. 문제가 있다면 카메라, 모델 경로, 의존성 확인.

---

## 4. 통신 + 기능 함께 테스트

전체 연동이 되는지 확인할 때 사용합니다.

```bash
# 터미널 1: Pi Gateway
./scripts/run_gateway.sh

# 터미널 2: MQTT 브릿지
export MQTT_HOST=localhost
export PI_GATEWAY_URL=http://localhost:8000
python3 scripts/mqtt_pi_bridge.py

# 터미널 3: Cat Detection (Spring 연동 포함)
export BE_SERVER_URL=https://i14c203.p.ssafy.io  # 실제 서버
./scripts/run_cat_detection.sh
```

---

## 5. 문제 유형별 점검

| 증상 | 우선 확인 |
|------|-----------|
| 웹에서 수동조작 안 됨 | 통신 (MQTT 브릿지, SSAFY MQTT 연결) |
| 갤러리에 영상 안 뜸 | 통신 (Spring API) + 기능 (cat_clips 저장) |
| 고양이 탐지가 안 됨 | 기능 (모델, 카메라) |
| 15초 영상이 안 저장됨 | 기능 (ring buffer, cat_clips 경로) |
| 액션/감정이 이상함 | 기능 (Swin 모델, cls_buf) |

---

## 6. 요약

1. **통신 문제일 때** → 섹션 2 (통신만 테스트)
2. **기능 문제일 때** → 섹션 3 (기능만 테스트)
3. **둘 다 확인할 때** → 섹션 4 (전체 연동)

각각 따로 실행해서 어디에서 끊기는지 먼저 확인하면 원인을 좁히기 쉽습니다.
