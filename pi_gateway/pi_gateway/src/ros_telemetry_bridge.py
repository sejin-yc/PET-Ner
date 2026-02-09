"""ros_telemetry_bridge.py — STM32(UART) → ROS2 토픽 브릿지.

정석: Web은 제어만 ROS로, ROS에서 cmd_vel_out 생성, ros_cmdvel가 UART로 전달.
여기서는 UART 텔레메트리 → telemetry/* 발행. Web은 telemetry/* 구독.

발행 토픽 (std_msgs/String, JSON): telemetry/battery, imu, encoder, raw.

실행 예:
  python3 -m pi_gateway.src.ros_telemetry_bridge --port /dev/serial0 --baud 115200

"""

from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Quaternion

from .uart_link import UartConfig, UartLink
from .uart_frames import decode_telemetry


class TelemetryRosPublisher(Node):
    """UART 안 열음. on_frame에서 넘긴 decode dict만 telemetry/* 로 발행. main이 UART 수신, 여기선 ROS만."""

    def __init__(self):
        super().__init__("telemetry_ros_publisher")
        self.pub_battery = self.create_publisher(String, "telemetry/battery", 10)
        self.pub_imu = self.create_publisher(String, "telemetry/imu", 10)
        self.pub_encoder = self.create_publisher(String, "telemetry/encoder", 10)
        self.pub_status = self.create_publisher(String, "telemetry/status", 10)
        self.pub_raw = self.create_publisher(String, "telemetry/raw", 10)

    def publish(self, obj: dict):
        msg = String()
        msg.data = json.dumps(obj, ensure_ascii=False)
        self.pub_raw.publish(msg)
        t = obj.get("type")
        if t == "battery":
            self.pub_battery.publish(msg)
        elif t == "imu":
            self.pub_imu.publish(msg)
        elif t == "encoder":
            self.pub_encoder.publish(msg)
        elif t == "status":
            self.pub_status.publish(msg)


def _yaw_to_quat(yaw: float) -> Quaternion:
    q = Quaternion()
    q.x, q.y = 0.0, 0.0
    q.z = math.sin(yaw / 2.0)
    q.w = math.cos(yaw / 2.0)
    return q

