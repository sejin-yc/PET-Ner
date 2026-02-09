# Patrol 로직 요약 — Nav2 팀 전달용

**목적**: “내가 구현한 Patrol 로직”을 한눈에 이해하고, Nav2 팀에 전달할 때 쓰는 요약 문서.

---

## 1. 한 줄 요약

- **이동**: Nav2가 **`/cmd_vel`** 만 발행하면 됨. Pi Gateway는 그걸 받아서 UART로 로봇에 전달만 함.
- **waypoint ↔ 액션**: Nav2가 waypoint 도착 시 **`patrol/waypoint_reached`**, 아루코 정렬 완료 시 **`patrol/aruco_aligned`** 발행 → Pi Gateway가 **변치우기/급식/급수** 실행 후 **`patrol/action_complete`** 발행 → Nav2는 이걸 보고 다음 waypoint로 진행.

---

## 2. Pi Gateway 쪽에서 “Patrol”이 하는 일 (역할만)

| 구성요소 | 하는 일 |
|----------|----------|
| **CmdVelMux** | `control_mode`에 따라 **cmd_vel_teleop**(웹) vs **/cmd_vel**(Nav2) 중 하나를 골라 **cmd_vel_out**으로 내보냄. **이동 명령 생성은 하지 않음.** |
| **PatrolLoop** | `patrol/waypoint_reached`, `patrol/aruco_aligned` **구독** → waypoint_type에 따라 액션 실행 → 끝나면 **`patrol/action_complete` 발행**. 순찰 시작/종료 시 **주간 순찰 시간** 계산 후 Backend에 POST. |
| **PatrolActionScheduler** | waypoint/aruco 신호 받으면 **실제 액션**(UART/젯슨) 실행: 변치우기, 급식, 급수. |
| **PatrolScheduler** | (선택) 주기적으로 `control_mode = "auto"` 발행해서 순찰 시작. **Nav2 goal 전송은 현재 TODO.** |

**정리**: Pi Gateway는 **경로/waypoint 목록을 만들지 않고**, **이동 명령도 만들지 않음.** Nav2가 경로 + `/cmd_vel` + waypoint/aruco 신호만 주면, Pi Gateway는 “어디서 무엇을 할지”만 받아서 액션 실행하고 `action_complete`로 알려줌.

---

## 3. Nav2 팀이 꼭 해야 할 것 (체크리스트)

| # | 항목 | 설명 |
|---|------|------|
| 1 | **이동 명령** | 순찰 경로대로 **`/cmd_vel`** (geometry_msgs/Twist) 발행. Pi Gateway(CmdVelMux)가 구독해서 그대로 로봇(UART)에 전달. |
| 2 | **waypoint 도착** | waypoint 도착 시 **`patrol/waypoint_reached`** 발행 (std_msgs/String, JSON). |
| 3 | **아루코 정렬 완료** | 변치우기/급수 등 아루코 필요한 지점에서 정렬 완료 시 **`patrol/aruco_aligned`** 발행 (같은 JSON 스타일). |
| 4 | **action_complete 대기** | **`patrol/action_complete`** 구독. 이 메시지 올 때까지 해당 waypoint에서 대기했다가, 수신 후 다음 waypoint로 진행. |

---

## 4. 토픽·메시지 형식 (복붙용)

### 4.1 Nav2 → Pi Gateway

**`patrol/waypoint_reached`** (std_msgs/String, JSON):

```json
{"waypoint_id": "litter_zone_1", "waypoint_type": "litter_clean", "timestamp": 1737700000.123}
```

- `waypoint_type`: `litter_clean` | `feed` | `water` | `general` (general은 액션 없이 통과 가능)

**`patrol/aruco_aligned`** (std_msgs/String, JSON):

```json
{"aruco_id": 10, "waypoint_id": "litter_zone_1", "waypoint_type": "litter_clean", "timestamp": 1737700000.456}
```

### 4.2 Pi Gateway → Nav2

**`patrol/action_complete`** (std_msgs/String, JSON) — Nav2는 **구독**만 하면 됨:

```json
{"action_type": "litter_clean", "waypoint_id": "litter_zone_1", "status": "success", "timestamp": 1737700000.789}
```

- `status`: `success` / `failed` → Nav2가 다음 진행/재시도/스킵 결정.

---

## 5. Pi Gateway 쪽 로직 (waypoint → 액션) 요약

1. **`patrol/waypoint_reached`** 수신  
   - `waypoint_type` 이 **litter_clean, water, feed** → 아루코 필요로 간주 → **아루코 정렬 대기** (이때는 아직 액션 실행 안 함).  
   - 그 외(**general** 등) → 아루코 불필요로 간주 → **바로** `execute_action(waypoint_type, waypoint_id)` 호출 (필요 시 바로 `action_complete` 발행).
2. **`patrol/aruco_aligned`** 수신  
   - 아루코 대기 중이었으면 그때 **execute_action(...)** 호출 (변치우기/급식/급수).
3. **execute_action**  
   - PatrolActionScheduler가 UART/젯슨으로 실제 동작 수행.
4. 액션 끝날 때마다 **`patrol/action_complete`** 발행  
   - Nav2는 이걸 보고 다음 waypoint로 진행.

---

## 6. 순찰 시작/종료와 “주간 순찰 시간”

- **시작**: `control_mode`가 **teleop → auto**로 바뀔 때 Pi Gateway가 “순찰 시작”으로 인식하고, Backend용 주간 순찰 시간 측정 시작.
- **종료**: **auto → teleop**으로 바뀔 때 “순찰 종료”로 인식하고, **duration(초)** 계산 후 **HTTP POST `/api/logs`** 로 전송 (프론트 “주간 순찰 시간” 등에 사용).
- **Nav2 입장**: `control_mode`는 웹/스케줄에서 제어. Nav2는 **`/cmd_vel` + waypoint/aruco/action_complete**만 맞추면 됨.

---

## 7. 참고 문서 (같은 repo)

- **역할·흐름 상세**: `Patrol_Nav2_협업_로직_정리.md`
- **토픽 필드·시나리오**: `Nav2_토픽_명세.md`
- **cmd_vel 구조**: `cmd_vel_토픽_구조_정리.md`
- **PatrolLoop 예전 패턴(참고용)**: `PatrolLoop_동작_방식_설명.md`

---

*Nav2 팀에 전달할 때 이 요약 + 위 참고 문서 링크 주면 됨.*
