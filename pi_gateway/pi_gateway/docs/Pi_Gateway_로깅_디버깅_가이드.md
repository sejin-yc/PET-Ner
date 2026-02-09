# Pi Gateway 로깅·디버깅 가이드 (현업 방식)

Pi Gateway는 **Python `logging`** 을 사용하며, **LOG_LEVEL** 환경변수로 레벨을 조절합니다. stdout으로 출력되므로 Docker/K8s에서 수집·검색할 수 있습니다.

---

## 로깅 규칙 (팀 공통)

- **기본 출력**: stdout (Docker/K8s 수집용).
- **기본 레벨**: INFO. 개발 시에만 DEBUG.
- **모듈별 logger**: `logging.getLogger(__name__)` 사용 (패키지명 기준 자동 일치).
- **예외 로그**: `except Exception:` 블록 안에서는 **무조건 `log.exception()`** 사용 (스택트레이스 포함). 단순 실패 처리만이면 `log.warning()` / `log.error()`.
- **로그 폭주 방지**: 패킷·요청 단위 상세 로그는 **기본 OFF**. 필요 시에만 `UART_DEBUG_TX/RX=1`, `GATEWAY_DEBUG=1` 사용. 상시는 `UART_LINK_STATS=1`, `GATEWAY_DEBUG_SUMMARY=1` 로 주기 요약만.

---

## 1. 로그 레벨 (LOG_LEVEL)

| 값 | 용도 |
|----|------|
| **DEBUG** | 개발 시 상세 로그 (WS/TELEOP 키 입력, UART TX/RX hex 등) |
| **INFO** | 기본. 시작/연결/주기 요약 등 |
| **WARNING** | 에러·실패만 |
| **ERROR** | 심각한 오류만 |

- **파싱**: 대소문자 무관 (예: `LOG_LEVEL=info` 가능). `VERBOSE`, `TRACE` 등 비표준 값이면 **경고 후 INFO**로 폴백.
- **중복 설정 방지**: `configure_logging()` 은 `force=True` 로 한 번만 적용되어, 로그가 2번 찍히는 현상을 막음.

**사용 예**

```bash
# 개발 시 상세 로그
LOG_LEVEL=DEBUG ./scripts/run_gateway.sh

# 운영 시 기본
LOG_LEVEL=INFO ./scripts/run_gateway.sh
```

**로그 포맷**

```
2025-01-27 12:00:00 [INFO] pi_gateway.main: starting uvicorn on 0.0.0.0:8000 (MODE=ROS, ...)
2025-01-27 12:00:01 [INFO] pi_gateway.uart: OPEN /dev/ttyAMA0 @ 115200
```

---

## 2. API·상태 확인 (로그 없이)

### GET /debug/state

내부 상태만 조회. **로그를 찍지 않습니다.**

```bash
curl -s http://localhost:8000/debug/state | python3 -m json.tool
```

### GET /metrics (Prometheus)

요청 횟수·요청 지연 시간 메트릭. Grafana/Prometheus로 수집 가능.

```bash
curl -s http://localhost:8000/metrics
```

**현재 제공**

- `gateway_requests_total` — method·path별 요청 횟수 (counter)
- `gateway_request_duration_seconds_sum` / `gateway_request_duration_seconds_count` — API 지연 (summary)

**추가 예정**

- `uart_tx_total`, `uart_rx_total` — UART TX/RX 프레임 수
- `uart_rx_crc_errors_total` — UART CRC 에러 수

예시:

```
# HELP gateway_requests_total Total HTTP requests by method and path
# TYPE gateway_requests_total counter
gateway_requests_total{method="GET",path="/robot/health"} 1234
gateway_request_duration_seconds_sum{method="GET",path="/robot/health"} 12.345
gateway_request_duration_seconds_count{method="GET",path="/robot/health"} 1234
```

---

## 3. API 호출 디버깅 (선택)

| 환경변수 | 동작 | 터미널 |
|----------|------|--------|
| **GATEWAY_DEBUG_SUMMARY=1** | 10초마다 API 호출 횟수 한 줄 | 깔끔 |
| **GATEWAY_DEBUG=1** | 요청/응답마다 로그 | 복잡 |

```bash
GATEWAY_DEBUG_SUMMARY=1 ./scripts/run_gateway.sh
# 10초마다: [INFO] pi_gateway.web: 10s: GET /robot/health 50, GET /telemetry/latest 50
```

---

## 4. UART (Pi↔STM) 디버깅 (선택)

| 환경변수 | 동작 | 터미널 |
|----------|------|--------|
| **UART_LINK_STATS=1** | 10초마다 TX/RX 요약 한 줄 | 깔끔 |
| **UART_DEBUG_TX=1** | 전송마다 hex 로그 | 복잡 |
| **UART_DEBUG_RX=1** | 수신마다 hex 로그 | 복잡 |

**패킷 단위 상세 로그는 위 TX/RX 옵션 켤 때만** 사용. 상시에는 `UART_LINK_STATS=1` 로 10초 요약만 권장.

```bash
UART_LINK_STATS=1 UART_ENABLED=1 ./scripts/run_gateway.sh
# 10초마다: [INFO] pi_gateway.uart: 10s: TX=200 RX=180 last_rx=0.2s ago
```

---

## 5. Docker 예시

```bash
sudo docker run -it --rm --name pi_gateway \
  --network host \
  --device /dev/ttyAMA0:/dev/ttyAMA0 \
  -e LOG_LEVEL=INFO \
  -e GATEWAY_DEBUG_SUMMARY=1 \
  -e UART_LINK_STATS=1 \
  -e UART_ENABLED=1 \
  -e UART_PORT=/dev/ttyAMA0 \
  -e ROS_ENABLED=1 \
  -v /home/c203/pi_gateway:/ws/pi_gateway \
  -w /ws/pi_gateway \
  ros:humble-ros-base \
  bash -lc "source /opt/ros/humble/setup.bash && pip install -r requirements.txt && python3 -m src.main"
```

- **LOG_LEVEL=DEBUG** 로 상세 로그 확인 가능.
- **/metrics** 는 Prometheus가 같은 네트워크에서 스크래핑하면 됨.
- uvicorn access/error 로그도 **동일 포맷·레벨**로 맞춰 두어 운영에서 한 줄 포맷으로 통일됨.

---

## 6. 요약

| 목적 | 방법 |
|------|------|
| 로그 양 조절 | **LOG_LEVEL** (DEBUG/INFO/WARNING/ERROR) |
| 상태만 확인 | **GET /debug/state** |
| 요청 통계·대시보드 | **GET /metrics** (Prometheus) |
| API 호출 흐름 (가벼움) | **GATEWAY_DEBUG_SUMMARY=1** |
| Pi↔STM 통신 (가벼움) | **UART_LINK_STATS=1** |
| 상세 디버깅 | GATEWAY_DEBUG=1, UART_DEBUG_TX/RX=1 (필요 시만) |
