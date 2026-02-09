import os
import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    bringup_dir = get_package_share_directory('cat_bot_bringup')
    description_dir = get_package_share_directory('cat_bot_description')
    lidar_driver_dir = get_package_share_directory('ydlidar_ros2_driver')

    # 1. Xacro 변환 (URDF)
    xacro_file = os.path.join(description_dir, 'urdf', 'catbot_full.xacro')
    robot_description_config = xacro.process_file(xacro_file).toxml()

    # 2. 설정 파일 경로 (config 폴더)
    filter_config = os.path.join(bringup_dir, 'config', 'laser_filter.yaml')

    # 3. Robot State Publisher
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description_config, 'use_sim_time': False}]
    )

    # 4. Joint State Publisher
    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher'
    )

    # 5. YDLIDAR Driver (보드레이트 등 인자 전달)
    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(lidar_driver_dir, 'launch', 'ydlidar_launch.py')
        ),
        launch_arguments={
            'port': '/dev/ttyUSB0',
            'baudrate': '128000' # 명철님 사양에 맞춰 수정
        }.items()
    )

    # 6. Laser Filter
    laser_filter_node = Node(
        package='laser_filters',
        executable='scan_to_scan_filter_chain',
        parameters=[filter_config],
        remappings=[('scan_filtered', 'scan_filtered')]
    )

    return LaunchDescription([
        LogInfo(msg='[Cat Bot] Hardware Bringup Starting...'),
        rsp_node,
        jsp_node,
        lidar_launch,
        laser_filter_node
    ])
