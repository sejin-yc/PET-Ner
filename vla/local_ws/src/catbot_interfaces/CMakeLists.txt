cmake_minimum_required(VERSION 3.8)
project(catbot_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
# 1. 의존성 추가
find_package(rosidl_default_generators REQUIRED)
find_package(action_msgs REQUIRED)

# 2. 인터페이스 생성 설정
rosidl_generate_interfaces(${PROJECT_NAME}
  "action/VlaTask.action"
  DEPENDENCIES action_msgs
)

ament_package()