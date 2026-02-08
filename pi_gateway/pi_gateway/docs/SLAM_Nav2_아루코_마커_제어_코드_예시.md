# SLAM/Nav2 아루코 마커 제어 코드 예시

SLAM/Nav2 담당자가 아루코 마커 정밀 제어 시 패트롤을 멈추는 코드 예시입니다.

---

## 🎯 핵심

**아루코 마커 정밀 제어 시작 전에 `control_mode`에 "teleop"을 발행하고, 완료 후 "auto"를 발행하면 됩니다.**

---

## 📋 코드 예시

### Python (ROS2)

```python
from std_msgs.msg import String
from rclpy.node import Node

class ArucoControlNode(Node):
    def __init__(self):
        super().__init__("aruco_control_node")
        
        # control_mode 발행자 생성
        self.pub_mode = self.create_publisher(String, "control_mode", 10)
        
        # 아루코 마커 감지 구독 (예시)
        # self.sub_aruco = self.create_subscription(...)
    
    def start_precision_control(self):
        """아루코 마커 정밀 제어 시작."""
        # 패트롤 멈춤
        msg = String()
        msg.data = "teleop"  # 패트롤 멈춤
        self.pub_mode.publish(msg)
        self.get_logger().info("Patrol stopped for precision control")
    
    def finish_precision_control(self):
        """아루코 마커 정밀 제어 완료."""
        # 패트롤 재개
        msg = String()
        msg.data = "auto"  # 패트롤 재개
        self.pub_mode.publish(msg)
        self.get_logger().info("Patrol resumed")
    
    def on_aruco_detected(self, aruco_msg):
        """아루코 마커 감지 시 호출 (예시)."""
        if aruco_msg.detected:
            self.start_precision_control()  # 정밀 제어 시작
            # 정밀 제어 로직 수행
            # ...
            self.finish_precision_control()  # 정밀 제어 완료
```

---

### C++ (ROS2)

```cpp
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

class ArucoControlNode : public rclcpp::Node {
public:
    ArucoControlNode() : Node("aruco_control_node") {
        // control_mode 발행자 생성
        pub_mode_ = this->create_publisher<std_msgs::msg::String>("control_mode", 10);
    }
    
    void start_precision_control() {
        // 패트롤 멈춤
        auto msg = std_msgs::msg::String();
        msg.data = "teleop";  // 패트롤 멈춤
        pub_mode_->publish(msg);
        RCLCPP_INFO(this->get_logger(), "Patrol stopped for precision control");
    }
    
    void finish_precision_control() {
        // 패트롤 재개
        auto msg = std_msgs::msg::String();
        msg.data = "auto";  // 패트롤 재개
        pub_mode_->publish(msg);
        RCLCPP_INFO(this->get_logger(), "Patrol resumed");
    }

private:
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_mode_;
};
```

---

## 🔄 실제 사용 시나리오

### 시나리오 1: 아루코 마커 감지 시

```python
def on_aruco_detected(self, aruco_msg):
    if aruco_msg.detected and aruco_msg.confidence > 0.8:
        # 정밀 제어 시작
        self.pub_mode.publish(String(data="teleop"))
        
        # 정밀 제어 수행
        self.perform_precision_control(aruco_msg.pose)
        
        # 정밀 제어 완료
        self.pub_mode.publish(String(data="auto"))
```

### 시나리오 2: 특정 위치 도달 시

```python
def on_waypoint_reached(self, waypoint_msg):
    if waypoint_msg.name == "aruco_zone":
        # 아루코 마커 구역 도달
        self.pub_mode.publish(String(data="teleop"))  # 패트롤 멈춤
        
        # 아루코 마커 정밀 제어
        while not self.aruco_aligned():
            self.adjust_position()
        
        self.pub_mode.publish(String(data="auto"))  # 패트롤 재개
```

### 시나리오 3: 타이머 기반

```python
def __init__(self):
    # ...
    self.timer = self.create_timer(1.0, self.check_aruco_control)

def check_aruco_control(self):
    if self.in_precision_zone():
        if self.mode != "teleop":
            self.pub_mode.publish(String(data="teleop"))
            self.mode = "teleop"
    else:
        if self.mode != "auto":
            self.pub_mode.publish(String(data="auto"))
            self.mode = "auto"
```

---

## 📊 전체 흐름

```
1. 아루코 마커 감지 또는 특정 위치 도달
   ↓
2. if 조건 확인
   ↓
3. control_mode = "teleop" 발행
   ↓
4. PatrolLoop → 패트롤 멈춤
   ↓
5. Nav2가 정밀 제어 명령 발행 (cmd_vel_auto)
   ↓
6. Pi Gateway → STM32로 전달
   ↓
7. 정밀 제어 완료
   ↓
8. control_mode = "auto" 발행
   ↓
9. PatrolLoop → 패트롤 재개
```

---

## ✅ 요약

**SLAM/Nav2 담당자가 할 일:**

1. **아루코 마커 정밀 제어 시작 전:**
   ```python
   pub_mode.publish(String(data="teleop"))
   ```

2. **아루코 마커 정밀 제어 완료 후:**
   ```python
   pub_mode.publish(String(data="auto"))
   ```

**조건부로 발행:**
```python
if aruco_detected or in_precision_zone():
    pub_mode.publish(String(data="teleop"))  # 패트롤 멈춤
    # 정밀 제어 수행
    pub_mode.publish(String(data="auto"))  # 패트롤 재개
```

**Pi Gateway는:**
- `control_mode` 토픽을 구독하고 있음
- "teleop"이면 자동으로 패트롤 멈춤
- "auto"이면 자동으로 패트롤 재개
- **추가 코드 수정 불필요**
