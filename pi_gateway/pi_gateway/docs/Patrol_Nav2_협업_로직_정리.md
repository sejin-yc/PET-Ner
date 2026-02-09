# Patrol 로직 정리 - Nav2 팀 협업용

**목적**: Pi Gateway 측 Patrol 구현 로직을 정리하고, Nav2 팀이 어떤 토픽을 발행/구독해야 하는지 명시

---

## 1. 역할 분담 (한 줄 요약)

| 담당 | 하는 일 |
|------|----------|
| **Nav2** | 경로 이동 + **waypoint 도착 시** `patrol/waypoint_reached` 발행, 아루코 정렬 완료 시 `patrol/aruco_aligned` 발행 |
| **Pi Gateway** | 위 토픽 **구독** → waypoint_type에 따라 **액션 실행**(변치우기/급식/급수) → 완료 시 `patrol/action_complete` **발행** |
| **이동 명령** | Nav2가 **표준 토픽 `/cmd_vel`** 발행 → Pi Gateway CmdVelMux가 수신 → UART로 전달 |

**Pi Gateway는 이동 경로를 만들지 않습니다.** Nav2가 경로를 만들고 `/cmd_vel`로 이동시키고, waypoint에 도착하면 신호만 보내줍니다.

---

## 2. 전체 흐름 (순찰 한 바퀴)

```
[웹/스케줄] "자동 모드" 선택 (또는 PatrolScheduler가 주기적으로 "auto" 발행)
      │
      ▼
[Pi Gateway] control_mode = "auto" 수신
      │
      ├─ CmdVelMux: mode=auto → /cmd_vel( Nav2 ) 값 사용
      └─ PatrolLoop: 순찰 시작 이벤트 (주간 순찰 시간용)

[Nav2] 순찰 경로 실행
      │
      ├─ /cmd_vel 발행 (로봇이 waypoint 따라 이동)
      └─ waypoint 도착 시 → patrol/waypoint_reached 발행
                │
                ▼
[Pi Gateway PatrolLoop] patrol/waypoint_reached 구독
      │
      ├─ waypoint_type 이 litter_clean / water / feed → 아루코 필요 시 "아루코 정렬 대기"
      └─ 아루코 불필요(general 등) → 바로 execute_action()
                │
[Nav2] 아루코 마커 정렬 완료 시 (필요한 waypoint만) → patrol/aruco_aligned 발행
                │
                ▼
[Pi Gateway] patrol/aruco_aligned 수신 → execute_action(waypoint_type, waypoint_id)
      │
      ├─ litter_clean → UART arm/start (변 치우기)
      ├─ feed → feed/request 발행 (젯슨) → feed/amount 수신 후 UART
      └─ water → UART arm/water (급수)
                │
                ▼
[Pi Gateway] 액션 완료 시 → patrol/action_complete 발행
      │
      ▼
[Nav2] patrol/action_complete 구독 → 다음 waypoint로 이동 (또는 순찰 종료)

… 반복 …

[웹/사용자] "수동 모드" 선택
      │
      ▼
[Pi Gateway] control_mode = "teleop" 수신
      │
      ├─ CmdVelMux: mode=teleop → cmd_vel_teleop( 웹 ) 값 사용
      └─ PatrolLoop: 순찰 종료 이벤트 (duration 계산 → POST /api/logs)
```

---

## 3. Pi Gateway 쪽 구성 요소

### 3.1 CmdVelMux (이동 명령 선택)

- **구독**: `cmd_vel_teleop` (웹), `/cmd_vel` (Nav2), `control_mode`, `control_estop`
- **발행**: `cmd_vel_out` (실제로 UART 쪽에 나가는 값)
- **로직**:
  - `control_mode == "auto"` → **Nav2가 발행한 `/cmd_vel`** 사용 (최근 0.5초 이내 값만 유효, 없으면 정지)
  - `control_mode == "teleop"` → **웹에서 오는 cmd_vel_teleop** 사용
- **정리**: **이동은 전부 Nav2가 `/cmd_vel`로 제어.** Pi Gateway는 그걸 그대로 UART로 넘기기만 함.

### 3.2 PatrolLoop (waypoint ↔ 액션 연결)

- **구독**:
  - `control_mode` (auto/teleop) → 순찰 시작/종료, 주간 순찰 시간 계산
  - `patrol/waypoint_reached` (Nav2 → Pi Gateway)
  - `patrol/aruco_aligned` (Nav2 → Pi Gateway)
- **발행**:
  - `patrol/action_complete` (Pi Gateway → Nav2) — 액션 끝났을 때만
- **로직 요약**:
  1. **waypoint_reached** 수신  
     - `waypoint_type` 이 `litter_clean`, `water`, `feed` → 아루코 필요로 간주 → **아루코 정렬 대기** (실제 액션은 하지 않음)  
     - 그 외 → 아루코 불필요로 간주 → **바로** `execute_action(waypoint_type, waypoint_id)` 호출
  2. **aruco_aligned** 수신  
     - 대기 중이었으면 그때 `execute_action(...)` 호출 (변치우기/급수 등)
  3. **execute_action**  
     - `PatrolActionScheduler`가 UART/젯슨 쪽 호출 (변치우기, 급식, 급수)
  4. 액션 끝나면 **항상** `patrol/action_complete` 발행  
     - Nav2는 이걸 보고 다음 waypoint로 진행하거나 순찰 종료

### 3.3 PatrolActionScheduler (실제 액션 실행)

- **Nav2 신호 사용 시** (`use_nav2_signals=True`, 기본값):  
  - waypoint/aruco 신호로만 동작.  
  - `tick()`에서는 아무 것도 안 함 (Nav2 없이 “매 순찰마다 자동 실행” 로직은 꺼져 있음).
