# Raspberry Pi에서 Gateway 실행 가이드

Pi에서 **venv 사용**으로 실행하는 방법입니다.

---

## 1. 빠른 실행 (권장)

```bash
cd /home/pi/pi_gateway   # 실제 경로에 맞게
chmod +x scripts/run_gateway.sh
./scripts/run_gateway.sh
```

- venv 없으면 자동 생성 (`.venv`)
- `requirements.txt` 자동 설치
- venv Python으로 `python3 -m src.main` 실행

---

## 2. 수동으로 venv 켠 뒤 실행

```bash
cd /home/pi/pi_gateway

# venv 생성 (최초 1회)
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치 (최초 1회, 또는 requirements 변경 시)
pip install -r requirements.txt

# 실행 (모듈로 실행 시 PYTHONPATH 불필요)
python3 -m src.main
```

---

## 3. Pi에서 자주 나오는 문제

### 3.1 `python3 -m venv` 실패

```
The virtual environment was not created successfully ...
```

**해결:** `venv` 패키지 설치 후 다시 시도

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv .venv
```

### 3.2 `pip install` 실패 (SSL 등)

```bash
# pip 업그레이드 후 재시도
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 `Permission denied: ./scripts/run_gateway.sh`

```bash
chmod +x scripts/run_gateway.sh
./scripts/run_gateway.sh
```

### 3.4 `ModuleNotFoundError: No module named 'src'`

**원인:** `python3 src/main.py`로 실행할 때 프로젝트 루트가 path에 없음.

**해결:** 프로젝트 루트에서 **모듈로** 실행:

```bash
cd pi_gateway
python3 -m src.main
```

또는 `PYTHONPATH` 설정 후 스크립트 실행:

```bash
export PYTHONPATH="$(pwd):$(pwd)/src:$PYTHONPATH"
python3 src/main.py
```

`run_gateway.sh`는 `python3 -m src.main`으로 실행하므로 해당 오류 없음.

### 3.5 `IndexError: wait set index too big` (ROS 모드)

ROS 모드에서 노드 다수 사용 시 발생할 수 있는 rclpy 이슈. **단일 executor** 사용으로 완화됨.  
**웹 ↔ Gateway만** 테스트할 때는 ROS 없이 데모 모드로 실행:

```bash
# DEMO_MODE=1 (기본값): ROS 비사용, WebSocket/REST만 동작
python3 -m src.main
# 또는
./scripts/run_gateway.sh
```

실기기(UART+ROS) 연동이 꼭 필요할 때만 `DEMO_MODE=0`, `ROS_ENABLED=1` 사용.

### 3.6 UART 사용 시 (`/dev/ttyAMA0`, `/dev/ttyUSB0` 등)

```bash
# 장치 확인 (GPIO 직결: ttyAMA0/serial0, USB-UART: ttyUSB0)
ls -l /dev/ttyAMA0 /dev/ttyUSB* /dev/serial* 2>/dev/null || true

# params.yaml 에서 uart.enabled: true 또는
export UART_ENABLED=1
export UART_PORT=/dev/ttyAMA0   # GPIO 직결. 또는 /dev/serial0, /dev/ttyUSB0

./scripts/run_gateway.sh
```

---

## 4. 데모 vs 실기기

| 모드 | 설명 | 실행 |
|------|------|------|
| **데모** | UART/ROS 없이 Web·WebSocket·REST만 동작 (가짜 텔레메트리) | `./scripts/run_gateway.sh` 또는 `python3 -m src.main` (기본) |
| **실기기** | UART 연결, ROS 사용 | `params.yaml` 설정 + `UART_ENABLED=1` 등 환경변수 후 `./scripts/run_gateway.sh` |

**웹 ↔ Gateway 연결만** 확인할 때는 **데모 모드**로 실행하면 됨. `/health`, `/ws/teleop`, `/ws/telemetry` 등 동작함.

---

## 5. 실행 확인

```bash
curl -s http://localhost:8000/health
# {"ok": true, ...} 이 나오면 정상
```

---

## 요약

- **실행:** `./scripts/run_gateway.sh` (venv 자동 사용)
- **venv 수동:** `source .venv/bin/activate` → `pip install -r requirements.txt` → `python3 -m src.main`
- **문제 시:** `python3-venv`, `python3-pip` 설치 확인, `PYTHONPATH` 확인
