#!/bin/bash
# UART 통신 확인 스크립트 (ROS 없이)

PORT="${1:-/dev/serial0}"
BAUD="${2:-115200}"

echo "=========================================="
echo "UART 통신 확인"
echo "=========================================="
echo "포트: $PORT"
echo "보드레이트: $BAUD"
echo "=========================================="
echo ""

# 포트 존재 확인
if [ ! -e "$PORT" ]; then
    echo "❌ 오류: $PORT 가 존재하지 않습니다."
    echo ""
    echo "사용 가능한 시리얼 포트 확인:"
    ls -la /dev/serial* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "시리얼 포트를 찾을 수 없습니다."
    exit 1
fi

# 권한 확인
if [ ! -r "$PORT" ] || [ ! -w "$PORT" ]; then
    echo "⚠️  경고: $PORT 에 읽기/쓰기 권한이 없습니다."
    echo "권한 부여: sudo chmod 666 $PORT"
    echo "또는 사용자를 dialout 그룹에 추가: sudo usermod -aG dialout \$USER"
    echo ""
fi

echo "UART 데이터 읽기 중... (Ctrl+C로 종료)"
echo "=========================================="
echo ""

# 방법 1: hexdump로 raw 데이터 확인
echo "방법 1: hexdump로 raw 데이터 확인"
echo "----------------------------------------"
timeout 5 hexdump -C "$PORT" 2>/dev/null || {
    echo ""
    echo "⚠️  hexdump 실패. 다른 방법 시도..."
    echo ""
}

# 방법 2: cat으로 raw 데이터 확인 (백그라운드로 실행)
echo "방법 2: cat으로 데이터 읽기 (5초)"
echo "----------------------------------------"
timeout 5 cat "$PORT" | hexdump -C || {
    echo ""
    echo "⚠️  cat 실패. 포트가 사용 중일 수 있습니다."
    echo ""
}

echo ""
echo "=========================================="
echo "추가 확인 방법:"
echo "=========================================="
echo ""
echo "1. 실시간 데이터 확인 (hexdump):"
echo "   sudo hexdump -C $PORT"
echo ""
echo "2. 실시간 데이터 확인 (od):"
echo "   sudo od -An -tx1 $PORT"
echo ""
echo "3. minicom 사용:"
echo "   sudo apt install minicom"
echo "   sudo minicom -D $PORT -b $BAUD"
echo ""
echo "4. screen 사용:"
echo "   sudo screen $PORT $BAUD"
echo ""
echo "5. Python으로 확인:"
echo "   python3 -c \"import serial; s=serial.Serial('$PORT', $BAUD, timeout=1); print(s.read(100).hex())\""
echo ""
