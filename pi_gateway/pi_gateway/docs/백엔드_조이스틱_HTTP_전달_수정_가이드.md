# 백엔드 조이스틱 HTTP 전달 수정 가이드

**문제**: 웹에서 조이스틱을 눌렀는데 Pi Gateway에 `[CONTROL]` 로그가 안 찍힘  
**원인**: 백엔드가 MQTT로만 전달하고 있어서 Pi Gateway에 도달하지 않음  
**해결**: 백엔드가 Pi Gateway의 HTTP `/robot/control` 엔드포인트로 직접 POST 요청 전송

---

## 📋 수정할 파일

**`RobotController.java`** (백엔드)

---

## 🔧 수정 방법

### 1단계: application.properties 또는 application.yml에 Pi Gateway URL 추가

```properties
# application.properties
pi.gateway.url=http://192.168.100.254:8000
```

또는

```yaml
# application.yml
pi:
  gateway:
    url: http://192.168.100.254:8000
```

**참고**: 
- 로컬 테스트 시: `http://localhost:8000`
- 실제 Pi IP: `http://192.168.100.254:8000` (또는 실제 Pi IP 주소)

### 2단계: RobotController.java에 RestTemplate 추가

**의존성 주입 추가:**

```java
@RestController
@RequiredArgsConstructor  // 또는 @Autowired 사용
public class RobotController {
    
    // 기존 필드들...
    private final SimpMessagingTemplate messagingTemplate;
    private final MqttService mqttService;
    
    // ✅ 추가: Pi Gateway URL
    @Value("${pi.gateway.url:http://192.168.100.254:8000}")
    private String piGatewayUrl;
    
    // ✅ 추가: RestTemplate (HTTP 요청용)
    private final RestTemplate restTemplate;
    
    // RestTemplate Bean 생성 (또는 Config 클래스에서)
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
    
    // ... 기존 코드 ...
}
```

**또는 `@RequiredArgsConstructor` 사용 시:**

```java
@RestController
@RequiredArgsConstructor
public class RobotController {
    
    private final SimpMessagingTemplate messagingTemplate;
    private final MqttService mqttService;
    
    @Value("${pi.gateway.url:http://192.168.100.254:8000}")
    private String piGatewayUrl;
    
    // RestTemplate은 Config 클래스에서 Bean으로 등록하거나
    // 여기서 직접 생성
    private final RestTemplate restTemplate = new RestTemplate();
    
    // ... 기존 코드 ...
}
```

### 3단계: handleControl 메서드 수정

**기존 `handleControl` 메서드를 찾아서 다음과 같이 수정:**

```java
@MessageMapping("/robot/control")
public void handleControl(RobotCommand command) {
    if (command.getUserId() == null) {
        System.err.println("❌ 명령 거부: UserID가 없습니다.");
        return;
    }
    
    try {
        // ✅ 옵션 A: MQTT로 전달 (기존 방식, 유지)
        String jsonCommand = objectMapper.writeValueAsString(command);
        String targetTopic = "robot/" + command.getUserId() + "/control";
        mqttService.sendCommand(targetTopic, jsonCommand);
        
        // ✅ 옵션 B: HTTP로 Pi Gateway에 직접 전달 (권장)
        // RobotCommand를 Pi Gateway 형식으로 변환
        Map<String, Object> piPayload = new HashMap<>();
        
        // 조이스틱 명령인 경우
        if ("MOVE".equals(command.getType())) {
            piPayload.put("type", "joy");
            piPayload.put("joy_x", command.getLinear() != null ? command.getLinear() : 0.0);
            piPayload.put("joy_y", 0.0);  // 좌우는 angular로 처리 (필요시 변환)
            piPayload.put("joy_active", true);
            piPayload.put("timestamp", System.currentTimeMillis() / 1000.0);
        } 
        // 버튼 명령인 경우 (예: "UP", "DOWN", "LEFT", "RIGHT")
        else if (command.getType() != null && command.getType().length() <= 10) {
            // 버튼 키 매핑 (예: "UP" -> "up", "DOWN" -> "down")
            String key = command.getType().toLowerCase();
            piPayload.put("type", "press");
            piPayload.put("key", key);
            piPayload.put("down", true);
            piPayload.put("timestamp", System.currentTimeMillis() / 1000.0);
        }
        
        // Pi Gateway로 HTTP POST 전송
        try {
            String url = piGatewayUrl + "/robot/control";
            restTemplate.postForObject(url, piPayload, Map.class);
            System.out.println("✅ Pi Gateway로 제어 명령 전송: " + command.getType());
        } catch (Exception e) {
            System.err.println("❌ Pi Gateway 전송 실패: " + e.getMessage());
            // MQTT로 fallback (이미 위에서 전송됨)
        }
        
    } catch (Exception e) {
        e.printStackTrace();
    }
}
```

