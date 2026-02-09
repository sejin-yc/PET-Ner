# 포팅 매뉴얼 (Porting Manual)

## 1. 개발 및 배포 환경

### 1.1 하드웨어 및 OS 요구사항

본 프로젝트는 AI 모델(CosyVoice) 구동을 위해 **GPU 환경**이 필수적입니다.

| 구분 | 사양 | 비고 |
| --- | --- | --- |
| **OS** | Ubuntu 20.04 LTS 이상 | Docker 호환성 권장 |
| **CPU** | 4 Core 이상 |  |
| **RAM** | 16GB 이상 | AI 모델 및 DB 부하 고려 |
| **GPU** | **NVIDIA GPU (VRAM 8GB↑)** | CosyVoice 구동 및 CUDA 가속 필수 |
| **Disk** | 50GB 이상 | Docker 이미지 및 모델 캐시 저장 공간 |

### 1.2 소프트웨어 및 프레임워크 버전

각 모듈별 상세 기술 스택과 버전 정보입니다.

| 구분 | 항목 | 버전 | 상세 설정/비고 |
| --- | --- | --- | --- |
| **Infra** | Docker | 24.0.x ↑ | 컨테이너 런타임 |
|  | Docker Compose | v2.21.0 ↑ | 오케스트레이션 도구 |
|  | Nginx | Alpine (Latest) | Reverse Proxy, SSL, WebSocket 지원 |
| **Backend** | Java (OpenJDK) | **17** | <br>`java-17-openjdk` 


| Spring Boot | **3.2.2** | Web, Security, JPA, Websocket 

 
| Build Tool | Gradle 7.6 |
| **Frontend** | Node.js | **20.x (LTS)** | 빌드 환경 


| React | **19.2.0** | Vite 번들러 사용 

| **Database** | PostgreSQL | **15** | 메인 RDBMS |
| **Broker** | Mosquitto | 2.0 | MQTT 메시지 브로커 |

### 1.3 로봇 하드웨어 구성 (Robot Hardware BOM)
본 프로젝트의 자율주행 로봇은 3단 적층 구조(Tier-based)로 설계되었으며, 상세 부품 명세는 다음과 같습니다.

| 층 (Tier) | 구분 | 부품명 (Model) | 수량 | 역할 및 설명 |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1**<br>(Drive & Sensing) | Motor | **JGB37-520** | 4 | 엔코더 내장 DC 기어드 모터 (하부 구동) |
| | Driver | **MDD10A** | 2 | 듀얼 채널 모터 드라이버 (4륜 제어) |
| | Wheel | **97mm Mecanum Wheel** | 1 Set | 전방향 이동(Omni-directional) 지원 휠 |
| | IMU | **BNO085** | 1 | 9축 관성 측정 센서 (정밀 자세 제어용) |
| **Tier 2**<br>(Logic & Power) | MCU | **STM32 Nucleo-F401RE** | 1 | 하위 제어기 (모터 PID 제어 및 센서 통합) |
| | LiDAR | **LDS-01** | 1 | 2D 360도 레이저 스캐너 (SLAM 및 장애물 감지) |
| | Power | **XL4016 / XL4015** | 각 1 | Buck Converter (전압 강하, MCU/센서 전원) |
| | Power | **LTC3780** | 1 | Buck-Boost Module (전압 안정화, Jetson 전원) |
| **Tier 3**<br>(AI & Main) | Main Board | **NVIDIA Jetson Orin Nano** | 1 | 메인 컴퓨터 (ROS2, 객체 인식, LLM/TTS 구동) |
| | Actuator | **So Arm 101** | 1 | 다관절 로봇팔 (상호작용 및 조작) |
| | Feeder | **Custom 3D Print** | 1 | 사료 급식통 (서보모터 제어) |
| | Battery | **3S LiPo 5000mAh** | 1 | 11.1V 대용량 배터리 (전체 전원 공급) |
| | BMS | **3S BMS Module** | 1 | 배터리 보호 회로 (과충전/과방전 방지) |

### 1.4 하드웨어 배선 및 핀 맵핑 (Hardware Wiring & Pin Mapping)

본 로봇은 **STM32F446RE (Nucleo-64)** 를 하위 제어기로 사용하며, 전원부와 제어 신호는 아래 아키텍처에 따라 연결됩니다.

#### 1) 전원 아키텍처 (Power Architecture)
3S LiPo 배터리(12.6V)를 메인 전원으로 사용하며, 노이즈 간섭 최소화를 위해 3단 분리 전원 시스템을 구축했습니다.