- **실행 액션**:
  - `litter_clean` → UART `arm/start` (변 치우기)
  - `feed` → `feed/request` 발행 → 젯슨 `feed/amount` 수신 → UART feed
  - `water` → UART `arm/water` (급수)
- 액션 완료 시 `_publish_action_complete` 호출 → **patrol/action_complete** 발행.

### 3.4 PatrolScheduler (주기 순찰, 선택)

- **역할**: 설정된 간격(예: 4시간)마다 `control_mode`를 "auto"로 한 번 발행해서 순찰 시작.
- **Nav2 경로 시작**: 현재는 **하지 않음** (nav2_client는 TODO).  
  → “순찰 시작”은 **웹에서 자동 모드 선택** 또는 **Nav2 팀이 auto 시 어떤 goal을 보낼지** 정하면 됨.

---

## 4. Nav2 팀이 해야 할 일 (체크리스트)

### 4.1 반드시 필요한 것

| # | 항목 | 설명 |
|---|------|------|
| 1 | **이동 명령** | 순찰 경로대로 **`/cmd_vel`** (geometry_msgs/Twist) 발행. Pi Gateway가 구독해서 그대로 로봇에 전달함. |
| 2 | **waypoint 도착 알림** | waypoint에 도착했을 때 **`patrol/waypoint_reached`** 발행 (std_msgs/String, JSON). |
| 3 | **action_complete 대기** | **`patrol/action_complete`** 구독. 이 메시지 올 때까지 해당 waypoint에서 대기했다가, 수신 후 다음 waypoint로 진행. |

### 4.2 waypoint_reached 메시지 형식 (std_msgs/String, JSON)

```json
{
  "waypoint_id": "litter_zone_1",
  "waypoint_type": "litter_clean",
  "timestamp": 1737700000.123
}
```

- **waypoint_id**: 임의 문자열 (같은 ID를 나중에 action_complete에 넣어주면 됨).
- **waypoint_type**:  
  - `litter_clean` → 변 치우기 (아루코 정렬 필요로 간주)  
  - `water` → 급수 (아루코 정렬 필요로 간주)  
  - `feed` → 급식 (아루코 필요 시 정렬 후 실행)  
  - `general` 등 → Pi Gateway가 액션 없이 바로 action_complete만 보낼 수 있도록 하거나, Nav2가 해당 waypoint에서는 waypoint_reached를 안 보내도 됨.

### 4.3 아루코 사용 시 (변 치우기/급수 등)

- 아루코 마커 정렬까지 끝났을 때 **`patrol/aruco_aligned`** 발행 (std_msgs/String, JSON):

```json
{
  "aruco_id": 10,
  "waypoint_id": "litter_zone_1",
  "waypoint_type": "litter_clean",
  "timestamp": 1737700000.456
}
```

- Pi Gateway는 **waypoint_reached** 수신 후 아루코 필요 타입이면 **aruco_aligned** 올 때까지 대기** → 그다음에 실제 액션 실행 → 끝나면 **action_complete** 발행.

### 4.4 action_complete (Pi Gateway → Nav2)

- Pi Gateway가 발행 (Nav2는 구독만 하면 됨):

```json
{
  "action_type": "litter_clean",
  "waypoint_id": "litter_zone_1",
  "status": "success",
  "timestamp": 1737700000.789
}
```

- **status**: `success` / `failed`  
- Nav2: `success`면 다음 waypoint로, `failed`면 재시도/스킵 등 정책에 따라 처리.

---

## 5. 토픽 정리 (Nav2 ↔ Pi Gateway)

| 토픽 | 방향 | 타입 | 발행/구독 |
|------|------|------|-----------|
| `/cmd_vel` | Nav2 → Pi Gateway | geometry_msgs/Twist | Nav2 발행, Pi Gateway(CmdVelMux) 구독 |
| `control_mode` | 웹/스케줄 → Pi Gateway | std_msgs/String | "auto" / "teleop" |
| `patrol/waypoint_reached` | Nav2 → Pi Gateway | std_msgs/String (JSON) | Nav2 발행, Pi Gateway(PatrolLoop) 구독 |
| `patrol/aruco_aligned` | Nav2 → Pi Gateway | std_msgs/String (JSON) | Nav2 발행, Pi Gateway(PatrolLoop) 구독 |
| `patrol/action_complete` | Pi Gateway → Nav2 | std_msgs/String (JSON) | Pi Gateway(PatrolLoop) 발행, Nav2 구독 |

---

## 6. Pi Gateway가 하지 않는 일

- 순찰 **경로/waypoint 목록** 생성 (Nav2 담당)
- **Goal 전송** (NavigateToPose 등) — 현재 PatrolScheduler의 nav2_client는 TODO
- **이동 명령 생성** — `/cmd_vel`은 Nav2가 생성, Pi Gateway는 전달만

---

## 7. Pi Gateway가 하는 일

- **control_mode**에 따라 **cmd_vel_teleop vs /cmd_vel** 선택해서 **cmd_vel_out**으로 내보내기 (UART까지 전달)
- **patrol/waypoint_reached**, **patrol/aruco_aligned** 수신 시 waypoint_type에 따라 **변치우기/급식/급수** 실행 (UART/젯슨 연동)
- 액션 끝날 때마다 **patrol/action_complete** 발행
- 순찰 시작/종료 시 **주간 순찰 시간** 계산 후 HTTP POST /api/logs (Backend)

---

## 8. 참고 문서

- `docs/Nav2_토픽_명세.md` — 토픽 필드 상세
- `docs/PatrolLoop_동작_방식_설명.md` — PatrolLoop 예전 패턴 설명 (현재는 Nav2 신호 기반만 사용)

---

*문의: Pi Gateway 담당자*
