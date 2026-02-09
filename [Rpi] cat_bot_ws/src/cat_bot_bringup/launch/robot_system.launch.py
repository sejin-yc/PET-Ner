import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    bringup_pkg = get_package_share_directory('cat_bot_bringup')
    gateway_pkg = get_package_share_directory('cat_bot_gateway')

    # 1. 기본 Bringup (URDF, LiDAR, Camera)
    included_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup_pkg, 'launch', 'bringup.launch.py'))
    )

    # 2. Gateway (STM32 통신 및 TwistMux)
    gateway_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(gateway_pkg, 'launch', 'gateway.launch.py'))
    )

    # 3. rf2o_laser_odometry (라파에서 계산해서 TF 발행)
    rf2o_node = Node(
        package='rf2o_laser_odometry',
        executable='rf2o_laser_odometry_node',
        name='rf2o_laser_odometry_node',
        parameters=[{
            'laser_scan_topic': '/scan_filtered',
            'odom_topic': '/odom',
            'publish_tf': True,
            'base_frame_id': 'base_link',
            'odom_frame_id': 'odom',
            'freq': 10.0 # 라파 부하 조절을 위해 10~20Hz 권장
        }]
    )

    return LaunchDescription([
        included_bringup,
        gateway_launch,
        rf2o_node
    ])
