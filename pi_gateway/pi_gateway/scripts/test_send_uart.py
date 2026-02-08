import os
import time
import argparse

from uart_link import UartLink, UartConfig
from uart_frames import make_cmd_vel_frame, make_estop_frame, make_feed_frame

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=os.getenv("UART_PORT", "/dev/ttyUSB0"))
    ap.add_argument("--baud", type=int, default=int(os.getenv("UART_BAUD", "115200")))
    ap.add_argument("--enabled", action="store_true")
    ap.add_argument("--vx", type=float, default=0.0)
    ap.add_argument("--vy", type=float, default=0.0)
    ap.add_argument("--wz", type=float, default=0.0)
    ap.add_argument("--estop", type=int, default=None)   # 0/1
    ap.add_argument("--feed", type=int, default=None)    # 0~3
    args = ap.parse_args()

    uart = UartLink(UartConfig(port=args.port, baudrate=args.baud, enabled=args.enabled))
    uart.open()

    if args.estop is not None:
        uart.send(make_estop_frame(args.estop))
        print("sent estop", args.estop)

    if args.feed is not None:
        uart.send(make_feed_frame(args.feed))
        print("sent feed", args.feed)

    uart.send(make_cmd_vel_frame(args.vx, args.vy, args.wz))
    print("sent cmd_vel", args.vx, args.vy, args.wz)

    time.sleep(0.2)
    uart.close()

if __name__ == "__main__":
    main()
