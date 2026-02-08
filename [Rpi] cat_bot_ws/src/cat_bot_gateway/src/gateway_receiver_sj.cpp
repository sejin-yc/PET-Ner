/**
 * @file    : serial_bridge_cmd_vel_out.cpp
 * @brief   : ROS2 /cmd_vel_out (또는 지정 토픽) Twist -> STM32 1바이트(w/x/a/d/q/e/s) 전송
 */

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <cmath>
#include <string>

using std::placeholders::_1;

class SerialBridgeCmdVelOut : public rclcpp::Node {
public:
    SerialBridgeCmdVelOut() : Node("serial_bridge_cmd_vel_out") {
        // -------------------------
        // Parameters
        // -------------------------
        this->declare_parameter<std::string>("serial_port", "/dev/ttyAMA0");
        this->declare_parameter<int>("baudrate", 115200);

        this->declare_parameter<std::string>("cmd_topic", "/cmd_vel_out");

        // deadband
        this->declare_parameter<double>("deadband_lin", 0.08);
        this->declare_parameter<double>("deadband_ang", 0.08);

        // watchdog resend (STM timeout 방지용)
        this->declare_parameter<bool>("watchdog_enable", true);
        this->declare_parameter<double>("watchdog_period_sec", 0.05);  // 50ms

        serial_port_ = this->get_parameter("serial_port").as_string();
        baudrate_ = this->get_parameter("baudrate").as_int();
        cmd_topic_ = this->get_parameter("cmd_topic").as_string();

        deadband_lin_ = this->get_parameter("deadband_lin").as_double();
        deadband_ang_ = this->get_parameter("deadband_ang").as_double();

        watchdog_enable_ = this->get_parameter("watchdog_enable").as_bool();
        watchdog_period_sec_ = this->get_parameter("watchdog_period_sec").as_double();

        // -------------------------
        // Serial open
        // -------------------------
        serial_fd_ = open_serial_port(serial_port_.c_str(), baudrate_);
        if (serial_fd_ < 0) {
            RCLCPP_ERROR(this->get_logger(),
                         "Failed to open serial port: %s (check permissions)",
                         serial_port_.c_str());
            // 노드 자체는 떠있게 두되, 동작은 못하게 됨
        } else {
            RCLCPP_INFO(this->get_logger(), "Serial connected: %s @ %d", serial_port_.c_str(), baudrate_);
        }

        // -------------------------
        // Subscriber
        // -------------------------
        subscription_ = this->create_subscription<geometry_msgs::msg::Twist>(
            cmd_topic_, 10, std::bind(&SerialBridgeCmdVelOut::topic_callback, this, _1));

        RCLCPP_INFO(this->get_logger(), "Subscribing: %s", cmd_topic_.c_str());

        // -------------------------
        // Watchdog timer (optional)
        // -------------------------
        if (watchdog_enable_) {
            auto period = std::chrono::duration<double>(watchdog_period_sec_);
            watchdog_timer_ = this->create_wall_timer(
                std::chrono::duration_cast<std::chrono::nanoseconds>(period),
                std::bind(&SerialBridgeCmdVelOut::watchdog_callback, this));
            RCLCPP_INFO(this->get_logger(), "Watchdog enabled: %.3f sec", watchdog_period_sec_);
        } else {
            RCLCPP_INFO(this->get_logger(), "Watchdog disabled");
        }
    }

    ~SerialBridgeCmdVelOut() override {
        if (serial_fd_ >= 0) close(serial_fd_);
    }

private:
    // -------------------------
    // Helpers
    // -------------------------
    bool near0(double v, double eps) const {
        return std::fabs(v) < eps;
    }

