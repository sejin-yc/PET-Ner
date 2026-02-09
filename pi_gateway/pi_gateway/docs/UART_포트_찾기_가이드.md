# UART 포트 찾기 가이드

시리얼 포트를 찾지 못할 때 확인하는 방법입니다.

---

## 🔍 포트 확인 명령어

### 1. 모든 시리얼 포트 확인

```bash
# 모든 시리얼 포트 나열
ls -la /dev/serial* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# 또는
ls -la /dev/tty* | grep -E "serial|USB|ACM"
```

### 2. dmesg로 최근 연결 확인

```bash
# 최근 USB/시리얼 연결 로그 확인
dmesg | tail -30 | grep -i "tty\|serial\|usb"

# 또는 전체 로그에서 찾기
dmesg | grep -i "tty\|serial"
```

### 3. 시스템 정보 확인

```bash
# USB 장치 확인
lsusb

# 시리얼 포트 상세 정보
dmesg | grep -i "tty"
```

---

## 📋 일반적인 포트 위치

### Raspberry Pi
- GPIO 직결: `/dev/serial0` 또는 `/dev/ttyAMA0`
- USB-UART 동글: `/dev/ttyUSB0`, `/dev/ttyUSB1`, ...

### 일반 Linux
- USB-UART: `/dev/ttyUSB0`, `/dev/ttyUSB1`, ...
- USB-Serial: `/dev/ttyACM0`, `/dev/ttyACM1`, ...

---

## 🛠️ 문제 해결

### 포트가 안 보일 때

1. **STM32가 연결되어 있는지 확인**
   - USB 케이블 연결 확인
   - 전원 확인

2. **드라이버 확인**
   ```bash
   # USB 장치 확인
   lsusb
   
   # 커널 모듈 확인
   lsmod | grep usbserial
   ```

3. **권한 확인**
   ```bash
   # 포트 권한 확인
   ls -la /dev/ttyUSB* /dev/ttyACM*
   
   # 권한 부여 (포트를 찾은 후)
   sudo chmod 666 /dev/ttyUSB0
   ```

4. **포트 사용 중 확인**
   ```bash
   # 포트 사용 중인 프로세스 확인
   sudo lsof /dev/ttyUSB0
   sudo fuser /dev/ttyUSB0
   ```

---

## 💡 빠른 확인 스크립트

```bash
#!/bin/bash
echo "=== 시리얼 포트 찾기 ==="
echo ""
echo "1. /dev/serial* 포트:"
ls -la /dev/serial* 2>/dev/null || echo "  없음"
echo ""
echo "2. /dev/ttyUSB* 포트:"
ls -la /dev/ttyUSB* 2>/dev/null || echo "  없음"
echo ""
echo "3. /dev/ttyACM* 포트:"
ls -la /dev/ttyACM* 2>/dev/null || echo "  없음"
echo ""
echo "4. 최근 USB 연결 로그:"
dmesg | tail -20 | grep -i "tty\|usb\|serial" || echo "  없음"
```

---

## 📝 참고

- `/dev/serial0`은 심볼릭 링크일 수 있음
- 실제 포트는 `/dev/ttyAMA0` 또는 `/dev/ttyS0`일 수 있음
- USB-UART 동글 사용 시 `/dev/ttyUSB0` 확인
