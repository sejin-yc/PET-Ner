FROM python:3.10-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    git \
    g++ \
    make \
    wget \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 설치 (static build 다운로드)
RUN wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar -xf ffmpeg-release-amd64-static.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-*-amd64-static* \
    && ffmpeg -version

# Python 의존성 먼저 설치 (CosyVoice requirements.txt 사용)
COPY CosyVoice/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ruamel.yaml 버전 호환성 문제 해결 (HyperPyYAML과 호환되는 버전)
RUN pip install --no-cache-dir "ruamel.yaml<0.18"

# CosyVoice 디렉토리 복사
COPY CosyVoice /app/CosyVoice

# 음성 토큰 추출 서비스 복사
COPY S14P11C203/cosyvoice_service/extract_tokens_api.py /app/extract_tokens_api.py

EXPOSE 50001

CMD ["python", "extract_tokens_api.py"]