class EncoderOdomNode(Node):
    """
    telemetry/encoder + imu → (vx,vy,wz), yaw로 (x,y) 적분 → /odom 발행.
    
    지원 모드:
    1. 4륜 (fl, fr, rl, rr 모두 있음)
    2. 3륜 (fl 고장, fr/rl/rr + FL 추정) - 기본 모드
    
    SLAM+nav2 관점 권장 구성:
    - FL 추정값(v_fl = v_rr 또는 평균)으로 4륜식 계산 유지
    - EMA 필터링 (alpha=0.6~0.75)
    - IMU yaw + gyro_z(wz) 우선 사용 (가능하면)
    - 공분산으로 불확실성 표현 (EKF가 덜 믿도록)
    - robot_localization EKF로 최종 융합 권장
    """
    def __init__(self, *, meters_per_tick: float = 1.0e-5, odom_lx: float = 0.1, odom_ly: float = 0.1,
                 odom_frame_id: str = "odom", child_frame_id: str = "base_link",
                 use_imu_yaw: bool = True, use_imu_gyro: bool = True,
                 encoder_filter_alpha: float = 0.7, fl_estimation_method: str = "rr",
                 encoder_mode: str = "3wheel"):  # "auto", "4wheel", "3wheel"
        """
        Args:
            encoder_filter_alpha: EMA 필터링 강도 (0.6~0.75 권장, nav2 지연 생기면 올리기)
            fl_estimation_method: FL 추정 방법 ("rr" 또는 "fr_rr_avg")
        """
        super().__init__("encoder_odom_node")
        self._meters_per_tick = float(meters_per_tick)
        self._lx, self._ly = float(odom_lx), float(odom_ly)
        self._odom_frame, self._child_frame = str(odom_frame_id), str(child_frame_id)
        self._prev, self._prev_t = None, None
        self._x, self._y, self._yaw = 0.0, 0.0, 0.0
        self._imu_yaw = None
        self._imu_gyro_z = None  # IMU에서 받은 각속도 (wz)
        self._use_imu_yaw = bool(use_imu_yaw)
        self._use_imu_gyro = bool(use_imu_gyro)
        # 엔코더 속도 필터링 (지수 이동 평균) - SLAM/내비 지연 고려
        self._filter_alpha = float(encoder_filter_alpha)  # 0.6~0.75 권장
        self._prev_vx, self._prev_vy, self._prev_wz = 0.0, 0.0, 0.0
        # FL 추정 방법: "rr" (v_fl = v_rr) 또는 "fr_rr_avg" (v_fl = 0.5*(v_rr+v_fr))
        self._fl_estimation_method = str(fl_estimation_method)
        # 엔코더 모드: "auto" (자동 감지), "4wheel", "3wheel"
        self._encoder_mode = str(encoder_mode)
        
        self._sub_enc = self.create_subscription(String, "telemetry/encoder", self._on_encoder, 10)
        self._sub_imu = self.create_subscription(String, "telemetry/imu", self._on_imu, 10)
        self._pub = self.create_publisher(Odometry, "odom", 10)
        
        self.get_logger().info(f"EncoderOdomNode initialized: encoder_mode={self._encoder_mode}, "
                              f"IMU yaw={'enabled' if self._use_imu_yaw else 'disabled'}, "
                              f"IMU gyro={'enabled' if self._use_imu_gyro else 'disabled'}, "
                              f"filter_alpha={self._filter_alpha} (0.6~0.75 권장, nav2 지연 생기면 올리기), "
                              f"fl_estimation={self._fl_estimation_method} (rr 또는 fr_rr_avg)")

    def _on_imu(self, msg: String):
        """
        IMU 데이터 수신: yaw(rad) 및 gyro_z(wz, rad/s) 추출.
        
        yaw/wz는 IMU에서 가져오고, 가능하면 gyro_z도 사용.
        """
        try:
            obj = json.loads(msg.data)
            # yaw: IMU에서 우선 사용
            yaw = obj.get("yaw")
            if yaw is not None:
                self._imu_yaw = float(yaw)
            # gyro_z (각속도, rad/s): 가능하면 사용 (더 정확한 각속도)
            # 여러 필드명 시도: gyro_z, wz, angular_z, gyro_z_rad_s 등
            gyro_z = obj.get("gyro_z") or obj.get("wz") or obj.get("angular_z") or obj.get("gyro_z_rad_s")
            if gyro_z is not None:
                self._imu_gyro_z = float(gyro_z)
        except Exception:
            pass

    def _estimate_fl_velocity(self, v_fr: float, v_rl: float, v_rr: float) -> float:
        """
        왼쪽 앞바퀴(fl) 속도 추정 (pseudo FL).
        
        방법:
        - "rr": v_fl = v_rr (대칭 위치 가정, 기본값)
        - "fr_rr_avg": v_fl = 0.5 * (v_rr + v_fr) (앞바퀴 평균)
        """
        if self._fl_estimation_method == "rr":
            return v_rr  # 대칭 위치 가정
        elif self._fl_estimation_method == "fr_rr_avg":
            return 0.5 * (v_rr + v_fr)  # 앞바퀴 평균
        else:
            # 기본값: rr 사용
            return v_rr

    def _on_encoder(self, msg: String):
        try:
            obj = json.loads(msg.data)
        except Exception:
            return
        
        # 엔코더 데이터 읽기
        fl = obj.get("enc_fl")
        fr = obj.get("enc_fr")
        rl = obj.get("enc_rl")
        rr = obj.get("enc_rr")
        
        # 엔코더 모드 자동 감지
        if self._encoder_mode == "auto":
            if fl is not None and fr is not None and rl is not None and rr is not None:
                mode = "4wheel"
            elif fr is not None and rl is not None and rr is not None:
                mode = "3wheel"
            else:
                return  # 데이터 부족
        else:
            mode = self._encoder_mode
        
        # 모드별 데이터 검증
        if mode == "4wheel":
            if fl is None or fr is None or rl is None or rr is None:
                return
            enc_data = (int(fl), int(fr), int(rl), int(rr))
        elif mode == "3wheel":
            if fr is None or rl is None or rr is None:
                return
            enc_data = (int(fr), int(rl), int(rr))
        else:
            return
        
        now = self.get_clock().now()
        t = now.nanoseconds * 1e-9
        if self._prev is None:
            self._prev = enc_data
            self._prev_t = t
            return
        dt = t - self._prev_t
        if dt <= 1e-6:
            return
        
        # 모드별 속도 계산
        # meters_per_tick에 이미 x4 디코딩이 반영되어 있으므로, 델타 틱에 4를 나누지 않음.
        if mode == "4wheel":
            d_fl = (enc_data[0] - self._prev[0]) * self._meters_per_tick
            d_fr = (enc_data[1] - self._prev[1]) * self._meters_per_tick
            d_rl = (enc_data[2] - self._prev[2]) * self._meters_per_tick
            d_rr = (enc_data[3] - self._prev[3]) * self._meters_per_tick
            v_fl, v_fr, v_rl, v_rr = d_fl/dt, d_fr/dt, d_rl/dt, d_rr/dt
            
            # 4륜식 계산
            vx_raw = (v_fl + v_fr + v_rl + v_rr) / 4.0
            vy_raw = (-v_fl + v_fr - v_rl + v_rr) / 4.0
            den = 4.0 * (self._lx + self._ly)
            wz_raw = (-v_fl + v_fr + v_rl - v_rr) / den if den > 1e-9 else 0.0
            
        elif mode == "3wheel":
            d_fr = (enc_data[0] - self._prev[0]) * self._meters_per_tick
            d_rl = (enc_data[1] - self._prev[1]) * self._meters_per_tick
            d_rr = (enc_data[2] - self._prev[2]) * self._meters_per_tick
            v_fr, v_rl, v_rr = d_fr/dt, d_rl/dt, d_rr/dt
            
            # Pseudo FL 추정값 계산 (4륜식 유지)
            v_fl_est = self._estimate_fl_velocity(v_fr, v_rl, v_rr)
            
            # 4륜식 계산 (FL은 추정값)
            vx_raw = (v_fl_est + v_fr + v_rl + v_rr) / 4.0
            vy_raw = (-v_fl_est + v_fr - v_rl + v_rr) / 4.0
            den = 4.0 * (self._lx + self._ly)
            wz_raw = (-v_fl_est + v_fr + v_rl - v_rr) / den if den > 1e-9 else 0.0
        
        # vx, vy에 EMA 필터링 적용 (엔코더 기반 + EMA)
        vx = self._filter_alpha * vx_raw + (1.0 - self._filter_alpha) * self._prev_vx
        vy = self._filter_alpha * vy_raw + (1.0 - self._filter_alpha) * self._prev_vy
        
        # wz: IMU gyro_z 우선 사용 (가능하면 gyro_z도 쓰기)
        if self._use_imu_gyro and self._imu_gyro_z is not None:
            # IMU gyro_z 사용 (더 정확한 각속도)
            wz = self._imu_gyro_z
        else:
            # IMU 없으면 엔코더로 계산 (fallback)
            wz = self._filter_alpha * wz_raw + (1.0 - self._filter_alpha) * self._prev_wz
        
        # 이전 값 저장 (다음 필터링을 위해)
        self._prev_vx, self._prev_vy = vx, vy
        if self._use_imu_gyro and self._imu_gyro_z is None:
            self._prev_wz = wz  # 엔코더 wz만 저장 (IMU 사용 시 불필요)
        
        # Yaw: IMU 우선 사용 (없으면 엔코더로 적분)
        if self._use_imu_yaw and self._imu_yaw is not None:
            # IMU yaw 사용 (SLAM 맵 품질에 중요)
            yaw = self._imu_yaw
            # 엔코더 yaw는 fallback으로만 유지
            self._yaw = self._yaw + wz * dt  # 엔코더 yaw 업데이트 (fallback용)
        else:
            # IMU 없으면 엔코더로만 적분 (fallback)
            self._yaw += wz * dt
            yaw = self._yaw
        
        # 위치 적분 (로봇 좌표계 → 월드 좌표계 변환)
        self._x += (vx * math.cos(yaw) - vy * math.sin(yaw)) * dt
        self._y += (vx * math.sin(yaw) + vy * math.cos(yaw)) * dt
        
        # Odometry 메시지 생성
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = self._odom_frame
        odom.child_frame_id = self._child_frame
        odom.pose.pose.position.x = self._x
        odom.pose.pose.position.y = self._y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation = _yaw_to_quat(yaw)
        odom.twist.twist.linear.x, odom.twist.twist.linear.y = vx, vy
        odom.twist.twist.linear.z = 0.0
        odom.twist.twist.angular.x, odom.twist.twist.angular.y = 0.0, 0.0
        odom.twist.twist.angular.z = wz
        
        # 공분산 설정: 모드별 불확실성 표현 (EKF가 덜 믿도록)
        if mode == "3wheel":
            # 3륜 모드: FL 추정값 사용으로 불확실성 증가
            odom.pose.covariance[0] = 0.1   # x 불확실성
            odom.pose.covariance[7] = 0.1   # y 불확실성
            odom.pose.covariance[35] = 0.2  # yaw 불확실성 (FL 추정값 사용으로 증가)
            odom.twist.covariance[0] = 0.05   # vx 불확실성
            odom.twist.covariance[7] = 0.08   # vy 불확실성 (비대칭으로 인해 더 높음)
            odom.twist.covariance[35] = 0.1   # wz 불확실성 (IMU 사용 시 낮아짐)
        else:  # 4wheel
            # 4륜 모드: 정상 불확실성
            odom.pose.covariance[0] = 0.05   # x 불확실성
            odom.pose.covariance[7] = 0.05   # y 불확실성
            odom.pose.covariance[35] = 0.1  # yaw 불확실성
            odom.twist.covariance[0] = 0.03   # vx 불확실성
            odom.twist.covariance[7] = 0.03   # vy 불확실성
            odom.twist.covariance[35] = 0.05  # wz 불확실성 (IMU 사용 시 낮아짐)
        
        self._pub.publish(odom)
        # 이전 값 저장 (모드별)
        self._prev = enc_data
        self._prev_t = t


