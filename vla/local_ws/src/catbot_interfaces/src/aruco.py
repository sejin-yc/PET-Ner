#!/usr/bin/env python3
"""ROS2 ArUco pose node (compat)

- OpenCV ArUco API 호환: DetectorParameters_create() / DetectorParameters()
- CompressedImage 구독
- 캘리브레이션(640x480)로 했는데 현재 해상도가 다르면 K 자동 스케일
- solvePnP(IPPE_SQUARE 우선)
- (선택) base_link로 변환: URDF TF(use_tf=true) 또는 수동 extrinsic(cam_in_base_*)

Publish:
  /aruco/id   (std_msgs/Int32)
  /aruco/pose (geometry_msgs/PoseStamped) : frame_id = base_frame(기본 base_link) 또는 camera_frame

Note:
  pose.position.x/y/z 는 "frame_id 기준"에서 마커 중심의 3D 위치(m)
"""

import math
import numpy as np
import cv2

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from sensor_msgs.msg import CompressedImage
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Int32

from tf2_ros import Buffer, TransformListener, TransformException
import rclpy.time


# -----------------------------
# Math helpers
# -----------------------------

def rpy_deg_to_R(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    r = math.radians(roll_deg)
    p = math.radians(pitch_deg)
    y = math.radians(yaw_deg)

    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)

    # R = Rz * Ry * Rx
    Rz = np.array([[cy, -sy, 0],
                   [sy,  cy, 0],
                   [ 0,   0, 1]], dtype=np.float64)
    Ry = np.array([[ cp, 0, sp],
                   [  0, 1,  0],
                   [-sp, 0, cp]], dtype=np.float64)
    Rx = np.array([[1,  0,   0],
                   [0, cr, -sr],
                   [0, sr,  cr]], dtype=np.float64)
    return Rz @ Ry @ Rx


def rotvec_to_R(rvec: np.ndarray) -> np.ndarray:
    R, _ = cv2.Rodrigues(rvec)
    return R


