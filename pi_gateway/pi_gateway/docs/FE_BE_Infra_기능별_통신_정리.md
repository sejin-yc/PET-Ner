# FE, BE, Infra(5) 기능별 통신 방식 정리

> FE,BE,Infra(5) 폴더 기준으로 기능별 통신 경로를 정리한 문서입니다.

---

## 1. 인프라 구성 (docker-compose)

| 서비스 | 역할 | 포트 | 비고 |
|--------|------|------|------|
| postgres | PostgreSQL DB | 5432 | |
| robot_mqtt | Eclipse Mosquitto (MQTT 브로커) | 1883 (TCP), 9001 (WebSocket) | |
| robot_server | Spring Boot 백엔드 | 8080 | |
| robot_client | React 프론트엔드 | 80 (내부) | |
| robot_nginx | Nginx 리버스 프록시 | 80, 443 | |
| robot_media | MediaMTX (스트리밍) | 8554, 8888, 8889 | |
| certbot | SSL 인증서 갱신 | - | |

---

## 2. Nginx 라우팅 (default.conf)

| 경로 | 프록시 대상 | 용도 |
|------|-------------|------|
| `/` | robot_client:80 | 프론트엔드 |
| `/api` | robot_server:8080 | REST API |
| `/mqtt` | robot_mqtt:9001 | MQTT WebSocket (wss) |
| `/ws` | robot_server:8080 | STOMP WebSocket (로봇 데이터, WebRTC 시그널링) |
| `/signal` | robot_server:8080 | WebRTC 시그널링 (대안) |
| `/ros2` | robot_server:8080 | ROS2 로봇 WebSocket |
| `/uploads` | /var/www/uploads | 이미지/동영상 정적 파일 |

---

## 3. 기능별 통신 방식

### 3.1 인증 (회원가입/로그인)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → BE | **HTTP REST** | `POST /api/user/register` | 회원가입 |
| FE → BE | **HTTP REST** | `POST /api/user/login` | 로그인, JWT 토큰 반환 |
| FE | - | localStorage (token, user) | 로그인 유지 |

- **FE**: AuthContext.jsx → axios
- **BE**: UserController.java

---

### 3.2 로봇 초기 상태 조회

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → BE | **HTTP REST** | `GET /api/robot/state?userId=` | 초기 상태(모드, 배터리 등) |

- **FE**: RobotContext.jsx `fetchInitialState()` → api.get()
- **BE**: RobotController.getRobotState() → mock 데이터 반환
- **비고**: 실제 로봇 상태는 MQTT `robot/{userId}/status` 로 실시간 수신

---

### 3.3 수동 조작 (이동/비상정지/모드변경)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → Mosquitto | **MQTT** | `robot/{userId}/control` 발행 | MOVE, EMERGENCY_STOP, MODE_CHANGE |
| Mosquitto → 로봇 | **MQTT** | `robot/{userId}/control` 구독 | robot_test/mqtt_bridge.py |
| 로봇 | ROS2 | `/cmd_vel_joy` 발행 | geometry_msgs/Twist |

**페이로드 예시:**
```json
{"userId": 1, "type": "MOVE", "linear": 0.5, "angular": 0.0}
{"userId": 1, "type": "EMERGENCY_STOP"}
{"userId": 1, "type": "MODE_CHANGE", "mode": "auto"}
```

- **FE**: RobotContext.moveRobot(), emergencyStop(), toggleMode() → mqtt.publish()
- **로봇**: mqtt_bridge.py (ROS2 노드) → /cmd_vel_joy 발행
- **통신**: FE ↔ MQTT 브로커 ↔ 로봇 (백엔드 경유 없음)

---

### 3.4 로봇 상태 수신 (실시간)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| 로봇 → Mosquitto | **MQTT** | `robot/{userId}/status` 발행 | pose, battery, mode 등 |
| Mosquitto → FE | **MQTT** | `robot/{userId}/status` 구독 | RobotContext |
| Mosquitto → BE | **MQTT** | `/#` 구독 | MqttService → DB 저장 + STOMP 전달 |

**페이로드 예시:**
```json
{"userId": 1, "x": 1.5, "y": 2.0, "theta": 0.1, "battery": 80, "mode": "manual", ...}
```