    int open_serial_port(const char* portname, int baudrate) {
        int fd = open(portname, O_RDWR | O_NOCTTY);
        if (fd < 0) return -1;

        struct termios tty;
        memset(&tty, 0, sizeof(tty));
        if (tcgetattr(fd, &tty) != 0) {
            close(fd);
            return -1;
        }

        speed_t baud;
        switch (baudrate) {
            case 9600: baud = B9600; break;
            case 19200: baud = B19200; break;
            case 38400: baud = B38400; break;
            case 57600: baud = B57600; break;
            case 115200: baud = B115200; break;
            default: baud = B115200; break;
        }

        cfsetospeed(&tty, baud);
        cfsetispeed(&tty, baud);

        // 8N1, no flow control
        tty.c_cflag |= (CLOCAL | CREAD);
        tty.c_cflag &= ~PARENB;
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CSIZE;
        tty.c_cflag |= CS8;
        tty.c_cflag &= ~CRTSCTS;

        // raw mode
        tty.c_lflag = 0;
        tty.c_iflag = 0;
        tty.c_oflag = 0;

        // flush + apply
        tcflush(fd, TCIFLUSH);
        if (tcsetattr(fd, TCSANOW, &tty) != 0) {
            close(fd);
            return -1;
        }
        return fd;
    }

    void send_char(char c) {
        if (serial_fd_ < 0) return;
        int n = write(serial_fd_, &c, 1);
        if (n != 1) {
            RCLCPP_ERROR(this->get_logger(), "Serial write failed!");
        }
    }

    // Twist -> command char
    char twist_to_cmd(const geometry_msgs::msg::Twist& t) {
        const double vx = t.linear.x;
        const double vy = t.linear.y;
        const double wz = t.angular.z;

        // 완전 정지 판정(노이즈 방지)
        if (near0(vx, deadband_lin_) && near0(vy, deadband_lin_) && near0(wz, deadband_ang_)) {
            return 's';
        }

        // 섞여 들어오면 가장 큰 축 1개만 선택 (안전)
        const double ax = std::fabs(vx);
        const double ay = std::fabs(vy);
        const double aw = std::fabs(wz);

        if (ax >= ay && ax >= aw) {
            return (vx > 0.0) ? 'w' : 'x';
        } else if (ay >= ax && ay >= aw) {
            return (vy > 0.0) ? 'a' : 'd';
        } else {
            return (wz > 0.0) ? 'q' : 'e';
        }
    }

    // -------------------------
    // Callbacks
    // -------------------------
    void topic_callback(const geometry_msgs::msg::Twist::SharedPtr msg) {
        last_twist_ = *msg;
        last_cmd_ = twist_to_cmd(*msg);

        // 같은 명령이면 굳이 스팸 전송 안함 (watchdog가 있으면 더더욱)
        if (last_cmd_ == prev_sent_cmd_) return;

        send_char(last_cmd_);
        prev_sent_cmd_ = last_cmd_;

        RCLCPP_INFO(this->get_logger(),
                    "TX [%c] (vx=%.2f vy=%.2f wz=%.2f) topic=%s",
                    last_cmd_, msg->linear.x, msg->linear.y, msg->angular.z, cmd_topic_.c_str());
    }

    void watchdog_callback() {
        // watchdog: 마지막 명령을 주기적으로 재전송 (STM 타임아웃 방지)
        if (serial_fd_ < 0) return;

        // 아직 아무 cmd도 받은 적 없으면 아무것도 안 보냄
        if (last_cmd_ == 0 || last_cmd_ == 's') return;

        send_char(last_cmd_);
        // 로그는 너무 많아져서 기본은 생략
    }

    // -------------------------
    // Members
    // -------------------------
    std::string serial_port_;
    int baudrate_;
    std::string cmd_topic_;

    double deadband_lin_;
    double deadband_ang_;

    bool watchdog_enable_;
    double watchdog_period_sec_;

    int serial_fd_ = -1;

    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr subscription_;
    rclcpp::TimerBase::SharedPtr watchdog_timer_;

    geometry_msgs::msg::Twist last_twist_;
    char last_cmd_ = 0;
    char prev_sent_cmd_ = 0;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SerialBridgeCmdVelOut>());
    rclcpp::shutdown();
    return 0;
}
