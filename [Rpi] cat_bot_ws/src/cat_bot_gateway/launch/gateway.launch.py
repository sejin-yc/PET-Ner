import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_path = get_package_share_directory('cat_bot_gateway')
    # config 폴더 안의 yaml 파일을 읽어옵니다.
    twist_mux_config = os.path.join(pkg_path, 'config', 'cat_bot_twistmux.yaml')

    return LaunchDescription([
        Node(
            package='twist_mux',
            executable='twist_mux',
            output='screen',
            parameters=[twist_mux_config],
            remappings=[('cmd_vel_out', 'cmd_vel_out')]
        ),
        Node(
            package='cat_bot_gateway',
            executable='gateway_receiver_node', # 주의: CMakeLists.txt의 add_executable 이름과 같아야 함
            name='mecanum_gateway_node',
            output='screen'
        )
    ])
