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

### 1. 🏠 Local Development (로컬 개발 환경)

개발 효율을 위해 **백엔드/DB/MQTT는 Docker**로 띄우고, **프론트엔드는 로컬(Node.js)**에서 실행하여 Hot-Reloading 기능을 활용하는 **하이브리드 방식**을 권장합니다.

**전제 조건**

* Docker Desktop 및 Node.js(v18+) 설치 필요

**단계 1: 인프라 및 백엔드 실행 (Docker)**
프로젝트 **루트 디렉터리**에서 아래 명령어를 실행하여 DB, MQTT, 백엔드 서버를 먼저 띄웁니다.

```bash
# 1. 프로젝트 클론
git clone https://lab.ssafy.com/s14-webmobile3-sub1/S14P11C203.git
cd S14P11C203

# 2. 백엔드 및 인프라 실행 (Nginx, Client 제외)
docker compose up -d --build robot_db robot_mqtt robot_server

# 3. 실행 확인 (3개의 컨테이너가 Up 상태여야 함)
docker compose ps

```

**단계 2: 프론트엔드 설정 변경**
로컬 개발 시에는 Nginx를 거치지 않고 백엔드(`localhost:8080`)로 직접 요청해야 합니다.
`client/src/api/axios.js` 파일을 열어 `baseURL`을 수정합니다.

```javascript
const api = axios.create({
  // baseURL: 'https://i14c203.p.ssafy.io/api',  // <-- 배포용 (주석 처리)
  baseURL: 'http://localhost:8080/api',         // <-- 로컬용 (주석 해제)
  headers: { 'Content-Type': 'application/json' },
});

```

**단계 3: 프론트엔드 실행 (Node.js)**
새로운 터미널 창을 열고 `client` 폴더로 이동하여 실행합니다.

```bash
cd client
npm install   # 의존성 설치 (최초 1회)
npm run dev   # 개발 서버 실행

```

**접속 주소**

* Frontend: `http://localhost:5173`
* Backend API: `http://localhost:8080/swagger-ui/index.html`

---

### 2. ☁️ Server Deployment (서버 배포 환경)

AWS EC2 등 운영 서버에서는 **Nginx를 포함한 전체 컨테이너**를 실행합니다.

**배포 순서**

1. `client/src/api/axios.js`의 주소를 배포용 도메인(`https://...`)으로 원복합니다.
2. 서버에는 SSL 인증서(`fullchain.pem`, `privkey.pem`)가 `./certbot/conf/live/...` 경로에 있어야 합니다.
3. 전체 서비스를 실행합니다.

```bash
# 전체 서비스 빌드 및 실행 (Nginx 포함)
sudo docker compose up -d --build

```

**접속 주소**

* Dashboard: `https://i14c203.p.ssafy.io` (HTTPS 적용됨)

---

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