| 층 (Tier) | 역할 | 구성 요소 및 설명 |
| :--- | :--- | :--- |
| **Tier 1**<br>(Drive) | **구동 전원** | **12.6V Raw Power**<br>- 배터리 직결 → MDD10A 모터 드라이버 공급<br>- 모터의 최대 토크 확보를 위해 감압 없이 사용 |
| **Tier 2**<br>(Regulated) | **변환 전원** | **DC-DC Converter**<br>- **XL4016**: 12.6V → **5.1V** (SBC: Jetson/RPi 전용)<br>- **XL4015**: 12.6V → **5.0V** (STM32, 센서, 로직용)<br>- **LTC3780**: 12.6V → **12.0V** (로봇팔 서보모터 정격 전압 유지) |
| **Tier 3**<br>(Source) | **메인 전원** | **Battery & BMS**<br>- 3S LiPo 배터리 및 보호회로(BMS) 탑재<br>- 전체 시스템의 전력 원천 |

* **Common Ground**: 전위차로 인한 통신 오류 방지를 위해 모든 모듈의 GND를 통합했습니다.
* **Voltage Monitoring**: 배터리 전압(12.6V)을 ADC 안전 범위(3.3V)로 맞추기 위해 **10kΩ:3.3kΩ 분배 저항**을 적용했습니다. (6V 입력 시 약 1.48V 측정)

---

#### 2) STM32F446RE 핀 할당 (Pin Mapping)

하위 제어기(OpenCR/Nucleo)와 각 센서/액추에이터 간의 핀 연결 상세입니다.

**① DC 모터 제어 (Mecanum Wheel Drive)**
* **제어 방식:** PWM (속도) + GPIO (방향)
* **PWM 주파수:** 20kHz

| 모터 위치 | PWM Pin (TIM8) | DIR Pin (GPIO) |
| :--- | :--- | :--- |
| **Front Left (FL)** | **PC6** (CH1) | **PB0** |
| **Front Right (FR)** | **PC7** (CH2) | **PB1** |
| **Rear Left (RL)** | **PC8** (CH3) | **PB2** |
| **Rear Right (RR)** | **PC9** (CH4) | **PB10** |

**② 엔코더 피드백 (Encoder Feedback)**
* **방식:** Quadrature Encoder Mode

| 모터 위치 | Phase A | Phase B | Timer |
| :--- | :--- | :--- | :--- |
| **FL Encoder** | PA0 | PA1 | TIM2/5 |
| **FR Encoder** | PB6 | PB7 | TIM4 |
| **RL Encoder** | PA6 | PA7 | TIM3 |
| **RR Encoder** | PA8 | PA9 | TIM1 |

**③ 로봇팔 및 서보모터 (Actuators)**
* **PWM 주파수:** 50Hz (Period 20ms)

| 기능 | Pin Name | 비고 |
| :--- | :--- | :--- |
| **주사기 제어** | **PB14** | 180° 서보모터 |
| **급식기 제어** | **PB15** | 360° 서보모터 (연속회전) |

**④ 통신 및 센서 (Communication & Sensors)**

| 기능 | Interface | Pin (TX/SCL) | Pin (RX/SDA) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| **ROS2 Comm** | **UART4** | **PC10** | **PC11** | 상위 제어기(Jetson)와 통신 |
| **IMU Sensor** | **I2C1** | **PB8** | **PB9** | BNO085/MPU6050 (자세제어) |
| **Debug Log** | **USART2** | **PA2** | **PA3** | ST-Link 디버깅 콘솔 |

> **참고:** IMU 센서의 인터럽트 핀은 `PC13`, 리셋 핀은 `PC14`에 할당되어 있습니다.
---

## 2. 프로젝트 구조 및 설정 파일

GitLab 소스 클론 후, 배포를 위해 필요한 디렉토리 구조 및 설정 파일 목록입니다.

### 2.1 디렉토리 구조

```text
(Root)
├── exec/                       # [제출용] 실행 파일 폴더
│   ├── 포팅매뉴얼.md
│   ├── 시연시나리오.md
│   └── DB_Dump.sql             # DB 초기 데이터 덤프
├── docker-compose.yml          # 전체 서비스 구성
├── .env                        # [생성 필요] 통합 환경 변수
├── nginx/
│   └── default.conf            # Nginx 라우팅 설정
├── server/                     # Backend Source
│   └── src/main/resources/application.yml
├── client/                     # Frontend Source
│   └── .env                    # [생성 필요] 프론트 환경 변수
└── cosvoice_models/            # (자동 생성) AI 모델 캐시 폴더

```

### 2.2 환경 변수 설정 (Environment Variables)

**1) Root 경로 `.env` 파일 (인프라/백엔드 공통)**
프로젝트 최상위 경로에 `.env` 파일을 생성하고 아래 내용을 작성합니다. `docker-compose.yml`과 `application.yml`이 이 파일을 참조합니다.

```ini
# Database (PostgreSQL)
SPRING_DATASOURCE_USERNAME=myuser       # DB 접속 ID
SPRING_DATASOURCE_PASSWORD=mypassword   # DB 접속 PW

# JWT Security
JWT_SECRET=v3ryS3cr3tK3yF0rJwTTokenGeneraTionMustBeLongEnough  # 32자 이상 필수

# MQTT Broker (Mosquitto)
MQTT_USERNAME=ssafy                     # application.yml 설정과 일치해야 함
MQTT_PASSWORD=ssafy1                    # application.yml 설정과 일치해야 함

# Jetson Connection (Optional)
JETSON_VOICE_URL=http://jetson-ip:port  

```

