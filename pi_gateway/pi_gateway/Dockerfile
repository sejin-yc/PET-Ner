FROM ros:humble-desktop

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ROS2 Python 패키지 설치
RUN apt-get update && apt-get install -y \
    ros-humble-rclpy \
    ros-humble-geometry-msgs \
    ros-humble-nav-msgs \
    ros-humble-sensor-msgs \
    ros-humble-std-msgs \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt requirements_ros.txt ./

# Python 의존성 설치
RUN pip3 install --no-cache-dir -r requirements.txt

# ROS2 의존성은 apt로 설치되므로 requirements_ros.txt는 참고용

# 소스 코드 복사
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# 실행 권한 부여
RUN chmod +x scripts/*.sh 2>/dev/null || true

# 환경 변수 설정
ENV ROS_DOMAIN_ID=1
ENV PYTHONPATH=/app:/app/src:${PYTHONPATH}
ENV ROS_DISTRO=humble

# 기본 포트 (FastAPI)
EXPOSE 8000

# 진입점
CMD ["python3", "-m", "src.main"]
