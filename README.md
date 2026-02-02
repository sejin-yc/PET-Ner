# 🤖 Intelligent Robot Dashboard (지능형 로봇 관제 시스템)

**자율주행 로봇의 실시간 모니터링, 원격 제어(WebRTC) 및 데이터 분석을 위한 웹 기반 통합 관제 플랫폼**입니다.
Nginx를 게이트웨이로 활용한 마이크로서비스 아키텍처로 설계되었으며, HTTPS 보안 통신과 MQTT를 이용한 실시간 로봇 제어를 지원합니다.

---

## 🏗 System Architecture (시스템 아키텍처)

이 프로젝트는 **Nginx Gateway**를 중심으로 5개의 컨테이너가 유기적으로 연결되어 동작합니다.

| 서비스명 | 컨테이너 이름 | 역할 | 포트 (Host:Container) | 비고 |
| --- | --- | --- | --- | --- |
| **Gateway** | `robot_nginx` | Reverse Proxy & SSL Termination | `80`, `443` | 모든 트래픽의 진입점 (HTTPS) |
| **Frontend** | `robot_client` | React 웹 서버 (Nginx Upstream) | (Internal) | Nginx를 통해서만 접근 |
| **Backend** | `robot_server` | Spring Boot API & WebSocket | `8080:8080` | 비즈니스 로직, WebRTC 시그널링 |
| **Broker** | `robot_mqtt` | Eclipse Mosquitto | `1883:1883` | 로봇-서버 간 메시지 중계 (ROS2) |
| **Database** | `robot_db` | PostgreSQL 15 | `5432:5432` | 사용자, 로그, 영상 메타데이터 저장 |

---

## 🛠 Tech Stack (기술 스택)

### **Frontend**

* **Core**: React (Vite), JavaScript
* **Styling**: Tailwind CSS v4, Lucide React
* **State Mgmt**: Context API (Auth, Robot, Notification)
* **Visualization**: Recharts (데이터 시각화), React-Joystick-Component
* **Communication**: Axios, WebSocket (StompJS), **WebRTC (영상 스트리밍)**

### **Backend**

* **Core**: Java 17, Spring Boot 3.x
* **Security**: Spring Security, JWT, BCrypt
* **Database**: PostgreSQL 15, JPA (Hibernate)
* **Messaging**: Spring Integration MQTT, WebSocket
* **API Docs**: Swagger (SpringDoc OpenAPI)

### **Infra & DevOps**

* **Server**: AWS EC2 (Ubuntu)
* **Container**: Docker, Docker Compose
* **Gateway**: Nginx (Load Balancing, SSL/TLS)
* **CI/CD**: Jenkins (Automated Deployment)

---
## 🏃 How to Run (실행 가이드)

이 프로젝트를 처음 실행하시는 분들을 위한 **상세 가이드**입니다.
소스 코드를 내려받고 실행하기까지의 모든 과정을 순서대로 따라와 주세요.

### 0. ⚙️ Prerequisites (사전 준비)

프로젝트 실행을 위해 아래의 필수 프로그램들이 설치되어 있어야 합니다.
설치되어 있지 않다면 링크를 통해 다운로드 및 설치를 먼저 진행해 주세요.