def R_to_quat_xyzw(R: np.ndarray):
    """Convert rotation matrix to quaternion (x,y,z,w)."""
    t = float(np.trace(R))
    if t > 0.0:
        s = math.sqrt(t + 1.0) * 2.0
        qw = 0.25 * s
        qx = (R[2, 1] - R[1, 2]) / s
        qy = (R[0, 2] - R[2, 0]) / s
        qz = (R[1, 0] - R[0, 1]) / s
    else:
        if (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
            s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2.0
            qw = (R[2, 1] - R[1, 2]) / s
            qx = 0.25 * s
            qy = (R[0, 1] + R[1, 0]) / s
            qz = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2.0
            qw = (R[0, 2] - R[2, 0]) / s
            qx = (R[0, 1] + R[1, 0]) / s
            qy = 0.25 * s
            qz = (R[1, 2] + R[2, 1]) / s
        else:
            s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2.0
            qw = (R[1, 0] - R[0, 1]) / s
            qx = (R[0, 2] + R[2, 0]) / s
            qy = (R[1, 2] + R[2, 1]) / s
            qz = 0.25 * s
    return float(qx), float(qy), float(qz), float(qw)


def get_aruco_dict(dict_name: str):
    # dict_name 예: "DICT_4X4_50"
    if hasattr(cv2.aruco, "getPredefinedDictionary"):
        return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
    if hasattr(cv2.aruco, "Dictionary_get"):
        return cv2.aruco.Dictionary_get(getattr(cv2.aruco, dict_name))
    raise RuntimeError("OpenCV aruco dictionary API not found")


def get_aruco_params():
    # OpenCV 버전에 따라 API가 다름
    if hasattr(cv2.aruco, "DetectorParameters"):
        return cv2.aruco.DetectorParameters()
    if hasattr(cv2.aruco, "DetectorParameters_create"):
        return cv2.aruco.DetectorParameters_create()
    raise RuntimeError("OpenCV aruco DetectorParameters API not found")


class ArucoPoseNode(Node):
    def __init__(self):
        super().__init__("aruco_pose_node_v3_autok")

        # ---------- params ----------
        self.declare_parameter("image_topic", "/front_cam/compressed")
        self.declare_parameter("debug_image_topic", "/image_aruco/compressed")
        self.declare_parameter("pose_topic", "/aruco/pose")
        self.declare_parameter("id_topic", "/aruco/id")

        self.declare_parameter("dictionary", "DICT_4X4_50")
        self.declare_parameter("marker_length_m", 0.0292)
        self.declare_parameter("publish_best_only", True)
        self.declare_parameter("target_id", -1)  # -1: 아무 id나

        # Calibration(캘리브레이션 당시 해상도)
        self.declare_parameter("calib_width", 640)
        self.declare_parameter("calib_height", 480)

        # Calibration matrices
        self.declare_parameter(
            "camera_matrix",
            [656.5, 0.0, 278.6,
             0.0, 612.1, 224.0,
             0.0, 0.0, 1.0]
        )
        self.declare_parameter("dist_coeffs", [0.055, 0.23, -0.02, -0.027, -0.52])

        # Publish frame
        self.declare_parameter("publish_in_base", True)
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("camera_frame", "camera_frame")

        # Manual extrinsic (base_T_cam)
        self.declare_parameter("cam_in_base_x", 0.15)
        self.declare_parameter("cam_in_base_y", 0.00)
        self.declare_parameter("cam_in_base_z", 0.10)
        self.declare_parameter("cam_in_base_roll_deg", -90.0)
        self.declare_parameter("cam_in_base_pitch_deg", 0.0)
        self.declare_parameter("cam_in_base_yaw_deg", -90.0)

        # Use TF instead of manual extrinsic
        self.declare_parameter("use_tf", False)

        # ---------- read ----------
        self.image_topic = self.get_parameter("image_topic").value
        self.debug_image_topic = self.get_parameter("debug_image_topic").value
        self.pose_topic = self.get_parameter("pose_topic").value
        self.id_topic = self.get_parameter("id_topic").value

        dict_name = self.get_parameter("dictionary").value
        self.marker_length = float(self.get_parameter("marker_length_m").value)
        self.publish_best_only = bool(self.get_parameter("publish_best_only").value)
        self.target_id = int(self.get_parameter("target_id").value)

        self.calib_w = int(self.get_parameter("calib_width").value)
        self.calib_h = int(self.get_parameter("calib_height").value)

        K_list = self.get_parameter("camera_matrix").value
        D_list = self.get_parameter("dist_coeffs").value
        self.K0 = np.array(K_list, dtype=np.float64).reshape(3, 3)
        self.D = np.array(D_list, dtype=np.float64).reshape(-1, 1)

        self.publish_in_base = bool(self.get_parameter("publish_in_base").value)
        self.base_frame = self.get_parameter("base_frame").value
        self.camera_frame = self.get_parameter("camera_frame").value

        tx = float(self.get_parameter("cam_in_base_x").value)
        ty = float(self.get_parameter("cam_in_base_y").value)
        tz = float(self.get_parameter("cam_in_base_z").value)
        rr = float(self.get_parameter("cam_in_base_roll_deg").value)
        pp = float(self.get_parameter("cam_in_base_pitch_deg").value)
        yy = float(self.get_parameter("cam_in_base_yaw_deg").value)

        self.t_base_cam_manual = np.array([tx, ty, tz], dtype=np.float64).reshape(3, 1)
        self.R_base_cam_manual = rpy_deg_to_R(rr, pp, yy)

        self.use_tf = bool(self.get_parameter("use_tf").value)

        # ---------- tf ----------
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ---------- aruco init ----------
        self.aruco_dict = get_aruco_dict(dict_name)
        self.aruco_params = get_aruco_params()

        # ---------- QoS ----------
        qos_img = QoSProfile(depth=1)
        qos_img.reliability = QoSReliabilityPolicy.BEST_EFFORT
        qos_img.durability = QoSDurabilityPolicy.VOLATILE

        qos_pub = QoSProfile(depth=10)
        qos_pub.reliability = QoSReliabilityPolicy.RELIABLE
        qos_pub.durability = QoSDurabilityPolicy.VOLATILE

        self.sub_img = self.create_subscription(CompressedImage, self.image_topic, self.on_img, qos_img)
        self.pub_pose = self.create_publisher(PoseStamped, self.pose_topic, qos_pub)
        self.pub_id = self.create_publisher(Int32, self.id_topic, qos_pub)
        self.pub_dbg = self.create_publisher(CompressedImage, self.debug_image_topic, qos_img)

        self.get_logger().info(
            f"✅ ArUcoPoseNode(compat) started. sub={self.image_topic} publish_in_base={self.publish_in_base} "
            f"base_frame={self.base_frame} camera_frame={self.camera_frame} use_tf={self.use_tf}"
        )

    # -----------------------------
    # Intrinsics scaling
    # -----------------------------
    def scaled_K(self, w: int, h: int) -> np.ndarray:
        sx = float(w) / float(self.calib_w)
        sy = float(h) / float(self.calib_h)
        K = self.K0.copy()
        K[0, 0] *= sx
        K[1, 1] *= sy
        K[0, 2] *= sx
        K[1, 2] *= sy
        return K

    # -----------------------------
    # Extrinsic: base_T_cam
    # -----------------------------
    def get_base_T_cam(self):
        if not self.publish_in_base:
            return None, None

        if self.use_tf:
            try:
                tf = self.tf_buffer.lookup_transform(self.base_frame, self.camera_frame, rclpy.time.Time())
                q = tf.transform.rotation
                t = tf.transform.translation

                x, y, z, w = q.x, q.y, q.z, q.w
                R = np.array([
                    [1 - 2*(y*y + z*z), 2*(x*y - z*w),     2*(x*z + y*w)],
                    [2*(x*y + z*w),     1 - 2*(x*x + z*z), 2*(y*z - x*w)],
                    [2*(x*z - y*w),     2*(y*z + x*w),     1 - 2*(x*x + y*y)],
                ], dtype=np.float64)

                tvec = np.array([t.x, t.y, t.z], dtype=np.float64).reshape(3, 1)
                return R, tvec
            except TransformException:
                # TF 실패하면 manual로 fallback
                pass

        return self.R_base_cam_manual, self.t_base_cam_manual

    # -----------------------------
    # Main callback (수정됨: 항상 이미지 송출)
    # -----------------------------
    def on_img(self, msg: CompressedImage):
        # decode compressed
        np_img = np.frombuffer(msg.data, dtype=np.uint8)
        frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if frame is None:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        K = self.scaled_K(w, h)

        # detect
        corners_list, ids, _ = cv2.aruco.detectMarkers(gray, self.aruco_dict, parameters=self.aruco_params)
        
        # --- [변경] ids가 있을 때만 포즈 계산 로직 수행 ---
        if ids is not None and len(ids) > 0:
            ids = ids.flatten().tolist()

            # choose marker
            sel = None
            if self.target_id >= 0:
                for i, mid in enumerate(ids):
                    if int(mid) == self.target_id:
                        sel = i
                        break
                # target_id를 찾지 못했으면 계산 스킵 (이미지는 보냄)
                if sel is None:
                    pass 
            else:
                # best-only면 가장 가까운 tz 선택
                sel = 0

            # Pose 계산 로직 진입 (target_id가 없거나 찾았을 때)
            # 만약 위에서 sel이 None인데 target_id 모드라면 여기 진입 안하도록 플래그 처리가 필요하지만,
            # 아래 로직은 전체 ids를 순회하므로 target_id 필터링이 아래 for문에서 다시 일어납니다.
            
            L = float(self.marker_length)
            half = L / 2.0
            objp = np.array([
                [-half,  half, 0.0],
                [ half,  half, 0.0],
                [ half, -half, 0.0],
                [-half, -half, 0.0],
            ], dtype=np.float64)

            best = None  # (tz, mid, rvec, tvec, corner)

            for i, mid in enumerate(ids):
                if (self.target_id >= 0) and (int(mid) != self.target_id):
                    continue

                corners = corners_list[i].reshape(4, 2).astype(np.float64)

                # solvePnP
                ok = False
                rvec = None
                tvec = None
                try:
                    ok, rvec, tvec = cv2.solvePnP(objp, corners, K, self.D, flags=cv2.SOLVEPNP_IPPE_SQUARE)
                except Exception:
                    ok, rvec, tvec = cv2.solvePnP(objp, corners, K, self.D, flags=cv2.SOLVEPNP_ITERATIVE)

                if not ok:
                    continue

                tz = float(tvec[2])
                if best is None or tz < best[0]:
                    best = (tz, int(mid), rvec, tvec, corners)

                if not self.publish_best_only:
                    self.publish_one(int(mid), rvec, tvec, msg, K, frame)

            if self.publish_best_only and best is not None:
                _, mid, rvec, tvec, corners = best
                self.publish_one(mid, rvec, tvec, msg, K, frame)

        # --- [변경] 마커 인식 여부와 상관없이 무조건 이미지 보냄 ---
        self.publish_debug(frame, msg)

    def publish_one(self, mid: int, rvec: np.ndarray, tvec: np.ndarray, img_msg: CompressedImage, K: np.ndarray, frame_bgr: np.ndarray):
        # cam -> marker
        R_cam_marker = rotvec_to_R(rvec)
        t_cam_marker = tvec.reshape(3, 1).astype(np.float64)

        out_frame = self.camera_frame
        R_out_marker = R_cam_marker
        t_out_marker = t_cam_marker

        if self.publish_in_base:
            R_base_cam, t_base_cam = self.get_base_T_cam()
            if R_base_cam is not None:
                # base_T_marker = base_T_cam * cam_T_marker
                R_out_marker = R_base_cam @ R_cam_marker
                t_out_marker = (R_base_cam @ t_cam_marker) + t_base_cam
                out_frame = self.base_frame

        # publish id
        self.pub_id.publish(Int32(data=int(mid)))

        # publish pose
        ps = PoseStamped()
        # CompressedImage header 그대로 쓰면 frame_id가 카메라 토픽 frame_id로 들어올 수 있음
        ps.header.stamp = img_msg.header.stamp
        ps.header.frame_id = out_frame

        ps.pose.position.x = float(t_out_marker[0, 0])
        ps.pose.position.y = float(t_out_marker[1, 0])
        ps.pose.position.z = float(t_out_marker[2, 0])

        qx, qy, qz, qw = R_to_quat_xyzw(R_out_marker)
        ps.pose.orientation.x = qx
        ps.pose.orientation.y = qy
        ps.pose.orientation.z = qz
        ps.pose.orientation.w = qw

        self.pub_pose.publish(ps)

        # draw axes for debug(로컬 frame 기준 축)
        try:
            cv2.aruco.drawDetectedMarkers(frame_bgr, [], None)
            cv2.drawFrameAxes(frame_bgr, K, self.D, rvec, tvec, self.marker_length * 0.5)
        except Exception:
            pass

    def publish_debug(self, frame_bgr: np.ndarray, img_msg: CompressedImage):
        try:
            ok, enc = cv2.imencode('.jpg', frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            if not ok:
                return
            out = CompressedImage()
            out.header = img_msg.header
            out.format = 'jpeg'
            out.data = enc.tobytes()
            self.pub_dbg.publish(out)
        except Exception:
            pass


def main():
    rclpy.init()
    node = ArucoPoseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()