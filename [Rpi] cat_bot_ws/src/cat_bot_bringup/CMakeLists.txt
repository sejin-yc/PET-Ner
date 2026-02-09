cmake_minimum_required(VERSION 3.8)
project(cat_bot_bringup)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 의존성 패키지 설정
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(robot_state_publisher REQUIRED)
find_package(ydlidar_ros2_driver REQUIRED)

# =========================================================
# 설치 설정 (라즈베리 파이 실행용)
# =========================================================

# 1. 런치 파일 및 하드웨어 설정(config) 폴더만 share 폴더로 설치
# Nav2와 맵은 PC에서 관리하므로 maps, params 폴더는 제외했습니다.
install(
  DIRECTORY 
    launch 
    config
  DESTINATION share/${PROJECT_NAME}
)

# 2. (선택) 만약 나중에 하드웨어 제어용 파이썬 노드를 만든다면 
# 여기에 install(PROGRAMS ...)를 추가하면 됩니다. 현재는 비워둡니다.

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
