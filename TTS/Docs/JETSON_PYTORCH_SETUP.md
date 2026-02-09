# Jetson 초기 PyTorch + CosyVoice 추론 환경 (JetPack 6.2)

**CosyVoice TTS 추론만** Jetson에서 돌릴 때 사용.  
토큰 추출(extract_tokens)은 서버에서 하므로 Jetson에는 **추론용 패키지만** 설치.

- **초기 PyTorch만** 설치하려면 **0~4단계**만 실행하면 됨.  
- CosyVoice TTS 서버까지 쓰려면 **5단계**까지 진행.

---

## 한 번에 실행 (초기 PyTorch만, 0~4단계)

아래 블록을 그대로 복사해 터미널에서 실행하면 **초기 PyTorch 설치까지** 끝남. (venv 이름: `cosyvoice-jp62`)

```bash
# 0) (권장) venv 만들기 – CosyVoice 추론용
python3 -m venv ~/venvs/cosyvoice-jp62
source ~/venvs/cosyvoice-jp62/bin/activate

# 1) 기본 의존성
sudo apt-get update
sudo apt-get install -y python3-pip libopenblas-base libopenmpi-dev libomp-dev

# 2) 기존 torch가 있으면 제거 (CPU-only 들어가 있는 경우가 흔함)
python3 -m pip uninstall -y torch torchvision torchaudio

# 3) pip/필수 패키지
python3 -m pip install -U pip
python3 -m pip install 'Cython<3' numpy

# 4) JetPack 6.2 (CUDA 12.6) 용 인덱스에서 설치 (torch 2.8 ↔ torchvision 0.23 쌍)
python3 -m pip install \
  torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
  --extra-index-url https://pypi.jetson-ai-lab.io/jp6/cu126
```

이후 CosyVoice TTS 서버를 쓰려면 **5단계** 패키지 설치 후, 모델·코드 복사 및 서버 실행을 진행하면 됨.

---

## 0) (권장) venv 만들기

CosyVoice 전용 가상환경 하나로 관리.

```bash
python3 -m venv ~/venvs/cosyvoice-jp62
source ~/venvs/cosyvoice-jp62/bin/activate
```

---

## 1) 기본 의존성

```bash
sudo apt-get update
sudo apt-get install -y python3-pip libopenblas-base libopenmpi-dev libomp-dev
```

---

## 2) 기존 torch 제거 (CPU-only 등이 깔려 있으면)

```bash
python3 -m pip uninstall -y torch torchvision torchaudio
```

---

## 3) pip / 필수 패키지

```bash
python3 -m pip install -U pip
python3 -m pip install 'Cython<3' numpy
```

---

## 4) JetPack 6.2 (CUDA 12.6) 용 PyTorch 설치

Jetson용 인덱스에서 **torch / torchvision / torchaudio**만 설치.  
(CosyVoice 추론은 `torch`·`torchaudio`만 사용. `torchvision`은 인덱스 호환용이라 0.23.0으로 두고, torch 2.8.0과 버전 쌍을 맞춤 — 0.24.0은 torch 2.9 요구.)

```bash
python3 -m pip install \
  torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
  --extra-index-url https://pypi.jetson-ai-lab.io/jp6/cu126
```

**여기까지가 “초기 PyTorch 설치”.**  
CosyVoice TTS 서버를 띄우려면 아래 5단계까지 진행.

---

## 5) CosyVoice TTS 추론 전용 패키지

`extract_tokens_api.py` / JetsonInferenceEngine + FastAPI 서버용.  
(deepspeed·gradio·modelscope 등은 제외, 추론에만 필요한 것만.)

```bash
python3 -m pip install \
  'HyperPyYAML==1.2.2' \
  'transformers' \
  'fastapi' \
  'uvicorn' \
  'wetext==0.0.4' \
  'inflect==7.3.1' \
  'ruamel.yaml<0.18'
```

| 패키지 | 용도 |
|--------|------|
| HyperPyYAML | cosyvoice3.yaml 로드 |
| transformers | Qwen 토크나이저 (CosyVoice-BlankEN) |
| fastapi / uvicorn | `/synthesize`, `/voices/upload_token` API 서버 |
| wetext | 텍스트 정규화 (한/영) |
| inflect | wetext 의존 |
| ruamel.yaml | HyperPyYAML 호환 |

---

## 6) (선택) ONNX Runtime

Jetson에서 **추론만** 할 경우 필수는 아님. CosyVoice 코드가 onnxruntime를 import할 수 있어서, 에러 나면 설치:

```bash
python3 -m pip install onnxruntime
```

(Jetson용 onnxruntime-gpu wheel이 따로 있을 수 있음. 필요 시 해당 문서 참고.)

---

## 요약

| 단계 | 내용 |
|------|------|
| 0 | venv 생성·활성화 (`cosyvoice-jp62`) |
| 1 | apt 기본 의존성 |
| 2 | 기존 torch 제거 |
| 3 | pip, Cython, numpy |
| 4 | **Jetson용 torch/torchvision/torchaudio** (jp6 cu126) ← 초기 PyTorch 여기까지 |
| 5 | **CosyVoice TTS 추론용** (HyperPyYAML, transformers, fastapi, uvicorn, wetext, inflect, ruamel.yaml) |
| 6 | (선택) onnxruntime |

이후 CosyVoice 모델 파일(`llm.pt`, `flow.pt`, `hift.pt`, `CosyVoice-BlankEN/`)과 추론 코드를 Jetson에 복사한 뒤, 같은 venv에서 서버 실행하면 됨.
