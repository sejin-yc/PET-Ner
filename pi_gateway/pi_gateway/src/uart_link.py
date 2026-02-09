from dataclasses import dataclass
import logging
import os
import time
import threading

try:
    import serial
except ImportError:
    serial = None

from src.uart_frames import FrameParser

log = logging.getLogger(__name__)


def _debug_tx() -> bool:
    return os.getenv("UART_DEBUG_TX", "").strip().lower() in ("1", "true", "yes", "y", "on")


def _debug_rx() -> bool:
    return os.getenv("UART_DEBUG_RX", "").strip().lower() in ("1", "true", "yes", "y", "on")


def _link_stats() -> bool:
    """10초마다 TX/RX 요약 한 줄만 (hex 없음)."""
    return os.getenv("UART_LINK_STATS", "").strip().lower() in ("1", "true", "yes", "y", "on")

@dataclass
class UartConfig:
    # GPIO 직결(UART0) 기준 기본 디바이스: /dev/serial0
    # (USB-UART 동글이면 /dev/ttyUSB0 형태가 될 수 있음)
    port: str = "/dev/serial0"
    baudrate: int = 115200
    enabled: bool = False
    rx_thread: bool = True

class UartLink:
    def __init__(self, cfg: UartConfig):
        self.cfg = cfg
        self.ser = None
        self._lock = threading.Lock()
        self._running = False
        self._rx_thread = None
        self._stats_thread = None
        self._parser = FrameParser()
        self._on_frame = None  # (msg_id, payload) 콜백
        self._tx_count = 0
        self._rx_count = 0
        self._last_rx_ts: float = 0.0
        self._stats_lock = threading.Lock()

    def set_on_frame(self, cb):
        self._on_frame = cb

    def open(self):
        if not self.cfg.enabled:
            log.info("DRY-RUN (enabled=false). TX will be logged.")
            return

        if serial is None:
            raise RuntimeError("pyserial not installed. pip install pyserial")

        self.ser = serial.Serial(self.cfg.port, self.cfg.baudrate, timeout=0.01)
        self._running = True
        log.info("OPEN %s @ %s", self.cfg.port, self.cfg.baudrate)

        if self.cfg.rx_thread:
            self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
            self._rx_thread.start()

        if _link_stats():
            self._stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
            self._stats_thread.start()
            log.info("UART_LINK_STATS=1: 10초마다 TX/RX 요약 한 줄 출력")

    def _stats_loop(self):
        interval = 10.0
        while self._running:
            time.sleep(interval)
            if not self._running:
                break
            with self._stats_lock:
                tx, rx = self._tx_count, self._rx_count
                last_rx = self._last_rx_ts
                self._tx_count = 0
                self._rx_count = 0
            ago = (time.time() - last_rx) if last_rx else None
            ago_str = f"{ago:.1f}s ago" if ago is not None else "never"
            log.info("10s: TX=%s RX=%s last_rx=%s", tx, rx, ago_str)

    def close(self):
        self._running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        log.info("CLOSED")

    def send(self, frame: bytes):
        if not self.cfg.enabled:
            log.debug("SEND %s", frame.hex())
            return

        if not self.ser:
            raise RuntimeError("UART not opened")

        with self._lock:
            self.ser.write(frame)
        if _link_stats():
            with self._stats_lock:
                self._tx_count += 1
        if _debug_tx():
            log.debug("TX %s", frame.hex())

    def _rx_loop(self):
        while self._running and self.ser:
            try:
                data = self.ser.read(256)
                if not data:
                    continue
                if _debug_rx():
                    log.debug("RX %s", data.hex())
                n_frames = 0
                for msg_id, payload in self._parser.feed(data):
                    n_frames += 1
                    if self._on_frame:
                        self._on_frame(msg_id, payload)
                if n_frames and _link_stats():
                    with self._stats_lock:
                        self._rx_count += n_frames
                        self._last_rx_ts = time.time()
            except Exception as e:
                log.warning("RX error: %s", e)
                time.sleep(0.1)
