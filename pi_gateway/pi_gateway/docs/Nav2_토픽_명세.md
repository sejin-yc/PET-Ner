# Nav2 연동 토픽 명세

Nav2와 Pi Gateway 간 통신을 위한 ROS2 토픽 명세

---

## 📡 Nav2 → Pi Gateway (Nav2가 발행, Pi Gateway가 구독)

### 1. `patrol/waypoint_reached` - Waypoint 도착

**용도**: Nav2가 waypoint에 도착했을 때 발행

**토픽**: `patrol/waypoint_reached`  
**타입**: `std_msgs/String` (JSON)

**메시지 형식**:
```json
{
  "waypoint_id": "litter_zone_1",
  "waypoint_type": "litter_clean|feed|water|general",
  "timestamp": 1737700000.123
}
```

**필드 설명**:
- `waypoint_id`: waypoint 식별자 (문자열)
- `waypoint_type`: waypoint 타입 (액션 종류)
- `timestamp`: 도착 시각 (epoch time, 초)

**Pi Gateway 동작**:
- `waypoint_type`에 따라 해당 액션 실행
- `litter_clean` → 변 치우기 (`arm/start`, 아루코 마커 필요)
- `feed` → 급식 (`feed/request` 발행 → 젯슨이 `feed/amount` 발행 → UART 전송, 아루코 마커 선택적)
- `water` → 급수 (`arm/water`, 아루코 마커 필요)

---

### 2. `patrol/aruco_aligned` - 아루코 마커 정렬 완료

**용도**: Nav2가 아루코 마커를 인식하고 정밀 위치 조정을 완료했을 때 발행

**토픽**: `patrol/aruco_aligned`  
**타입**: `std_msgs/String` (JSON)

**메시지 형식**:
```json
{
  "aruco_id": 10,
  "waypoint_id": "litter_zone_1",
  "waypoint_type": "litter_clean|water",
  "timestamp": 1737700000.456
}
```

**필드 설명**:
- `aruco_id`: 아루코 마커 ID (정수)
- `waypoint_id`: 해당 waypoint 식별자
- `waypoint_type`: 액션 종류 (아루코 정렬이 필요한 액션만)
- `timestamp`: 정렬 완료 시각

**Pi Gateway 동작**:
- 아루코 정렬 완료 후 정밀 액션 실행
- `litter_clean` → 변 치우기 (`arm/start`)
- `water` → 급수 단계별 (`arm/water`)

---

## 📤 Pi Gateway → Nav2 (Pi Gateway가 발행, Nav2가 구독)

### 1. `patrol/action_complete` - 액션 완료

**용도**: Pi Gateway가 액션 실행을 완료했을 때 발행 (Nav2가 다음 waypoint로 이동 가능)

**토픽**: `patrol/action_complete`  
**타입**: `std_msgs/String` (JSON)

**메시지 형식**:
```json
{
  "action_type": "litter_clean|feed|water",
  "waypoint_id": "litter_zone_1",
  "status": "success|failed",
  "timestamp": 1737700000.789
}
```

**필드 설명**:
- `action_type`: 실행한 액션 종류
- `waypoint_id`: 해당 waypoint 식별자
- `status`: 액션 상태 (`success` 또는 `failed`)
- `timestamp`: 완료 시각

**Nav2 동작**:
- `status == "success"`면 다음 waypoint로 이동
- `status == "failed"`면 에러 처리 또는 재시도

---

## 🔄 통신 흐름 예시

### 시나리오: 변 치우기 (아루코 마커 필요)

```
1. [Nav2] waypoint 도착 → patrol/waypoint_reached 발행
   {"waypoint_id": "litter_zone_1", "waypoint_type": "litter_clean"}

2. [Pi Gateway] 신호 받음 → 아루코 정렬 대기

3. [Nav2] 아루코 마커 정렬 완료 → patrol/aruco_aligned 발행
   {"aruco_id": 10, "waypoint_id": "litter_zone_1", "waypoint_type": "litter_clean"}

4. [Pi Gateway] 변 치우기 시작 → arm/start (action_id=1) UART 전송

5. [젯슨] 로봇팔 제어 → 작업 완료 → arm/job_complete 발행

6. [Pi Gateway] 완료 신호 받음 → patrol/action_complete 발행
   {"action_type": "litter_clean", "waypoint_id": "litter_zone_1", "status": "success"}

7. [Nav2] 다음 waypoint로 이동
```

### 시나리오: 급식 (젯슨 연동, 아루코 마커 선택적)

```
1. [Nav2] waypoint 도착 → patrol/waypoint_reached 발행
   {"waypoint_id": "feed_zone", "waypoint_type": "feed"}

2. [Pi Gateway] 급식 요청 → feed/request 토픽 발행 (젯슨에 알림)

3. [젯슨] FEED_AI 모델로 사료량 계산 → feed/amount 토픽 발행 (level: 1~3)

4. [Pi Gateway] 사료량 수신 → feed (level=1~3) UART 전송

5. [STM32] 서보 제어 → 완료 → STATUS(0x84, 0x01) UART 전송

6. [Pi Gateway] 완료 신호 받음 → patrol/action_complete 발행
   {"action_type": "feed", "waypoint_id": "feed_zone", "status": "success"}

7. [Nav2] 다음 waypoint로 이동
```

**참고**: 급식도 아루코 마커가 필요할 수 있습니다. 필요한 경우 `patrol/aruco_aligned` 신호를 기다린 후 급식을 시작합니다.

---

## 📝 참고사항

1. **토픽 이름**: 표준 ROS2 네이밍 컨벤션 사용 (`patrol/...`)
2. **메시지 타입**: `std_msgs/String` 사용 (JSON 형식으로 유연하게 확장 가능)
3. **타임스탬프**: 모든 메시지에 `timestamp` 포함 (디버깅/로깅용)
4. **에러 처리**: `status == "failed"`일 때 Nav2가 재시도 또는 스킵 결정

---

## 🔧 구현 위치

- **Nav2**: `patrol/waypoint_reached`, `patrol/aruco_aligned` 발행
- **Pi Gateway**: 위 토픽 구독 → 액션 실행 → `patrol/action_complete` 발행

---

## ⚙️ 설정 방법

### Pi Gateway 설정

Pi Gateway는 **항상 Nav2 신호를 사용**합니다. 별도 설정 불필요.

- Nav2 토픽 구독: 항상 활성화
- 액션 실행: Nav2 신호 기반으로만 실행

---

## 📋 Nav2 체크리스트

- [ ] `patrol/waypoint_reached` 토픽 발행 (waypoint 도착 시)
- [ ] `patrol/aruco_aligned` 토픽 발행 (아루코 마커 정렬 완료 시, 필요한 경우만)
- [ ] `patrol/action_complete` 토픽 구독 (액션 완료 대기)
- [ ] 메시지 형식: `std_msgs/String` (JSON 문자열)
- [ ] JSON 필드: `waypoint_id`, `waypoint_type`, `timestamp` (필수)
