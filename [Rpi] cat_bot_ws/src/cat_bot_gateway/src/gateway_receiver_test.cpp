/**
 * @file    : serial_bridge_cmd_vel_out.cpp
 * @brief   : ROS2 /cmd_vel_out -> STM32 1Byte Protocol
 * @details : [기능 포함] 
 * 1. Twist Mux 연동 (/cmd_vel_out 구독)
 * 2. 승자독식 (Winner Takes All): X, Y, 회전 중 가장 큰 값 하나만 수행
 * 3. 관성 제어 (Inertia Brake): 이동 방향 전환 시 강제 정지 후 출발
 * @author  : 명철님 (Updated by Gemini)
 */

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <cmath>
#include <string>
#include <thread> // [추가] sleep을 위해 필요
#include <chrono> // [추가] 시간 단위를 위해 필요

using std::placeholders::_1;
using namespace std::chrono_literals;

class SerialBridgeCmdVelOut : public rclcpp::Node {
public:
    SerialBridgeCmdVelOut() : Node("serial_bridge_cmd_vel_out") {
        // --------------------------------------------------------
        // 1. 파라미터 설정 (Parameters)
        // --------------------------------------------------------
        this->declare_parameter<std::string>("serial_port", "/dev/ttyAMA0");
        this->declare_parameter<int>("baudrate", 115200);

        // [중요] Twist Mux의 출력 토픽 이름과 일치해야 합니다.
        this->declare_parameter<std::string>("cmd_topic", "/cmd_vel_out");

        // 데드존 (노이즈 방지)
        this->declare_parameter<double>("deadband_lin", 0.08);
        this->declare_parameter<double>("deadband_ang", 0.08);

        // 왓치독 (통신 끊김 방지)
        this->declare_parameter<bool>("watchdog_enable", true);
        this->declare_parameter<double>("watchdog_period_sec", 0.05);

        // [핵심] 관성 제거를 위한 정지 시간 (ms 단위)
        // 로봇이 무거워서 많이 미끄러지면 300, 가벼우면 100 정도로 조절하세요.
        this->declare_parameter<int>("inertia_brake_ms", 50); 

        // 파라미터 불러오기
        serial_port_ = this->get_parameter("serial_port").as_string();
        baudrate_ = this->get_parameter("baudrate").as_int();
        cmd_topic_ = this->get_parameter("cmd_topic").as_string();

        deadband_lin_ = this->get_parameter("deadband_lin").as_double();
        deadband_ang_ = this->get_parameter("deadband_ang").as_double();

        watchdog_enable_ = this->get_parameter("watchdog_enable").as_bool();
        watchdog_period_sec_ = this->get_parameter("watchdog_period_sec").as_double();
        
        inertia_brake_ms_ = this->get_parameter("inertia_brake_ms").as_int();

        // --------------------------------------------------------
        // 2. 시리얼 포트 개방 (Serial Open)
        // --------------------------------------------------------
        serial_fd_ = open_serial_port(serial_port_.c_str(), baudrate_);
        if (serial_fd_ < 0) {
            RCLCPP_ERROR(this->get_logger(), "Failed to open serial port: %s (Check Permissions)", serial_port_.c_str());
            // 노드는 살려두되 통신 불가 상태
        } else {
            RCLCPP_INFO(this->get_logger(), "Serial Connected: %s @ %d bps", serial_port_.c_str(), baudrate_);
            RCLCPP_INFO(this->get_logger(), "Mode: Winner Takes All + Inertia Brake (%d ms)", inertia_brake_ms_);
        }

        // --------------------------------------------------------
        // 3. 서브스크라이버 (Subscriber)
        // --------------------------------------------------------
        // Twist Mux에서 나오는 최종 명령을 구독합니다.
        subscription_ = this->create_subscription<geometry_msgs::msg::Twist>(
            cmd_topic_, 1, std::bind(&SerialBridgeCmdVelOut::topic_callback, this, _1));

        RCLCPP_INFO(this->get_logger(), "Subscribing to: %s", cmd_topic_.c_str());

        // --------------------------------------------------------
        // 4. 왓치독 타이머 (Watchdog)
        // --------------------------------------------------------
        if (watchdog_enable_) {
            auto period = std::chrono::duration<double>(watchdog_period_sec_);
            watchdog_timer_ = this->create_wall_timer(
                std::chrono::duration_cast<std::chrono::nanoseconds>(period),
                std::bind(&SerialBridgeCmdVelOut::watchdog_callback, this));
        }
    }

    ~SerialBridgeCmdVelOut() override {
        if (serial_fd_ >= 0) {
            send_char('s'); // 종료 시 로봇 정지
            close(serial_fd_);
        }
    }

private:
    // --------------------------------------------------------
    // Helper Functions
    // --------------------------------------------------------
    bool near0(double v, double eps) const {
        return std::fabs(v) < eps;
    }