- **로봇**: mqtt_bridge.py - /amcl_pose 구독 → status 발행
- **FE**: RobotContext - mqtt.subscribe(`robot/${userId}/status`)
- **BE**: MqttService - status 수신 시 RobotStatus DB 저장, SimpMessagingTemplate으로 /topic/robot/{userId}/status 브로드캐스트 (STOMP 구독 클라이언트용)

---

### 3.5 TTS (텍스트 음성 출력)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → BE | **HTTP REST** | `POST /api/robot/tts` | { text, useClonedVoice, userId } |
| BE → 로봇 | **MQTT** | `robot/{userId}/control` 발행 | {"type":"TTS","text":"..."} |

- **FE**: RobotContext.sendTTS() → api.post('/robot/tts')
- **BE**: RobotController.sendTts() → MqttService.sendCommand()
- **로봇**: mqtt control 구독, type=TTS 처리 (Pi Gateway 등에서 음성 출력)

---

### 3.6 목소리 학습 완료

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → BE | **HTTP REST** | `POST /api/robot/training/complete` | { userId } |

- **FE**: RobotContext.trainVoice()
- **BE**: RobotController.completeTraining() → User.voiceTrained=true DB 저장

---

### 3.7 비디오 스트리밍 (WebRTC)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE ↔ BE | **WebSocket (STOMP)** | `wss://.../ws` | 시그널링 |
| FE | STOMP 구독 | `/sub/peer/offer` | 로봇 Offer 수신 |
| FE | STOMP 발행 | `/pub/peer/answer` | Answer 전송 |
| 로봇 | STOMP 발행 | `/pub/peer/offer` | Offer 전송 (ROS /front_cam/compressed → VideoStreamTrack) |
| 로봇 | STOMP 구독 | `/sub/peer/answer` | Answer 수신 |
| FE ↔ 로봇 | **WebRTC P2P** | - | 미디어 스트림 (STUN: stun.l.google.com) |

- **FE**: StreamPanel.jsx - raw WebSocket + STOMP 프레임, RTCPeerConnection
- **로봇**: robot_webrtc.py - ROS CompressedImage 구독 → aiortc VideoStreamTrack
- **BE**: WebSocketConfig (STOMP broker), WebRTCController (MessageMapping /pub/peer/offer, /pub/peer/answer)

---

### 3.8 고양이 관리 (반려묘 등록/조회/삭제)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → BE | **HTTP REST** | `GET /api/cats?userId=` | 목록 조회 |
| FE → BE | **HTTP REST** | `POST /api/cats` | 고양이 등록 |
| FE → BE | **HTTP REST** | `DELETE /api/cats/{id}` | 삭제 |

- **FE**: PetContext.jsx (CatProvider)
- **BE**: CatController.java
- **용도**: 로봇 AI의 고양이 인식/매칭용 마스터 데이터

---

### 3.9 영상 갤러리 (고양이 감지 영상)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → BE | **HTTP REST** | `GET /api/videos?userId=` | 목록 조회 (VideoController 제공) |
| FE → BE | **HTTP REST** | `POST /api/videos` | 영상 메타 저장 |
| FE → BE | **HTTP REST** | `DELETE /api/videos/{id}` | 삭제 |
| FE | - | /uploads/... | 썸네일/영상 URL (Nginx 정적) |

- **FE**: RobotContext (videos, deleteVideo) - 현재 GET /videos 호출 없음, addTestVideo는 로컬 더미만 추가
- **BE**: VideoController.java
- **비고**: 실제 로봇이 감지 시 BE로 POST하여 저장하는 연동 필요

---

### 3.10 로그 (순찰 로그)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → BE | **HTTP REST** | `GET /api/logs?userId=` | 목록 조회 |
| FE → BE | **HTTP REST** | `POST /api/logs` | 로그 생성 |
| FE → BE | **HTTP REST** | `DELETE /api/logs/{id}` | 삭제 |

- **FE**: RobotContext (useQuery logs, addTestLog, deleteLog)
- **BE**: LogController.java
- **용도**: 로봇 순찰 기록, 로봇→BE POST 연동 시 자동 저장

---

### 3.11 알림

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE | **로컬** | localStorage `notifications_{userId}` | 클라이언트 알림 저장 |
| 로봇 → BE | **HTTP REST** | `POST /api/user/notifications` | 로봇 이벤트 알림 저장 (규격) |
| FE → BE | **HTTP REST** | `GET /api/user/notifications?userId=` | 알림 목록 조회 |

