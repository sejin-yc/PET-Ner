# 🏗️ System Architecture

## 1. Overview
본 로봇은 **STM32 G431RB**를 메인 하위 제어기(Low-level Controller)로 사용하며, 상위 제어기(Jetson Orin Nano, RPi)와 UART 통신을 수행합니다. 전원 시스템은 구동용(LiPo)과 서비스용(보조배터리)으로 물리적으로 분리되어 안정성을 확보했습니다.

## 2. Block Diagram
```mermaid
graph TD
    %% 스타일 정의
    classDef power fill:#ffcccc,stroke:#ff0000,stroke-width:2px;
    classDef signal fill:#e6f3ff,stroke:#0000ff,stroke-dasharray: 5 5;
    classDef actuator fill:#fff3cd,stroke:#e0a800,stroke-width:2px;

    %% 전원 소스
    LiPo["🔋 LiPo Battery (12.6V)"]:::power
    PowerBank["🔋 Power Bank (5V)"]:::power

    %% 전원 분배
    FuseHub["🔌 6-Way Fuse Hub"]:::power
    Buck["📉 DC-DC Converter (5V)"]:::power

    %% 제어기
    Jetson["🧠 Jetson Orin Nano / RPi"]
    STM32["🦾 STM32 G431RB"]
    Lidar["📡 LiDAR Sensor"]

    %% 구동기
    MDD["⚡ Motor Drivers (MDD10A x2)"]:::actuator
    Motors["⚙️ Mecanum Wheels (x4)"]:::actuator
    RobotArm["🦾 Robot Arm"]:::actuator
    
    %% 서비스 모듈 (보조배터리 사용)
    Servo_Feeder["🍚 Feeder Servo (MG996R)"]:::actuator
    Servo_Injector["💉 Injector Servo (MG996R)"]:::actuator

    %% === Power Flow (Red Lines) ===
    LiPo ==> FuseHub
    FuseHub ==> MDD
    FuseHub ==> RobotArm
    FuseHub ==> Buck
    Buck ==> Jetson
    Buck ==> STM32
    Buck ==> Lidar
    
    PowerBank ==> Servo_Feeder
    PowerBank ==> Servo_Injector

    %% === Data Flow (Blue Dotted) ===
    Jetson -.->|UART (Tx/Rx)| STM32
    STM32 -.->|PWM/DIR| MDD
    MDD ==> Motors
    Motors -.->|Encoder Pulse| STM32
    Lidar -.->|Data| Jetson
    
    %% 링크 스타일
    linkStyle 0,1,2,3,4,5,6,7,8 stroke:red,stroke-width:3px;
    linkStyle 9,10,11,12,13 stroke:blue,stroke-width:1px,fill:none;
```

## 3. Power Distribution Strategy
* **Main Power (3S LiPo 12.6V):**
    * 주행 모터, 로봇팔, 메인 컴퓨팅 유닛(Jetson, RPi), Lidar, STM32에 전원 공급.
    * 6구 퓨즈 허브를 통해 전력을 분배하여 과전류 보호 및 배선 효율화.
* **Service Power (Power Bank 5V):**
    * **밥 주기 개폐기**와 **츄르 주입기**에 사용되는 MG996R 서보모터 2개 전용.
    * 서보모터의 노이즈가 메인 제어 시스템에 영향을 주지 않도록 전원 완전 분리.

## 4. Communication Interface
* **Connection:** Pin-to-Pin Direct Connection (Tx-Rx, Rx-Tx, GND-GND)
* **Protocol:** UART (Baudrate 115200)