    // 시리얼 포트 설정 (Linux Standard)
    int open_serial_port(const char* portname, int baudrate) {
        int fd = open(portname, O_RDWR | O_NOCTTY);
        if (fd < 0) return -1;

        struct termios tty;
        memset(&tty, 0, sizeof(tty));
        if (tcgetattr(fd, &tty) != 0) { close(fd); return -1; }

        speed_t baud;
        switch (baudrate) {
            case 9600: baud = B9600; break;
            case 57600: baud = B57600; break;
            case 115200: baud = B115200; break;
            default: baud = B115200; break;
        }

        cfsetospeed(&tty, baud);
        cfsetispeed(&tty, baud);

        // 8N1 Setting
        tty.c_cflag |= (CLOCAL | CREAD);
        tty.c_cflag &= ~PARENB;
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CSIZE;
        tty.c_cflag |= CS8;
        tty.c_cflag &= ~CRTSCTS; // No Flow Control

        // Raw Mode
        tty.c_lflag = 0;
        tty.c_iflag = 0;
        tty.c_oflag = 0;

        tcflush(fd, TCIFLUSH);
        if (tcsetattr(fd, TCSANOW, &tty) != 0) { close(fd); return -1; }
        return fd;
    }

    void send_char(char c) {
        if (serial_fd_ < 0) return;
        int n = write(serial_fd_, &c, 1);
        if (n != 1) RCLCPP_ERROR(this->get_logger(), "Serial write failed!");
    }

    // [핵심] Twist 메시지를 단일 문자(w/x/a/d/q/e/s)로 변환
    // 여기서 '승자독식(Winner Takes All)' 로직이 수행됩니다.
    char twist_to_cmd(const geometry_msgs::msg::Twist& t) {
        const double vx = t.linear.x;
        const double vy = t.linear.y;
        const double wz = t.angular.z;

        // 1. 데드존 체크 (너무 작은 값은 정지로 처리)
        if (near0(vx, deadband_lin_) && near0(vy, deadband_lin_) && near0(wz, deadband_ang_)) {
            return 's';
        }

        // 2. 절댓값 크기 비교
        const double ax = std::fabs(vx);
        const double ay = std::fabs(vy);
        const double aw = std::fabs(wz);

        // 3. 가장 큰 축 하나만 선택
        if (ax >= ay && ax >= aw) {
            return (vx > 0.0) ? 'w' : 'x'; // 전진 / 후진
        } else if (ay >= ax && ay >= aw) {
            return (vy > 0.0) ? 'a' : 'd'; // 좌 / 우 (메카넘)
        } else {
            return (wz > 0.0) ? 'q' : 'e'; // 좌회전 / 우회전
        }
    }

    // --------------------------------------------------------
    // Callbacks
    // --------------------------------------------------------
    void topic_callback(const geometry_msgs::msg::Twist::SharedPtr msg) {
        char new_cmd = twist_to_cmd(*msg);

        // 1. 명령이 이전과 동일하면 중복 전송 방지 (Watchdog가 처리함)
        if (new_cmd == prev_sent_cmd_) return;

        // 2. [관성 제어 로직] 방향 전환 감지
        // 조건: (이전이 정지가 아님) AND (지금도 정지가 아님) AND (명령이 다름)
        // 예: 'w'(전진) 하다가 'd'(오른쪽) 명령이 들어옴 -> 관성 발생 상황
        if (prev_sent_cmd_ != 's' && new_cmd != 's' && prev_sent_cmd_ != new_cmd) {
            
            // A. 일단 멈춤 신호 전송
            send_char('s');
            
            // B. 관성 죽이기 (파라미터 시간만큼 대기)
            // ROS2 노드 스레드를 잠깐 재웁니다. 
            // STM이 물리적으로 멈출 시간을 벌어줍니다.
            if (inertia_brake_ms_ > 0) {
                std::this_thread::sleep_for(std::chrono::milliseconds(inertia_brake_ms_));
            }
            
            // (디버깅용 로그 - 필요하면 주석 해제)
            // RCLCPP_INFO(this->get_logger(), "BRAKE: %c -> s -> %c", prev_sent_cmd_, new_cmd);
        }

        // 3. 새로운 명령 전송 (이제 관성이 죽었으므로 안전하게 이동)
        send_char(new_cmd);
        prev_sent_cmd_ = new_cmd;
    }

    void watchdog_callback() {
        if (serial_fd_ < 0) return;
        
        // 아무 명령도 없었다면 무시
        if (prev_sent_cmd_ == 0) return;
        
        // STM 타임아웃 방지를 위해 마지막 명령 재전송
        send_char(prev_sent_cmd_);
    }

    // --------------------------------------------------------
    // Members
    // --------------------------------------------------------
    std::string serial_port_;
    int baudrate_;
    std::string cmd_topic_;

    double deadband_lin_;
    double deadband_ang_;
    bool watchdog_enable_;
    double watchdog_period_sec_;
    
    int inertia_brake_ms_; // 관성 제어 대기 시간

    int serial_fd_ = -1;

    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr subscription_;
    rclcpp::TimerBase::SharedPtr watchdog_timer_;

    char prev_sent_cmd_ = 's'; // 초기 상태는 정지
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SerialBridgeCmdVelOut>());
    rclcpp::shutdown();
    return 0;
}
