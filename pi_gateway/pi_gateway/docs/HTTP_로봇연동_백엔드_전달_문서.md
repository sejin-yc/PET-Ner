# HTTP 로봇 연동 - 백엔드 전달 문서

**작성일**: 2026.02  
**목적**: MQTT 1883 포트 차단 시 HTTP API로 로봇 상태·제어 연동 (복붙 가능)

---

## 1. 배경

- SSAFY 서버 UFW 기본: **22번 포트만 허용**, 1883(MQTT) 미개방
- MQTT 연결 시 `timed out` 발생 → 로봇 대시보드 "연결 끊김"
- **해결**: HTTP API로 상태/제어 전송 (80/443 포트 사용)

---

## 2. 추가할 API 요약

| 메서드 | 경로 | 역할 |
|--------|------|------|
| `POST` | `/api/robot/status` | Pi → 로봇 상태 수신 (배터리, 위치, 모드) |
| `GET` | `/api/robot/control` | Pi → 대기 중인 제어 명령 조회 (수동 조작) |

---

## 3. POST /api/robot/status (상태 수신)

### 3.1 수정 파일

`RobotController.java`

### 3.2 수정 위치

`@GetMapping("/state")` 메서드 **아래에** 추가

### 3.3 추가할 코드 (복붙)

```java
/**
 * Pi Gateway가 HTTP로 로봇 상태 전송 (MQTT 1883 차단 시 대안)
 * Payload 형식: mqtt_pi_bridge와 동일
 */
@PostMapping("/status")
public ResponseEntity<?> receiveRobotStatus(@RequestBody Map<String, Object> payload) {
    try {
        Long userId = Long.valueOf(String.valueOf(payload.getOrDefault("userId", 1L)));
        
        @SuppressWarnings("unchecked")
        Map<String, Object> status = (Map<String, Object>) payload.getOrDefault("status", Map.of());
        @SuppressWarnings("unchecked")
        Map<String, Object> vehicleStatus = (Map<String, Object>) status.getOrDefault("vehicleStatus", Map.of());
        @SuppressWarnings("unchecked")
        Map<String, Object> module = (Map<String, Object>) status.getOrDefault("module", Map.of());
        @SuppressWarnings("unchecked")
        Map<String, Object> currentLocation = (Map<String, Object>) payload.getOrDefault("currentLocation", Map.of());
        
        int batteryLevel = ((Number) vehicleStatus.getOrDefault("batteryLevel", 0)).intValue();
        boolean isCharging = Boolean.TRUE.equals(vehicleStatus.get("isCharging"));
        String modeStr = String.valueOf(module.getOrDefault("status", "INACTIVE"));
        String mode = "INACTIVE".equals(modeStr) ? "manual" : "auto";
        
        double x = ((Number) currentLocation.getOrDefault("x", 0.0)).doubleValue();
        double y = ((Number) currentLocation.getOrDefault("y", 0.0)).doubleValue();
        double theta = ((Number) currentLocation.getOrDefault("theta", 0.0)).doubleValue();
        
        // RobotStatus 저장 및 WebSocket 전달
        RobotStatus s = RobotStatus.builder()
                .userId(userId)
                .batteryLevel(batteryLevel)
                .temperature(0.0)
                .isCharging(isCharging)
                .x(x)
                .y(y)
                .mode(mode)
                .build();
        statusRepository.save(s);
        messagingTemplate.convertAndSend("/sub/robot/" + userId + "/status", s);
        
        // RobotPose 저장 및 WebSocket 전달 (위치)
        RobotPose p = RobotPose.builder()
                .userId(userId)
                .x(x)
                .y(y)
                .theta(theta)
                .build();
        poseRepository.save(p);
        messagingTemplate.convertAndSend("/sub/robot/" + userId + "/pose", p);
        
        return ResponseEntity.ok().build();
    } catch (Exception e) {
        System.err.println("POST /api/robot/status 에러: " + e.getMessage());
        return ResponseEntity.badRequest().build();
    }
}
```

### 3.4 RobotController 의존성 추가

`RobotController` 클래스에 다음 필드 추가 (생성자 주입):

```java
private final RobotStatusRepository statusRepository;
private final RobotPoseRepository poseRepository;
```

`@RequiredArgsConstructor` 사용 시 자동 주입됨. 없으면 생성자에 추가.

### 3.5 import 추가

```java
import com.ssafy.robot_server.domain.RobotStatus;
import com.ssafy.robot_server.domain.RobotPose;
import com.ssafy.robot_server.repository.RobotStatusRepository;
import com.ssafy.robot_server.repository.RobotPoseRepository;
```

---

## 4. GET /api/robot/control (제어 명령 폴링)

