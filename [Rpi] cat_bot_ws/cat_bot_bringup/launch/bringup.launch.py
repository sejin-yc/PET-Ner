import os
import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    # 패키지 경로 설정
    bringup_dir = get_package_share_directory('cat_bot_bringup')
    description_dir = get_package_share_directory('cat_bot_description')
    lidar_driver_dir = get_package_share_directory('ydlidar_ros2_driver')

    # 1. Xacro 변환 (URDF)
    xacro_file = os.path.join(description_dir, 'urdf', 'catbot_full.xacro')
    doc = xacro.process_file(xacro_file)
    robot_description_config = doc.toxml()

    # 2. 필터 설정 파일 경로
    filter_config = os.path.join(bringup_dir, 'config', 'laser_filter.yaml')

    # 3. Robot State Publisher
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description_config}]
    )

    # 4. Joint State Publisher
    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher'
    )

    # 5. YDLIDAR Driver 실행
    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(lidar_driver_dir, 'launch', 'ydlidar_launch.py')
        ),
        launch_arguments={
            'port': '/dev/ttyUSB0',
            'baudrate': '128000' 
        }.items()
    )

    # 6. Laser Filter Node
    laser_filter_node = Node(
        package='laser_filters',
        executable='scan_to_scan_filter_chain',
        parameters=[filter_config],
        remappings=[
            ('scan', 'scan'),
            ('scan_filtered', 'scan_filtered')
        ]
    )

    # [추가] 7. Camera Node (UDP 수신 및 토픽 발행)
    camera_node = Node(
        package='cat_bot_camera',
        executable='camera_node',
        name='camera_node',
        parameters=[{
            'udp_ip': '192.168.100.254',
            'udp_port': 5000
        }],
        output='screen'
    )

    return LaunchDescription([
        LogInfo(msg='[Cat Bot] Starting Bringup with Laser Filters and Camera...'),
        rsp_node,
        jsp_node,
        lidar_launch,
        laser_filter_node,
        camera_node  # [추가] 카메라 노드 실행 리스트에 포함
    ])
