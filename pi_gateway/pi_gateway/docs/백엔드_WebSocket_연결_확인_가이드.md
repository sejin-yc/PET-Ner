# 백엔드 WebSocket 연결 확인 가이드

백엔드가 Pi Gateway의 WebSocket에 연결했다고 하셨는데, 조이스틱 입력이 전달되지 않는 경우 확인 방법입니다.

---

## 🔍 Pi Gateway WebSocket 엔드포인트

Pi Gateway는 다음 WebSocket 엔드포인트를 제공합니다:

- **경로**: `ws://192.168.100.254:8000/ws/teleop` (또는 `ws://localhost:8000/ws/teleop`)
- **용도**: 조이스틱 제어 명령 수신

---

## 📋 백엔드가 보내야 하는 메시지 형식

### 조이스틱 명령 (MOVE)

```json
{
  "type": "joy",
  "joy_x": 0.5,        // 전진(+)/후진(-), -1.0 ~ 1.0
  "joy_y": 0.0,        // 좌(+)/우(-), -1.0 ~ 1.0
  "joy_active": true,  // 조이스틱 입력 유효 여부
  "timestamp": 1234567890.123
}
```

### 버튼 명령 (UP, DOWN, LEFT, RIGHT)

```json
{
  "type": "press",
  "key": "up",         // "up", "down", "left", "right", "rot_l", "rot_r"
  "down": true,         // true=누름, false=뗌
  "timestamp": 1234567890.123
}
```

### 모드 전환

```json
{
  "type": "mode",
  "mode": "teleop",    // "teleop" 또는 "auto"
  "timestamp": 1234567890.123
}
```

---

## ✅ 백엔드 연결 확인 방법

### 1. Pi Gateway 로그 확인

Pi Gateway 실행 중인 터미널에서 다음 로그가 보여야 합니다:

```
WS/TELEOP client connected, mode=teleop, estop=False
```

**이 로그가 안 보이면**: 백엔드가 WebSocket 연결에 실패한 것입니다.

### 2. WebSocket 연결 테스트 (수동)

백엔드 코드 없이 직접 테스트:

```bash
# Python으로 WebSocket 테스트
python3 -c "
import websocket
import json
import time

def on_message(ws, message):
    print('📩 수신:', message)

def on_error(ws, error):
    print('❌ 에러:', error)

def on_close(ws, close_status_code, close_msg):
    print('🔌 연결 종료')

def on_open(ws):
    print('✅ 연결 성공!')
    # 조이스틱 명령 전송
    cmd = {
        'type': 'joy',
        'joy_x': 0.5,
        'joy_y': 0.0,
        'joy_active': True,
        'timestamp': time.time()
    }
    ws.send(json.dumps(cmd))
    print('📤 명령 전송:', cmd)

ws = websocket.WebSocketApp('ws://localhost:8000/ws/teleop',
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close,
                            on_open=on_open)
ws.run_forever()
"
```

**또는 브라우저 콘솔에서:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/teleop');
ws.onopen = () => {
    console.log('✅ 연결 성공!');
    ws.send(JSON.stringify({
        type: 'joy',
        joy_x: 0.5,
        joy_y: 0.0,
        joy_active: true,
        timestamp: Date.now() / 1000
    }));
};
ws.onmessage = (e) => console.log('📩 수신:', e.data);
ws.onerror = (e) => console.error('❌ 에러:', e);
```

### 3. Pi Gateway 상태 확인

WebSocket으로 명령을 보낸 후:

```bash
curl http://localhost:8000/debug/state
```

`joy_x`, `joy_y`, `joy_active` 값이 변경되었는지 확인합니다.

---

## 🔧 백엔드 코드 확인 포인트

백엔드가 Pi Gateway WebSocket에 연결할 때 확인해야 할 사항:

### 1. 연결 URL 확인

```java
// 올바른 URL 형식
String piGatewayWsUrl = "ws://192.168.100.254:8000/ws/teleop";
// 또는
String piGatewayWsUrl = "ws://localhost:8000/ws/teleop";
```

### 2. 메시지 형식 확인

백엔드가 보내는 메시지가 Pi Gateway가 기대하는 형식과 일치하는지 확인:

**❌ 잘못된 형식 (백엔드가 보낼 수 있는 형식):**
```json
{
  "type": "MOVE",
  "linear": 0.5,
  "angular": 0.3,
  "userId": 1
}
```

**✅ 올바른 형식 (Pi Gateway가 기대하는 형식):**
```json
{
  "type": "joy",
  "joy_x": 0.5,
  "joy_y": 0.0,
  "joy_active": true,
  "timestamp": 1234567890.123
}
```

### 3. 변환 로직 필요

백엔드가 프론트엔드로부터 받은 `RobotCommand`를 Pi Gateway 형식으로 변환해야 합니다:

```java
// 프론트엔드로부터 받은 명령
RobotCommand command = ...; // type="MOVE", linear=0.5, angular=0.3