### 4.1 제어 큐 서비스 (새 파일)

**파일 생성**: `server/src/main/java/com/ssafy/robot_server/service/RobotControlQueueService.java`

```java
package com.ssafy.robot_server.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

@Slf4j
@Service
public class RobotControlQueueService {

    // userId별 대기 제어 명령 큐 (MQTT 대신 HTTP 폴링용)
    private final Map<Long, ConcurrentLinkedQueue<Map<String, Object>>> queues = new ConcurrentHashMap<>();

    public void push(Long userId, Map<String, Object> command) {
        queues.computeIfAbsent(userId, k -> new ConcurrentLinkedQueue<>()).offer(command);
    }

    public Map<String, Object> poll(Long userId) {
        var q = queues.get(userId);
        return (q != null) ? q.poll() : null;
    }
}
```

### 4.2 RobotController - 제어 수신 시 큐에 추가

`handleControl` 메서드 수정: MQTT 발행 **후** 큐에도 push

```java
// 기존 handleControl 메서드에 추가 (RobotControlQueueService 주입 필요)
@MessageMapping("/robot/control")
public void handleControl(RobotCommand command) {
    if (command.getUserId() == null) {
        System.err.println("❌ 명령 거부: UserID가 없습니다.");
        return;
    }
    try {
        String jsonCommand = objectMapper.writeValueAsString(command);
        String targetTopic = "robot/" + command.getUserId() + "/control";
        mqttService.sendCommand(targetTopic, jsonCommand);
        
        // HTTP 폴링용 큐에 추가 (MQTT 차단 시 대안)
        Map<String, Object> cmd = Map.of(
            "type", command.getType() != null ? command.getType() : "MOVE",
            "linear", command.getLinear(),
            "angular", command.getAngular(),
            "value", command.getValue() != null ? command.getValue() : ""
        );
        robotControlQueueService.push(command.getUserId(), cmd);
    } catch (Exception e) {
        e.printStackTrace();
    }
}
```

### 4.3 RobotController - GET /api/robot/control 추가

```java
/**
 * Pi Gateway가 HTTP 폴링으로 제어 명령 수신 (MQTT 1883 차단 시 대안)
 */
@GetMapping("/control")
public ResponseEntity<?> pollRobotControl(@RequestParam(value = "userId", defaultValue = "1") Long userId) {
    var cmd = robotControlQueueService.poll(userId);
    if (cmd == null) {
        return ResponseEntity.ok().body(Map.of());
    }
    return ResponseEntity.ok(cmd);
}
```

### 4.4 RobotController 의존성

```java
private final RobotControlQueueService robotControlQueueService;
```

---

## 5. Pi Gateway 측 (당신 담당)

`mqtt_pi_bridge.py`가 **HTTP 모드**를 기본으로 지원합니다. 백엔드 API 추가 후:

```bash
BE_SERVER_URL=https://i14c203.p.ssafy.io PI_GATEWAY_URL=http://localhost:8000 ./scripts/run_mqtt_bridge.sh
```

(HTTP가 기본이므로 `BE_USE_HTTP=1` 생략 가능)

- **상태**: `POST https://i14c203.p.ssafy.io/api/robot/status` (약 5Hz)
- **제어**: `GET https://i14c203.p.ssafy.io/api/robot/control?userId=1` (약 10Hz 폴링)

---

## 6. Payload 형식 (POST /api/robot/status)

```json
{
  "userId": 1,
  "status": {
    "vehicleStatus": {
      "batteryLevel": 78,
      "isCharging": false
    },
    "module": {
      "status": "ACTIVE"
    }
  },
  "currentLocation": {
    "x": 2.34,
    "y": 1.56,
    "theta": 0.78
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `userId` | number | 유저 ID (필수) |
| `status.vehicleStatus.batteryLevel` | number | 배터리 % |
| `status.vehicleStatus.isCharging` | boolean | 충전 여부 |
| `status.module.status` | string | "ACTIVE"(자동) / "INACTIVE"(수동) |
| `currentLocation.x`, `.y`, `.theta` | number | 맵 좌표(m), 방향(rad) |

---

## 7. 체크리스트

- [ ] RobotController에 `POST /api/robot/status` 추가
- [ ] RobotController에 `statusRepository`, `poseRepository` 주입
- [ ] RobotControlQueueService.java 생성
- [ ] handleControl에서 큐 push 추가
- [ ] RobotController에 `GET /api/robot/control` 추가

---

## 8. 참고

- 1883(MQTT) 막혀 있음 → HTTP만 사용
- HTTP API는 80/443 포트만 사용하므로 UFW/Lightsail 방화벽 변경 불필요
- Pi → Backend는 서버 간 통신이라 CORS 적용 안 됨