- **FE**: NotificationContext - addNotification()은 로컬 state + localStorage만 사용
- **BE**: NotificationController - 로봇이 POST로 알림 저장 가능
- **비고**: 현재 FE 알림은 RobotContext 등에서 addNotification() 호출 시 토스트 + 로컬 저장만 수행

---

### 3.12 설정 (프로필/비밀번호)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| FE → BE | **HTTP REST** | `PUT /api/user/{id}/profile` | 이름 수정 |
| FE → BE | **HTTP REST** | `POST /api/user/verify-password` | 비밀번호 확인 |
| FE → BE | **HTTP REST** | `PUT /api/user/{id}/password` | 비밀번호 변경 |

- **FE**: AuthContext (updateProfile, changePassword)
- **BE**: UserController.java

---

### 3.13 고양이 상태 (cat_state) - MQTT

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| 로봇 → Mosquitto | **MQTT** | `robot/{userId}/cat_state` 발행 | 감지된 고양이 상태 |
| BE | MqttService | `/topic/robot/{userId}/cat_state` STOMP 전달 | |

- **BE**: MqttService - topic.endsWith("/cat_state") 시 STOMP 브로드캐스트
- **용도**: 로봇 AI가 고양이 감지/상태 변경 시 실시간 전달 (FE STOMP 구독 시 활용 가능)

---

### 3.14 ROS2 로봇 데이터 (대안 경로)

| 구분 | 통신 방식 | 경로/토픽 | 설명 |
|------|-----------|-----------|------|
| 로봇 → BE | **WebSocket** | `wss://.../ros2/vehicle/status` | JSON 전송 |
| BE | Ros2WebSocketHandler | messagingTemplate → /sub/robot/{userId}/status | STOMP 브로드캐스트 |

- **로봇**: real_robot_simulator.py - ws://.../ros2/vehicle/status 로 규격서 기반 JSON 전송
- **BE**: Ros2WebSocketHandler - 수신 후 STOMP로 웹에 전달
- **비고**: 현재 FE는 MQTT `robot/{userId}/status` 직접 구독 사용, 이 WebSocket 경로는 대안/시뮬레이터용

---

## 4. 통신 방식 요약표

| 기능 | FE↔BE | BE↔로봇 | FE↔로봇 |
|------|--------|----------|----------|
| 인증 | HTTP REST | - | - |
| 로봇 초기 상태 | HTTP REST | - | - |
| 수동 조작 | - | - | **MQTT** (직접) |
| 로봇 상태 수신 | - | MQTT (BE도 구독) | **MQTT** (직접) |
| TTS | HTTP REST | **MQTT** | - |
| 목소리 학습 | HTTP REST | - | - |
| 비디오 스트리밍 | **WebSocket(STOMP)** 시그널링 | - | **WebRTC P2P** |
| 고양이 관리 | HTTP REST | - | - |
| 영상 갤러리 | HTTP REST | - | - |
| 로그 | HTTP REST | - | - |
| 알림 | HTTP REST (조회/저장) | - | - |
| 설정 | HTTP REST | - | - |
| cat_state | - | MQTT | - |

---

## 5. MQTT 토픽 정리

| 토픽 | 발행 | 구독 | 용도 |
|------|------|------|------|
| `robot/{userId}/control` | FE, BE(TTS) | 로봇(mqtt_bridge) | 이동/TTS/모드/비상정지 명령 |
| `robot/{userId}/status` | 로봇 | FE, BE | 로봇 상태(pose, battery, mode) |
| `robot/{userId}/cat_state` | 로봇 | BE | 고양이 감지 상태 |
| `robot/{userId}/pose` | 로봇 | BE | 위치 좌표 (status와 유사) |

---

## 6. robot_test 폴더 역할

| 파일 | 역할 |
|------|------|
| mqtt_bridge.py | ROS2 ↔ MQTT 브릿지. /amcl_pose → status 발행, control 구독 → /cmd_vel_joy 발행 |
| robot_webrtc.py | ROS /front_cam/compressed 구독 → WebRTC Offer/Answer (STOMP) → 실시간 영상 스트리밍 |
| real_robot_simulator.py | 로컬 시뮬레이터. WebSocket /ros2/vehicle/status, /signal WebRTC 시그널링 |
| homing.py | 자동 모드 시 homing 프로세스 (mqtt_bridge에서 subprocess로 실행) |

---

*작성일: 2026-01-27*