### 4단계: Import 추가

```java
import org.springframework.web.client.RestTemplate;
import org.springframework.beans.factory.annotation.Value;
import java.util.HashMap;
import java.util.Map;
```

---

## 🎯 조이스틱 명령 변환 로직 (상세)

프론트엔드에서 보내는 `RobotCommand` 형식:
```json
{
  "type": "MOVE",
  "linear": 0.5,    // 전진 속도 (-1.0 ~ 1.0)
  "angular": 0.3,   // 회전 속도 (-1.0 ~ 1.0)
  "userId": 1
}
```

Pi Gateway가 기대하는 형식:
```json
{
  "type": "joy",
  "joy_x": 0.5,      // 전진/후진 (-1.0 ~ 1.0)
  "joy_y": 0.0,      // 좌/우 (-1.0 ~ 1.0)
  "joy_active": true,
  "timestamp": 1234567890.123
}
```

**변환 로직:**
- `linear` → `joy_x` (전진/후진)
- `angular` → `joy_y` (좌/우 회전, 또는 별도 처리)

**더 정확한 변환 예시:**

```java
if ("MOVE".equals(command.getType())) {
    piPayload.put("type", "joy");
    
    // linear: 전진(+)/후진(-)
    double linear = command.getLinear() != null ? command.getLinear() : 0.0;
    piPayload.put("joy_x", linear);
    
    // angular: 좌회전(+)/우회전(-) → joy_y로 변환
    // 또는 angular를 그대로 사용하거나, 회전은 별도 처리
    double angular = command.getAngular() != null ? command.getAngular() : 0.0;
    piPayload.put("joy_y", angular);  // 또는 0.0으로 고정
    
    piPayload.put("joy_active", true);
    piPayload.put("timestamp", System.currentTimeMillis() / 1000.0);
}
```

---

## ✅ 테스트 방법

### 1. 백엔드 수정 후 재시작

```bash
cd /home/ssafy/Downloads/S14P11C203-FE,BE,Infra(2)/S14P11C203-FE,BE,Infra/server
./gradlew bootRun
```

### 2. Pi Gateway 실행 확인

```bash
# Pi Gateway가 실행 중인지 확인
curl http://localhost:8000/debug/state
# 또는
curl http://192.168.100.254:8000/debug/state
```

### 3. 웹에서 조이스틱 조작

1. 프론트엔드 웹 접속 (`http://localhost:5173`)
2. 로그인 후 대시보드 접속
3. 조이스틱을 위로 드래그 (전진)

### 4. 로그 확인

**백엔드 콘솔:**
```
✅ Pi Gateway로 제어 명령 전송: MOVE
```

**Pi Gateway 콘솔:**
```
[CONTROL] joy: x=0.50 y=0.00 active=True
```

**상태 확인:**
```bash
curl http://localhost:8000/debug/state
```

응답 예시:
```json
{
  "mode": "teleop",
  "estop": false,
  "pressed": [],
  "joy_x": 0.5,
  "joy_y": 0.0,
  "joy_active": true,
  "feed_level": null,
  "last_ts": 1234567890.123
}
```

---

## 🔍 문제 해결

### 문제 1: `RestTemplate` Bean을 찾을 수 없음

**해결**: Config 클래스에 Bean 등록

```java
@Configuration
public class AppConfig {
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
```

### 문제 2: Pi Gateway 연결 실패 (`Connection refused`)

**확인 사항:**
1. Pi Gateway가 실행 중인지 확인: `curl http://192.168.100.254:8000/robot/health`
2. `application.properties`의 `pi.gateway.url` 값 확인
3. 방화벽 설정 확인 (Pi Gateway 포트 8000이 열려있는지)

### 문제 3: 조이스틱 입력이 여전히 안 찍힘

**디버깅:**
1. 백엔드 콘솔에서 `✅ Pi Gateway로 제어 명령 전송` 로그 확인
2. Pi Gateway 로그에서 `[CONTROL]` 로그 확인
3. `curl -X POST http://localhost:8000/robot/control -H "Content-Type: application/json" -d '{"type":"joy","joy_x":0.5,"joy_y":0.0,"joy_active":true,"timestamp":0}'` 직접 테스트

---

## 📝 요약

1. ✅ `application.properties`에 `pi.gateway.url` 추가
2. ✅ `RobotController`에 `RestTemplate` 주입
3. ✅ `handleControl` 메서드에서 Pi Gateway로 HTTP POST 전송 추가
4. ✅ `RobotCommand`를 Pi Gateway 형식으로 변환
5. ✅ 테스트: 웹 조이스틱 → 백엔드 → Pi Gateway → 로그 확인

이렇게 수정하면 웹에서 조이스틱을 눌렀을 때 Pi Gateway에 `[CONTROL]` 로그가 정상적으로 출력됩니다!
