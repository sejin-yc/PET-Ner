#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"

class CatBotGateway : public rclcpp::Node {
public:
    CatBotGateway() : Node("cat_bot_gateway") {
        // 1. 시리얼 포트 설정 (명철님 장치 확인 완료)
        const char* port_name = "/dev/ttyAMA0";
        serial_fd = open(port_name, O_RDWR | O_NOCTTY);

        if (serial_fd < 0) {
            RCLCPP_ERROR(this->get_logger(), "포트를 열 수 없습니다: %s. 권한을 확인하세요!", port_name);
            return;
        }

        // 2. 시리얼 통신 환경 설정 (115200 bps)
        struct termios tty;
        tcgetattr(serial_fd, &tty);
        cfsetospeed(&tty, B115200);
        cfsetispeed(&tty, B115200);
        tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
        tty.c_lflag = 0;
        tty.c_oflag = 0;
        tcsetattr(serial_fd, TCSANOW, &tty);

        // 3. cmd_vel 토픽 구독
        subscription_ = this->create_subscription<geometry_msgs::msg::Twist>(
            "cmd_vel", 10, std::bind(&CatBotGateway::velocity_callback, this, std::placeholders::_1));

        RCLCPP_INFO(this->get_logger(), "CatBot Gateway 시작됨. 포트: %s", port_name);
    }

    ~CatBotGateway() {
        if (serial_fd >= 0) close(serial_fd);
    }

private:
    void velocity_callback(const geometry_msgs::msg::Twist::SharedPtr msg) {
        char cmd = '\0';

        // 선속도(linear) 및 각속도(angular) 기반 키 매핑
        double vx = msg->linear.x;
        double vy = msg->linear.y;
        double omega = msg->angular.z;

        if (vx > 0.1) cmd = 'w';        // 전진
        else if (vx < -0.1) cmd = 'x';   // 후진
        else if (vy > 0.1) cmd = 'a';    // 좌 평행이동
        else if (vy < -0.1) cmd = 'd';   // 우 평행이동
        else if (omega > 0.1) cmd = 'q'; // 좌 회전
        else if (omega < -0.1) cmd = 'e';// 우 회전
        else if (vx == 0 && vy == 0 && omega == 0) cmd = 's'; // 정지

        if (cmd != '\0') {
            // STM32로 1바이트 전송 (echo -n "w" > /dev/ttyAMA0와 동일)
            write(serial_fd, &cmd, 1);
            RCLCPP_INFO(this->get_logger(), "명령 전송: [%c]", cmd);
        }
    }

    int serial_fd;
    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr subscription_;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<CatBotGateway>());
    rclcpp::shutdown();
    return 0;
}
