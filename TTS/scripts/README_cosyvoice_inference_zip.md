# CosyVoice 추론 전용 압축 (Jetson 배포용)

## 스크립트 실행

**CV3-test** 프로젝트 루트에서 실행:

```powershell
cd c:\Users\SSAFY\downtown\mingsung\CV3-test
.\S14P11C203\scripts\pack_cosyvoice_inference.ps1
```

생성 파일: `CV3-test/CosyVoice_inference_only.zip`

## ZIP 내용

| 포함 | 설명 |
|------|------|
| `CosyVoice/cosyvoice/` | 추론에 필요한 코드만 (JetsonInferenceEngine, frontend, model, llm, flow, hifigan, transformer, tokenizer, utils) |
| **제외** | `bin/` (학습·export), `dataset/`, `vllm/` |

- **포함 디렉터리**: `cli/`, `flow/`, `hifigan/`, `llm/`, `tokenizer/`, `transformer/`, `utils/`
- **모델은 ZIP에 없음** → Jetson TTS **추론에만** 쓰는 파일만 옮기면 됨 (폴더 전체 아님).

**Jetson에 넣어야 할 것 (최소)**  
모델 폴더 안에서 아래만 복사/압축해서 Jetson에 두고, `COSYVOICE_MODEL_DIR` 를 그 폴더 경로로 지정.

| 파일/폴더 | 용도 |
|-----------|------|
| `cosyvoice3.yaml` | 설정 |
| `llm.pt` | LLM 가중치 |
| `flow.pt` | Flow 가중치 |
| `hift.pt` | HiFi-GAN 가중치 |
| `CosyVoice-BlankEN/` | 토크나이저 (폴더 통째로) |

**옮기지 않아도 되는 것** (추론에 미사용): `campplus.onnx`, `speech_tokenizer_v3.onnx`, `llm.rl.pt`, `flow.decoder.estimator.*.onnx`, `asset/`, `README.md`, `configuration.json`, `.mdl`, `.msc`, `.mv` 등.

**대략 용량 (최소 5개만)**  
| 항목 | 용량 |
|------|------|
| cosyvoice3.yaml | ~수 KB |
| llm.pt | ~1.9 GB |
| flow.pt | ~1.3 GB |
| hift.pt | ~80 MB |
| CosyVoice-BlankEN/ | ~950 MB |
| **합계** | **약 4.1~4.2 GB** |

Jetson 여유 공간이 **4.1 GB**면 딱 맞거나 약간 부족할 수 있음. **4.5 GB 이상** 여유 있으면 여유 있게 들어감.

**VRAM (GPU 메모리)**  
- 서버 기동 후 TTS 모델 로드 직후 **allocated/peak** 가 로그에 한 번 출력됨 (`VRAM (TTS 모델 로드 직후): allocated=… GB, …`).  
- 추론 시점 VRAM까지 보려면 `LOG_VRAM=1` 로 실행 후 `/synthesize` 한 번 호출하면, 그 요청 직후 VRAM이 한 번 더 로그에 찍힘.  
- CosyVoice 0.5B + FP32 기준 대략 **2~4 GB VRAM** 예상 (FP16 사용 시 더 적을 수 있음). Jetson 모델에 따라 다르므로 실제는 로그로 확인하는 것이 좋음.

## Jetson에서 압축 풀기

ZIP을 `/home/SSAFY/` 에 넣었다고 가정.

**방법 1 – 터미널 (unzip)**

```bash
cd /home/SSAFY
unzip -o CosyVoice_inference_only.zip
```

`-o`: 기존 파일 있으면 덮어쓰기. 풀리면 `CosyVoice/` 폴더가 생김.

**방법 2 – Python 코드로 풀기**

같은 디렉터리에 `unzip_cosyvoice.py` 를 두고 실행 (아래 스크립트 사용).

## Jetson에서 사용 (경로 설정 + 서버 실행)

unzip까지 끝났다면, **같은 디렉터리**에 `extract_tokens_api.py`만 두면 됩니다. 코드에서 이미 `Path(__file__).parent / "CosyVoice"` 로 CosyVoice 경로를 잡으므로, **별도로 `sys.path.insert` 할 필요 없음.**

### 1. 디렉터리 구조

Jetson에서 예시 (`/home/SSAFY/`):

```
/home/SSAFY/
├── CosyVoice/              ← unzip으로 풀린 폴더 (cosyvoice/ 가 안에 있음)
│   └── cosyvoice/
├── CosyVoice_inference_only.zip
└── extract_tokens_api.py   ← 이 파일을 여기 복사
```

`extract_tokens_api.py`는 **CosyVoice와 같은 위치**에 두면 됨 (프로젝트의 `S14P11C203/cosyvoice_service/extract_tokens_api.py` 를 복사).

### 2. 모델 경로 설정

모델 파일(`llm.pt`, `flow.pt`, `hift.pt`, `cosyvoice3.yaml`, `CosyVoice-BlankEN/`)을 Jetson **아무 경로**에 두고, 그 디렉터리의 **절대 경로**를 환경 변수로 지정하면 됨. (`/home/SSAFY/` 안에 둘 필요 없음.)

```bash
# 예: 모델을 /home/SSAFY/ 안에 둔 경우
export COSYVOICE_MODEL_DIR="/home/SSAFY/cosyvoice_models/FunAudioLLM/Fun-CosyVoice3-0___5B-2512"

# 예: 다른 경로에 둔 경우
# export COSYVOICE_MODEL_DIR="/opt/models/Fun-CosyVoice3-0___5B-2512"
```

(실제로 모델을 둔 폴더의 **절대 경로**로 바꿔서 사용.)

### 3. Jetson TTS 전용 모드로 실행

Jetson에서는 토큰 추출 없이 **TTS만** 쓰므로, 아래처럼 실행:

```bash
cd /home/SSAFY
export JETSON_TTS_ONLY=1
export COSYVOICE_MODEL_DIR="/home/SSAFY/cosyvoice_models/FunAudioLLM/Fun-CosyVoice3-0___5B-2512"   # 실제 경로로 변경
python3 extract_tokens_api.py
```

또는 한 줄로:

```bash
cd /home/SSAFY && JETSON_TTS_ONLY=1 COSYVOICE_MODEL_DIR=/home/SSAFY/cosyvoice_models/FunAudioLLM/Fun-CosyVoice3-0___5B-2512 python3 extract_tokens_api.py
```

서버가 뜨면 기본 포트 **50001** 에서 `/synthesize` 등이 동작함. (uvicorn 기본 포트를 바꾸려면 `extract_tokens_api.py` 맨 아래 `uvicorn.run(...)` 에서 `port=50001` 로 지정되어 있는지 확인.)

### 요약

| 항목 | 내용 |
|------|------|
| 경로 | `extract_tokens_api.py` 와 **같은 폴더**에 `CosyVoice/` 가 있으면 됨. 코드에서 자동으로 `CosyVoice` 경로 추가. |
| 환경 변수 | `JETSON_TTS_ONLY=1` (TTS만 사용), `COSYVOICE_MODEL_DIR` (모델 디렉터리 절대 경로) |
| 실행 | `cd /home/SSAFY` 후 위처럼 `python3 extract_tokens_api.py` |

자세한 단계는 `Docs/JETSON_PYTORCH_SETUP.md` 참고.
