# UART 터미널 명령어로 확인 (Python 없이)

순수 리눅스 명령어만으로 UART 통신을 확인하는 방법입니다.

---

## 🚀 가장 빠른 방법

### 1. hexdump로 raw 데이터 확인

```bash
# 5초간 데이터 읽기
timeout 5 hexdump -C /dev/serial0

# 실시간 확인 (Ctrl+C로 종료)
sudo hexdump -C /dev/serial0
```

**출력 예시:**
```
00000000  aa 55 81 05 88 13 52 00  00                       |.U.....R..|
```

- `aa 55`: 프레임 시작 (STX)
- `81`: MSG_ID (배터리=0x81, 엔코더=0x82, IMU=0x83)
- `05`: 데이터 길이
- 나머지: 실제 데이터 + 체크섬

---

### 2. od 명령어로 확인

```bash
# 5초간 데이터 읽기
timeout 5 od -An -tx1 /dev/serial0

# 실시간 확인
sudo od -An -tx1 /dev/serial0
```

**출력 예시:**
```
aa 55 81 05 88 13 52 00 00
```

---

### 3. cat으로 raw 바이트 확인

```bash
# 5초간 데이터 읽기
timeout 5 cat /dev/serial0 | od -An -tx1

# 실시간 확인
sudo cat /dev/serial0 | od -An -tx1
```

---

## 📋 포트 확인 명령어

### 사용 가능한 시리얼 포트 찾기

```bash
# 모든 시리얼 포트 확인
ls -la /dev/serial* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# 특정 포트 상세 정보
ls -l /dev/serial0

# 포트 권한 확인
stat /dev/serial0
```

---

## 🔍 데이터 해석

### 프레임 구조

```
[STX1] [STX2] [MSG_ID] [LENGTH] [PAYLOAD...] [CHECKSUM]
 0xAA   0x55    1바이트   1바이트    N바이트      1바이트
```

### MSG_ID 종류

- `0x81` (129): 배터리 데이터
- `0x82` (130): 엔코더 데이터 (fl, fr, rl, rr)
- `0x83` (131): IMU 데이터 (yaw, pitch, roll, acc)

### 예시 해석

```
aa 55 81 05 88 13 52 00 00
│  │  │  │  │  │  │  │  │
│  │  │  │  │  │  │  │  └─ CHECKSUM
│  │  │  │  │  │  │  └─ charging (0)
│  │  │  │  │  │  └─ soc (82 = 0x52)
│  │  │  │  │  └─ vbat_mV 상위바이트 (0x13 = 19)
│  │  │  │  └─ vbat_mV 하위바이트 (0x88 = 136)
│  │  │  │     → vbat = 0x1388 = 5000mV = 5.0V
│  │  │  └─ LENGTH (5바이트)
│  │  └─ MSG_ID (0x81 = 배터리)
│  └─ STX2 (0x55)
└─ STX1 (0xAA)
```

---

## 🛠️ 고급 명령어

### 1. minicom (시리얼 터미널)

```bash
# 설치
sudo apt install minicom

# 실행
sudo minicom -D /dev/serial0 -b 115200

# 종료: Ctrl+A → X → Y
```

### 2. screen (시리얼 터미널)

```bash
# 실행
sudo screen /dev/serial0 115200

# 종료: Ctrl+A → K → Y
```

### 3. stty로 포트 설정 확인

```bash
# 포트 설정 확인
stty -F /dev/serial0 -a

# 포트 설정 변경
sudo stty -F /dev/serial0 115200 cs8 -cstopb -parenb
```

---

## ⚠️ 문제 해결

### 권한 오류

```bash
# 권한 부여
sudo chmod 666 /dev/serial0

# 또는 사용자를 dialout 그룹에 추가
sudo usermod -aG dialout $USER
# 로그아웃 후 다시 로그인 필요
```

### 포트가 사용 중

```bash
# 사용 중인 프로세스 확인
sudo lsof /dev/serial0

# 또는
sudo fuser /dev/serial0

# 프로세스 종료
sudo kill -9 <PID>
```

### 데이터가 안 보임

```bash
# 포트 존재 확인
ls -la /dev/serial0

# 최근 연결 로그 확인
dmesg | tail -20 | grep -i serial

# 포트 상태 확인
sudo stty -F /dev/serial0 -a
```

---

## 💡 추천 명령어 조합

### 빠른 확인 (5초)

```bash
timeout 5 hexdump -C /dev/serial0
```

### 실시간 모니터링

```bash
sudo hexdump -C /dev/serial0 | grep -E "aa 55"
```

### 특정 MSG_ID만 필터링

```bash
sudo hexdump -C /dev/serial0 | grep "aa 55 81"  # 배터리만
sudo hexdump -C /dev/serial0 | grep "aa 55 82"  # 엔코더만
sudo hexdump -C /dev/serial0 | grep "aa 55 83"  # IMU만
```

---

## 📝 요약

| 명령어 | 용도 | 예시 |
|--------|------|------|
| `hexdump -C` | hex + ASCII 확인 | `hexdump -C /dev/serial0` |
| `od -An -tx1` | hex만 확인 | `od -An -tx1 /dev/serial0` |
| `cat` | raw 바이트 읽기 | `cat /dev/serial0` |
| `minicom` | 시리얼 터미널 | `minicom -D /dev/serial0 -b 115200` |
| `screen` | 시리얼 터미널 | `screen /dev/serial0 115200` |

**가장 추천**: `sudo hexdump -C /dev/serial0`
