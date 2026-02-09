# GPU 지원: PyTorch CUDA 이미지 사용
# -devel: DeepSpeed pip 설치 시 nvcc 필요 (runtime 이미지에는 nvcc 없음)
# CPU만 사용할 경우 python:3.10-slim 으로 변경 가능
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-devel

ENV CUDA_HOME=/usr/local/cuda
ENV DS_BUILD_OPS=0

WORKDIR /app

# 시스템 패키지 설치 (일시적 미러 400 오류 시 재시도)
RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    git g++ make wget xz-utils \
    || (apt-get update && apt-get install -y --no-install-recommends --fix-missing git g++ make wget xz-utils) \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 설치 (static build 다운로드)
RUN wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar -xf ffmpeg-release-amd64-static.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-*-amd64-static* \
    && ffmpeg -version

# Python 의존성 설치 (CosyVoice requirements.txt 사용)
# PyTorch는 이미 베이스 이미지에 포함되어 있으므로 torch 관련은 건너뜀
COPY CosyVoice/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ruamel.yaml 버전 호환성 문제 해결 (HyperPyYAML과 호환되는 버전)
RUN pip install --no-cache-dir "ruamel.yaml<0.18"

# Edge TTS (기본 음성용: 한국어 SunHi/InJoon)
RUN pip install --no-cache-dir edge-tts

# CosyVoice 디렉토리 복사
COPY CosyVoice /app/CosyVoice

# 음성 토큰 추출 서비스 복사
COPY S14P11C203/cosyvoice_service/extract_tokens_api.py /app/extract_tokens_api.py

EXPOSE 50001

CMD ["python", "extract_tokens_api.py"]