1. **Git** (소스 코드 다운로드용)
* [Git 다운로드](https://www.google.com/search?q=https://git-scm.com/downloads)
* 설치 후 터미널(CMD)에서 `git --version` 입력 시 버전이 나오면 성공.


2. **Docker Desktop** (서버/DB/MQTT 실행용)
* [Docker Desktop 다운로드](https://www.docker.com/products/docker-desktop/)
* **중요**: 설치 후 반드시 **Docker Desktop을 실행**시켜 두어야 합니다. (고래 아이콘 확인)


3. **Node.js (LTS 버전)** (프론트엔드 실행용)
* [Node.js 다운로드](https://nodejs.org/) (Recommended for Most Users 버전 권장)
* 설치 후 터미널에서 `node -v`, `npm -v` 입력 시 버전이 나오면 성공.



---

### 1. 📥 Clone Repository (프로젝트 다운로드)

원하는 폴더에서 터미널(CMD, PowerShell, Git Bash 등)을 열고 아래 명령어를 입력합니다.

```bash
# 1. 프로젝트 복제하기
git clone https://lab.ssafy.com/s14-webmobile3-sub1/S14P11C203.git

# 2. 프로젝트 폴더로 이동
cd S14P11C203

```

---

### 2. 🏠 Local Development Mode (로컬 개발 환경 실행)

가장 추천하는 실행 방식입니다.
**백엔드/DB/MQTT**는 도커 컨테이너로 띄우고, **프론트엔드(React)**는 로컬에서 실행하여 빠른 개발 및 디버깅이 가능합니다.

#### **Step 1: 백엔드 및 인프라 실행 (Docker)**

프로젝트 루트 폴더(`S14P11C203`)에서 아래 명령어를 실행합니다.

```bash
# DB, MQTT, 백엔드 서버만 실행 (Nginx와 Client는 제외)
docker compose up -d --build robot_db robot_mqtt robot_server

```

> **⏳ 기다려주세요!**
> 처음 실행 시 이미지를 다운로드하고 Spring Boot 서버가 켜지는 데 **약 1~2분** 정도 소요될 수 있습니다.
> `docker logs -f robot_server` 명령어로 로그를 확인했을 때, `Started ServerApplication` 메시지가 뜨면 준비 완료입니다.

#### **Step 2: 프론트엔드 설정 변경 (API 주소)**

로컬에서 실행할 때는 Nginx를 거치지 않고 백엔드 API와 직접 통신해야 합니다.
`client/src/api/axios.js` 파일을 텍스트 에디터(VS Code, 메모장 등)로 열어 아래와 같이 수정해 주세요.

```javascript
// client/src/api/axios.js

const api = axios.create({
  // baseURL: 'https://i14c203.p.ssafy.io/api',  // <-- 기존 배포용 주소는 주석 처리(//)
  baseURL: 'http://localhost:8080/api',         // <-- 로컬용 주소 주석 해제
  headers: { 'Content-Type': 'application/json' },
});

```

#### **Step 3: 프론트엔드 실행**

새로운 터미널 창을 열고 아래 명령어를 순서대로 입력합니다.

```bash
# 1. client 폴더로 이동
cd client

# 2. 필요한 라이브러리 설치 (최초 1회 필수)
npm install

# 3. 리액트 개발 서버 실행
npm run dev

```

#### **Step 4: 접속 확인**

브라우저(Chrome 권장)를 열고 아래 주소로 접속합니다.

* **웹 대시보드**: [http://localhost:5173](https://www.google.com/search?q=http://localhost:5173)
* **API 문서 (Swagger)**: [http://localhost:8080/swagger-ui/index.html](https://www.google.com/search?q=http://localhost:8080/swagger-ui/index.html)

---

### 3. ☁️ Production Mode (배포 환경 시뮬레이션)

실제 서버와 동일하게 **Nginx를 포함한 모든 서비스**를 도커로 실행하는 방법입니다.
(HTTPS 인증서 설정이 되어 있지 않다면 로컬에서는 정상 동작하지 않을 수 있으니 주의하세요.)

1. `client/src/api/axios.js`의 `baseURL`을 배포용 도메인(`https://...`)으로 원복합니다.
2. 프로젝트 루트에서 아래 명령어를 실행합니다.

```bash
# 기존 컨테이너 종료 및 삭제
docker compose down

# 전체 서비스 빌드 및 실행
docker compose up -d --build

```

---

### 4. 🧹 종료 및 정리 (Clean Up)

실행 중인 모든 서비스를 종료하고 싶다면 아래 명령어를 사용하세요.

```bash
# 컨테이너 종료 및 네트워크 정리
docker compose down

# (선택) DB 데이터까지 초기화하고 싶다면
docker compose down -v

```
## 📂 Project Structure (폴더 구조)

```bash
S14P11C203
├── client/                 # React Frontend (Vite)
├── server/                 # Spring Boot Backend
├── nginx/                  # Nginx Gateway Config
│   └── conf.d/default.conf # 리버스 프록시 및 라우팅 설정
├── mosquitto/              # MQTT Broker Config
├── certbot/                # SSL 인증서 저장소
└── docker-compose.yml      # 전체 컨테이너 오케스트레이션

```

---

## ⚠️ Troubleshooting (트러블슈팅)

### Q1. 차트 에러 (Recharts width -1)

* **현상**: 콘솔에 `The width(-1) of chart should be greater than 0` 에러 발생.
* **원인**: 브라우저 렌더링 타이밍 문제입니다.
* **해결**: 기능상 문제는 없으나, `ResponsiveContainer`의 `width`를 `99%`로 설정하거나 부모 div에 고정 높이(`style={{height: '250px'}}`)를 주면 해결됩니다.

### Q2. 404 Not Found (API 요청 실패)

* **원인**: 프론트엔드는 `/api/logs`로 요청하지만, 백엔드에는 `/user/logs`로 매핑되어 있을 수 있습니다.
* **해결**: Nginx의 `rewrite` 설정이 올바르게 적용되었는지 확인하거나, 로컬 실행 시 `axios.js`의 경로를 확인하세요.

### Q3. 502 Bad Gateway

* **원인**: 백엔드(`robot_server`)가 부팅 중이거나 DB 연결 실패로 다운된 상태입니다.
* **해결**: `docker logs -f robot_server`로 에러 로그를 확인하세요. (DB 비밀번호나 MQTT URL 확인 필요)

---

## 👨‍💻 Team Members

* **Front-End**: (이름)
* **Back-End**: (이름)
* **Infra/DevOps**: (본인 이름)
* **Embedded/ROS**: (이름)

---

Copyright © 2026 Robot Project Team. All Rights Reserved.