# 🤖 Intelligent Robot Dashboard Project

**지능형 로봇을 웹에서 실시간으로 관제하고 제어하는 통합 대시보드 프로젝트**입니다.
Docker Compose를 기반으로 마이크로서비스 아키텍처를 구축하였으며, MQTT 프로토콜을 이용한 실시간 통신 및 Jenkins를 활용한 원클릭 배포 시스템을 갖추고 있습니다.

---

## 🏗 System Architecture (시스템 아키텍처)

이 프로젝트는 **Docker Compose**를 통해 5개의 컨테이너가 유기적으로 연결되어 동작합니다.

| 서비스명 | 컨테이너 이름 | 역할 | 포트 | 비고 |
| --- | --- | --- | --- | --- |
| **Frontend** | `robot_client` | React 기반 웹 대시보드 (Nginx) | `80` | 사용자 UI 제공 |
| **Backend** | `robot_server` | Spring Boot API 서버 | `8080` | 비즈니스 로직, DB/MQTT 연동 |
| **Broker** | `robot_mqtt` | Eclipse Mosquitto | `1883` | 로봇-서버-클라이언트 메시지 중계 |
| **Database** | `robot_db` | PostgreSQL 15 | `5432` | 사용자, 로그, 비디오 데이터 저장 |
| **Jenkins** | `jenkins` | CI/CD 자동화 서버 | `9090` | 배포 파이프라인 관리 |

---

## 🛠 Tech Stack (기술 스택)

* **Frontend**: React, Nginx, Axios, WebSocket
* **Backend**: Java 17, Spring Boot 3.x, Spring Data JPA, Spring Security
* **Database**: PostgreSQL 15
* **Infra & DevOps**: AWS EC2, Docker, Docker Compose, Jenkins
* **Communication**: MQTT (Eclipse Mosquitto)

---

## 🏃 How to Run (실행 가이드)

### 1. 🏠 Local Environment (로컬 개발 환경)

개발자 PC(Windows/Mac)에서 프로젝트를 실행하는 방법입니다.

**전제 조건**

* Docker Desktop 및 Git 설치 필요

**실행 단계**

```bash
# 1. 프로젝트 클론
git clone https://lab.ssafy.com/s14-webmobile3-sub1/S14P11C203.git
cd S14P11C203

# 2. 통합 브랜치 체크아웃
git checkout FE,BE,Infra

# 3. 전체 서비스 실행 (백그라운드 모드)
docker compose up -d --build

```

**접속 주소**

* Frontend: `http://localhost:80`
* Backend: `http://localhost:8080`
* Jenkins: `http://localhost:9090`

> **💡 주의사항 (IDE 실행 시)**
> IntelliJ나 VS Code에서 Spring Boot만 단독 실행할 경우, `application.yml`의 DB/MQTT 주소를 컨테이너 이름(`robot_db`)이 아닌 `localhost`로 변경해야 합니다.

### 2. ☁️ AWS EC2 Server (서버 배포 환경)

AWS EC2(Ubuntu) 환경에서 서비스를 운영하는 방법입니다.

**최초 설정**

```bash
# 1. Docker 설치 및 권한 부여
sudo apt-get update && sudo apt-get install docker.io docker-compose-plugin -y
sudo usermod -aG docker $USER
newgrp docker

# 2. 프로젝트 실행
git clone https://lab.ssafy.com/s14-webmobile3-sub1/S14P11C203.git
cd S14P11C203
sudo docker compose up -d --build

```

**배포 및 업데이트 (Deployment)**

* 이 프로젝트는 **Jenkins**를 통해 배포 자동화가 구축되어 있습니다.
* 소스 코드를 `FE,BE,Infra` 브랜치에 Push한 후, **Jenkins 대시보드에서 `Build Now` 버튼을 클릭**하면 배포가 시작됩니다.
* 터미널에 접속하여 수동으로 명령어를 입력할 필요가 없습니다.

---

## 🔄 CI/CD Pipeline (Jenkins)

안정적인 배포를 위해 Jenkins 파이프라인 스크립트가 구성되어 있습니다.

### 배포 프로세스 (Workflow)

1. **Code Push**: 개발자가 GitLab에 코드를 업로드합니다.
2. **Manual Trigger**: Jenkins 관리자가 **[Build Now]** 버튼을 클릭합니다.
3. **Git Pull**: Jenkins가 `FE,BE,Infra` 브랜치의 최신 코드를 가져옵니다.
4. **Docker Cleanup**: 충돌 방지를 위해 기존 컨테이너(`robot_server`, `robot_mqtt` 등)를 **강제 삭제**합니다.
5. **Build & Up**: 최신 코드로 이미지를 빌드하고 컨테이너를 재실행합니다.

---

## 📂 Project Structure (폴더 구조)

```bash
S14P11C203
├── client/                 # React Frontend Source
│   ├── Dockerfile
│   └── nginx.conf
├── server/                 # Spring Boot Backend Source
│   ├── src/main/resources/application.yml  # 설정 파일
│   └── Dockerfile
├── jenkins_home/           # Jenkins Data Volume
├── docker-compose.yml      # Container Orchestration
└── README.md

```

---

## ⚠️ Troubleshooting (트러블슈팅)

### Q1. 502 Bad Gateway 에러가 발생해요.

* **원인**: Spring Boot 서버가 아직 부팅 중이거나, 에러로 인해 컨테이너가 종료된 상태입니다.
* **해결**: 약 30초 대기 후 새로고침하거나, `docker logs robot_server`로 에러 로그를 확인하세요.

### Q2. MQTT 연결 실패 (Connection Refused)

* **원인**: 백엔드 서버가 브로커의 주소를 찾지 못하는 경우입니다.
* **해결**: `application.yml` 파일의 `mqtt.broker-url`이 `tcp://robot_mqtt:1883`으로 설정되어 있는지 확인하세요. (Localhost 아님)

### Q3. "Bind for 0.0.0.0:1883 failed" 에러

* **원인**: 기존에 실행된 `mqtt_broker` 컨테이너가 포트를 점유하고 있어서 발생합니다.
* **해결**: Jenkins 파이프라인의 Cleanup 단계가 이를 자동으로 처리하지만, 수동 해결 시 `docker rm -f mqtt_broker`를 입력하세요.

---

## 👨‍💻 Team Members

* **Front-End**: (이름)
* **Back-End**: (이름)
* **Infra/DevOps**: (본인 이름)
* **Embedded**: (이름)

---

Copyright © 2026 Robot Project Team. All Rights Reserved.