**2) `client` 폴더 내 `.env` 파일 (프론트엔드)**
`client/.env` 파일을 생성합니다. 빌드 시점에 적용됩니다.

```ini
VITE_API_URL=/api                       # API 서버 주소 (Proxy)
VITE_WEBSOCKET_URL=wss://i14c203.p.ssafy.io/ws   # 소켓 주소 (SSL 적용)
VITE_SIGNALING_URL=wss://i14c203.p.ssafy.io/signal # WebRTC 시그널링

```

---

## 3. 빌드 및 배포 가이드

### 3.1 사전 필수 설치 (Prerequisites)

서버에 Docker와 **NVIDIA Container Toolkit**이 반드시 설치되어 있어야 합니다.

```bash
# 1. Docker 설치
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 2. NVIDIA Container Toolkit 설치 (AI 서비스 GPU 할당용) ⭐ 중요
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

```

### 3.2 SSL 인증서 발급 (Certbot)

Nginx가 HTTPS(`443`)로 구동되므로, **Docker 실행 전** 인증서가 호스트에 존재해야 합니다.

```bash
# 80 포트가 비어있는지 확인 후 실행
sudo certbot certonly --standalone -d i14c203.p.ssafy.io

```

* 발급 경로 확인: `/etc/letsencrypt/live/i14c203.p.ssafy.io/`

### 3.3 전체 서비스 빌드 및 실행

프로젝트 루트 경로에서 아래 명령어를 실행합니다.

```bash
# 백그라운드 모드로 빌드 및 실행
docker compose up -d --build

# 실행 로그 확인 (Backend)
docker compose logs -f robot_server

```

### 3.4 배포 시 특이사항

1. **AI 모델 다운로드:** `cosyvoice_service` 컨테이너는 최초 실행 시 `ModelScope`에서 약 4GB 크기의 모델을 다운로드합니다. 첫 실행 시 **5~10분 정도 소요**될 수 있습니다.
2. **포트 개방:** 방화벽(EC2 Security Group)에서 다음 포트를 허용해야 합니다.
* `80` (HTTP), `443` (HTTPS)
* `1883` (MQTT TCP), `9001` (MQTT WS)
* `8554` (WebRTC Streaming)



---

## 4. 외부 서비스 정보

프로젝트 구동에 사용되는 외부 서비스 및 API 정보입니다.

| 서비스명 | 용도 | 비고 |
| --- | --- | --- |
| **ModelScope** | AI 모델 저장소 | CosyVoice 구동 시 `FunAudioLLM/Fun-CosyVoice3-0` 모델 자동 다운로드 |
| **Jetson Nano** | Edge Device | 로컬 네트워크 통신 (음성 인식/처리) |
| **LetsEncrypt** | SSL 인증서 | HTTPS 보안 통신 적용 |

---

## 5. DB 접속 정보

`docker-compose.yml`에 정의된 DB 접속 정보입니다.

* **DBMS**: PostgreSQL 15
* **Port**: 5432
* **Database**: `robot_db`
* **User/PW**: `.env` 파일의 `SPRING_DATASOURCE_USERNAME`, `PASSWORD` 값 참조
* **Dump File**: `exec/DB_Dump.sql` (초기 데이터)

---

## 6. 시연 시나리오

### 6.1 접속 및 로그인

1. PC 또는 모바일 브라우저에서 `https://i14c203.p.ssafy.io` 접속.
2. 로그인 페이지에서 테스트 계정(`admin@admin.com`/`admin1234`)으로 로그인.

### 6.2 로봇 상태 모니터링 (Dashboard)

1. 메인 대시보드 진입.
2. **[Connection Status]** 패널 확인:
* `Server`: Online (초록불)
* `MQTT`: Connected (초록불)


3. **[Battery]** 및 **[Robot Status]** 실시간 데이터 갱신 확인.

### 6.3 로봇 제어 및 영상 스트리밍

1. 화면 중앙 **조이스틱(Joystick)** 컴포넌트 조작 -> 로봇 이동 확인.
2. **[Real-time View]** 패널에서 로봇 카메라 영상이 지연 없이(WebRTC) 출력되는지 확인.
3. **[식당]** 패널의 '츄르 주기' 버튼 클릭 -> 우측 상단 Toast 알림 및 로봇 동작 확인.

### 6.4 AI 음성 합성 (TTS)

1. **[음성 제어 센터]** 패널로 이동.
2. 텍스트 입력창에 "안녕하세요, 반가워요" 입력 후 재생 버튼 클릭.
3. 서버(GPU)에서 생성된 음성이 브라우저를 통해 재생되는지 확인.

---

**작성일:** 2026. 02. 09.
**작성자:** C203팀 
