# WebSocket 통신 흐름 설명

WebSocket은 "전화선"이고, 그 위에서 누가 무엇을 보내는지 설명합니다.

---

## 📞 WebSocket = 전화선

**WebSocket은 통신 채널(전화선)입니다.**

- WebSocket 자체는 메시지를 보내지 않음
- WebSocket을 **사용하는 클라이언트**가 메시지를 보냄

---

## 🔄 실제 통신 흐름

### 현재 시스템 구조

```
[FE 웹 브라우저]
    ↓ HTTP/STOMP
[MQTT 브로커]
    ↓ MQTT
[MQTT 브릿지 스크립트]
    ↓ WebSocket (전화선)
[Pi Gateway]
    ↓ UART
[STM32]
```

---

## 📱 누가 WebSocket으로 메시지를 보내는가?

### 1. MQTT 브릿지 (현재 사용 중)

**파일**: `scripts/mqtt_pi_bridge.py`

```python
# MQTT 브릿지가 WebSocket으로 메시지 보냄
def _ws_send(msg):
    ws.send(json.dumps(msg))

# FE에서 A 키 누름 → MQTT 브릿지가 변환
presses = [
    ("left", angular > 0),   # ← left 보냄 (rot_l이 아님!)
    ("rot_l", False),        # ← 항상 False (보내지 않음)
]
_ws_send({"type": "press", "key": "left", "down": True})
```

**의미**: 
- MQTT 브릿지가 WebSocket(전화선)을 사용해서 `left`를 보냄
- `rot_l`은 보내지 않음 (항상 `False`)

---

### 2. 다른 클라이언트 (예: Python 스크립트, 테스트 도구)

**예시**: Python 스크립트가 WebSocket으로 직접 연결

```python
import websocket
import json

# WebSocket 연결 (전화선 연결)
ws = websocket.create_connection("ws://localhost:8000/ws/teleop")

# 직접 rot_l 보내기 (MQTT 브릿지를 거치지 않음!)
ws.send(json.dumps({
    "type": "press",
    "key": "rot_l",  # ← rot_l 직접 보냄
    "down": True,
    "timestamp": 1234567890.0
}))
```

**의미**:
- Python 스크립트가 WebSocket(전화선)을 사용해서 `rot_l`을 보냄
- MQTT 브릿지를 거치지 않으므로 `rot_l`을 보낼 수 있음

---

## 🎯 "WebSocket에서 직접 rot_l 보내기"의 의미

### 잘못된 이해
❌ "WebSocket이 rot_l을 보낸다"
- WebSocket은 전화선일 뿐, 메시지를 보내지 않음

### 올바른 이해
✅ "다른 클라이언트가 WebSocket을 통해 rot_l을 보낸다"
- Python 스크립트, 테스트 도구 등이 WebSocket을 사용해서 `rot_l`을 보냄
- MQTT 브릿지를 거치지 않으므로 `rot_l`을 보낼 수 있음

---

## 📊 비교표

| 발신자 | 통신 경로 | 보내는 키 | 결과 |
|--------|----------|----------|------|
| **FE 웹 브라우저** | FE → MQTT → MQTT 브릿지 → WebSocket → Pi Gateway | `left` (rot_l이 아님) | 좌회전 동작 |
| **MQTT 브릿지** | MQTT 브릿지 → WebSocket → Pi Gateway | `left` (rot_l은 항상 False) | 좌회전 동작 |
| **Python 스크립트** | Python 스크립트 → WebSocket → Pi Gateway | `rot_l` (직접 보냄) | 좌회전 동작 |

---

## 💡 비유로 이해하기

### 전화선 비유

**WebSocket = 전화선**
- 전화선 자체는 메시지를 보내지 않음
- 전화선을 사용하는 사람이 메시지를 보냄

**현재 시스템**:
- FE (사람 A) → MQTT 브릿지 (중계인) → 전화선 → Pi Gateway (받는 사람)
- 중계인(MQTT 브릿지)이 항상 `left`만 전달함 (`rot_l`은 전달 안 함)

**다른 클라이언트**:
- Python 스크립트 (사람 B) → 전화선 → Pi Gateway (받는 사람)
- 중계인을 거치지 않으므로 `rot_l`을 직접 보낼 수 있음

---

## 🔍 실제 코드 확인

### Pi Gateway가 받는 메시지 (`web_ws_server.py:430-435`)

```python
@app.websocket("/ws/teleop")
async def ws_teleop(ws: WebSocket):
    # WebSocket으로 메시지 수신 (누가 보냈든 상관없이 받음)
    data = await ws.receive_json()
    
    if t == "press":
        key = str(data.get("key", ""))  # "left" 또는 "rot_l" 등
        down = bool(data.get("down", False))
        if down:
            STATE.pressed.add(key)  # 받은 키를 그대로 추가
```

**의미**:
- Pi Gateway는 WebSocket으로 받은 키를 그대로 처리함
- `left`를 받으면 `left` 처리, `rot_l`을 받으면 `rot_l` 처리
- 누가 보냈는지는 상관없음 (MQTT 브릿지든, Python 스크립트든)

---

## 🎯 정리

### "WebSocket에서 직접 rot_l 보내기"의 의미

**발신자**: MQTT 브릿지가 아닌 다른 클라이언트 (예: Python 스크립트, 테스트 도구)

**통신 경로**: 
```
[다른 클라이언트] → WebSocket → [Pi Gateway]
```

**보내는 메시지**:
```json
{
    "type": "press",
    "key": "rot_l",  // ← rot_l 직접 보냄
    "down": true
}
```

**현재 시스템에서는**:
- FE → MQTT 브릿지 → WebSocket → Pi Gateway
- MQTT 브릿지가 `left`만 보냄 (`rot_l`은 보내지 않음)

**따라서**:
- `rot_l`을 보낼 수 있지만 (코드가 동작함)
- 실제로는 보내지 않음 (MQTT 브릿지가 `left`만 보냄)

---

## 💻 실제 테스트 예시

### 테스트 1: Python 스크립트로 rot_l 보내기

```python
import websocket
import json
import time

# WebSocket 연결 (전화선 연결)
ws = websocket.create_connection("ws://localhost:8000/ws/teleop")

# rot_l 보내기 (MQTT 브릿지를 거치지 않음)
ws.send(json.dumps({
    "type": "press",
    "key": "rot_l",
    "down": True,
    "timestamp": time.time()
}))

# 결과: 로봇이 좌회전함! ✅
```

### 테스트 2: FE에서 A 키 누르기

```
1. FE에서 A 키 누름
2. FE가 MQTT로 {linear: 0, angular: 1.0} 전송
3. MQTT 브릿지가 WebSocket으로 {"key": "left", "down": true} 전송
4. Pi Gateway가 "left" 처리
5. 로봇이 좌회전함 ✅
```

---

## 🎯 결론

**WebSocket = 전화선 (통신 채널)**

**"WebSocket에서 직접 rot_l 보내기"**:
- = 다른 클라이언트가 WebSocket을 사용해서 `rot_l`을 보내는 것
- = MQTT 브릿지를 거치지 않고 직접 보내는 것
- = 코드는 동작하지만, 현재 시스템에서는 사용되지 않음

**현재 시스템**:
- FE → MQTT 브릿지 → WebSocket → Pi Gateway
- MQTT 브릿지가 `left`만 보냄 (`rot_l`은 보내지 않음)
