cmake_minimum_required(VERSION 3.8)
project(cat_bot_gateway)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 1. 필수 의존성 패키지 찾기
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)

# -----------------------------
# 2. 실행 파일 생성 (원본 유지)
# -----------------------------
add_executable(gateway_receiver_node src/gateway_receiver.cpp)
ament_target_dependencies(gateway_receiver_node
  rclcpp
  nav_msgs
  geometry_msgs
  tf2
  tf2_ros
)

# -----------------------------
# 3. 실행 파일 생성 (SJ 테스트용)
# -----------------------------
add_executable(gateway_receiver_sj_node src/gateway_receiver_sj.cpp)
ament_target_dependencies(gateway_receiver_sj_node
  rclcpp
  nav_msgs
  geometry_msgs
  tf2
  tf2_ros
)

# -----------------------------
# 4. 테스트 노드 (기존 유지)
# -----------------------------
add_executable(gateway_receiver_test_node src/gateway_receiver_test.cpp)
ament_target_dependencies(gateway_receiver_test_node
  rclcpp
  nav_msgs
  geometry_msgs
  tf2
  tf2_ros
)

# 5. 실행 파일 설치
install(TARGETS
  gateway_receiver_node
  gateway_receiver_sj_node
  gateway_receiver_test_node
  DESTINATION lib/${PROJECT_NAME}
)

# 6. Launch 및 Config 폴더 설치
install(DIRECTORY
  launch
  config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