// Pi Gateway 형식으로 변환
Map<String, Object> piMessage = new HashMap<>();
if ("MOVE".equals(command.getType())) {
    piMessage.put("type", "joy");
    piMessage.put("joy_x", command.getLinear());  // linear → joy_x
    piMessage.put("joy_y", command.getAngular());  // angular → joy_y (또는 0.0)
    piMessage.put("joy_active", true);
    piMessage.put("timestamp", System.currentTimeMillis() / 1000.0);
}

// WebSocket으로 전송
webSocketSession.sendMessage(new TextMessage(objectMapper.writeValueAsString(piMessage)));
```

---

## 🎯 권장 방법: HTTP POST 사용

WebSocket 연결이 복잡하거나 문제가 있을 때는 **HTTP POST**를 사용하는 것이 더 간단합니다:

### 백엔드에서 HTTP POST로 전송

```java
@Value("${pi.gateway.url:http://192.168.100.254:8000}")
private String piGatewayUrl;

private final RestTemplate restTemplate = new RestTemplate();

@MessageMapping("/robot/control")
public void handleControl(RobotCommand command) {
    // Pi Gateway 형식으로 변환
    Map<String, Object> piPayload = new HashMap<>();
    if ("MOVE".equals(command.getType())) {
        piPayload.put("type", "joy");
        piPayload.put("joy_x", command.getLinear() != null ? command.getLinear() : 0.0);
        piPayload.put("joy_y", 0.0);
        piPayload.put("joy_active", true);
        piPayload.put("timestamp", System.currentTimeMillis() / 1000.0);
    }
    
    // HTTP POST로 전송
    try {
        String url = piGatewayUrl + "/robot/control";
        restTemplate.postForObject(url, piPayload, Map.class);
        System.out.println("✅ Pi Gateway로 제어 명령 전송: " + command.getType());
    } catch (Exception e) {
        System.err.println("❌ Pi Gateway 전송 실패: " + e.getMessage());
    }
}
```

**장점:**
- 연결 관리 불필요 (HTTP는 요청마다 연결)
- 재연결 로직 불필요
- 디버깅 쉬움 (curl로 직접 테스트 가능)
- 로그 확인 쉬움 (`[CONTROL]` 로그가 명확히 보임)

---

## 🔍 문제 해결 체크리스트

- [ ] Pi Gateway가 실행 중인지 확인 (`curl http://localhost:8000/robot/health`)
- [ ] 백엔드가 WebSocket 연결에 성공했는지 확인 (Pi Gateway 로그: `WS/TELEOP client connected`)
- [ ] 백엔드가 보내는 메시지 형식이 올바른지 확인 (`type: "joy"`, `joy_x`, `joy_y` 필드 존재)
- [ ] Pi Gateway 로그에서 `[CONTROL]` 또는 `WS/TELEOP` 로그 확인
- [ ] `curl http://localhost:8000/debug/state`로 상태 변경 확인

---

## 📝 백엔드 코드 예시 (Spring WebSocket)

```java
@Component
public class PiGatewayWebSocketClient {
    
    @Value("${pi.gateway.url:ws://192.168.100.254:8000}")
    private String piGatewayUrl;
    
    private WebSocketSession session;
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    @PostConstruct
    public void connect() {
        try {
            WebSocketContainer container = ContainerProvider.getWebSocketContainer();
            URI uri = URI.create(piGatewayUrl + "/ws/teleop");
            session = container.connectToServer(new ClientEndpoint() {
                @OnOpen
                public void onOpen(Session session) {
                    System.out.println("✅ Pi Gateway WebSocket 연결 성공");
                }
                
                @OnMessage
                public void onMessage(String message) {
                    System.out.println("📩 Pi Gateway로부터 수신: " + message);
                }
                
                @OnError
                public void onError(Throwable error) {
                    System.err.println("❌ WebSocket 에러: " + error.getMessage());
                }
            }, uri);
        } catch (Exception e) {
            System.err.println("❌ WebSocket 연결 실패: " + e.getMessage());
        }
    }
    
    public void sendControl(RobotCommand command) {
        if (session == null || !session.isOpen()) {
            System.err.println("❌ WebSocket 연결되지 않음");
            return;
        }
        
        try {
            Map<String, Object> piMessage = new HashMap<>();
            if ("MOVE".equals(command.getType())) {
                piMessage.put("type", "joy");
                piMessage.put("joy_x", command.getLinear() != null ? command.getLinear() : 0.0);
                piMessage.put("joy_y", 0.0);
                piMessage.put("joy_active", true);
                piMessage.put("timestamp", System.currentTimeMillis() / 1000.0);
            }
            
            String json = objectMapper.writeValueAsString(piMessage);
            session.getBasicRemote().sendText(json);
            System.out.println("✅ Pi Gateway로 명령 전송: " + json);
        } catch (Exception e) {
            System.err.println("❌ 메시지 전송 실패: " + e.getMessage());
        }
    }
}
```

---

## 💡 추천: HTTP POST 사용

WebSocket 연결이 복잡하거나 문제가 있을 때는 **HTTP POST**를 사용하는 것을 강력히 권장합니다:

- ✅ 구현 간단
- ✅ 디버깅 쉬움
- ✅ 재연결 불필요
- ✅ 로그 확인 명확

자세한 내용은 `백엔드_조이스틱_HTTP_전달_수정_가이드.md`를 참고하세요.