class RosTelemetryUartBridge(Node):
    def __init__(self, *, port: str, baud: int, enabled: bool = True):
        super().__init__("telemetry_uart_bridge")

        self.pub_battery = self.create_publisher(String, "telemetry/battery", 10)
        self.pub_imu = self.create_publisher(String, "telemetry/imu", 10)
        self.pub_encoder = self.create_publisher(String, "telemetry/encoder", 10)
        self.pub_raw = self.create_publisher(String, "telemetry/raw", 10)

        self.uart = UartLink(UartConfig(port=port, baudrate=baud, enabled=enabled, rx_thread=True))
        self.uart.set_on_frame(self._on_uart_frame)

        # UART 오픈
        self.uart.open()
        self.get_logger().info(f"UART opened: port={port} baud={baud}")

    def _publish_json(self, pub, obj):
        msg = String()
        msg.data = json.dumps(obj, ensure_ascii=False)
        pub.publish(msg)

    def _on_uart_frame(self, msg_id: int, payload: bytes):
        obj = decode_telemetry(msg_id, payload)
        # raw는 항상 발행
        self._publish_json(self.pub_raw, obj)

        # 타입별 라우팅
        if obj.get("type") == "battery":
            self._publish_json(self.pub_battery, obj)
        elif obj.get("type") == "encoder":
            self._publish_json(self.pub_encoder, obj)
        elif obj.get("type") == "imu":
            self._publish_json(self.pub_imu, obj)


def _install_sigint():
    signal.signal(signal.SIGINT, lambda s, f: (_ for _ in ()).throw(KeyboardInterrupt()))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyAMA0", help="Pi GPIO: ttyAMA0 or serial0; USB: ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args(argv)

    _install_sigint()

    rclpy.init()
    node = None
    try:
        node = RosTelemetryUartBridge(port=args.port, baud=args.baud, enabled=True)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            try:
                node.uart.close()
            except Exception:
                pass
            node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
