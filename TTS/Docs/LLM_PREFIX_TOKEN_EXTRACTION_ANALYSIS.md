# CosyVoice3 토큰 추출 시 LLM 프리픽스의 중요성

CosyVoice3 기반 TTS에서 한국어 발음 품질이 저하되는 근본 원인과 해결 방법을 정리한 문서.

---

## 1. 문제 상황

| 항목 | 내용 |
|------|------|
| **현상** | 기본 토큰으로 생성한 TTS에서 한국어 발음이 중국어처럼 들리거나, 주어진 문장을 제대로 읽지 못함 |
| **비교 대상** | `2_audio_gen.py` (음성 복제 테스트 스크립트)는 동일 모델로 양호한 발음 품질 제공 |
| **초기 시도** | `text_frontend=False` 적용 → 효과 없음, 오히려 품질 저하 |

---

## 2. 근본 원인 발견

### 2.1 1_token_extract.py vs extract_tokens_api.py 비교

음성 복제 시 사용하는 `1_token_extract.py`와 우리 서버의 `extract_tokens_api.py`를 비교한 결과:

| 항목 | 1_token_extract.py (정상) | extract_tokens_api.py (문제) |
|------|---------------------------|------------------------------|
| **prompt_text** | `"You are a helpful assistant.<|endofprompt|>" + 실제텍스트` | 실제텍스트만 |
| **결과** | 한국어 발음 정상 | 중국어 발음 유사, 문장 미인식 |

### 2.2 핵심 발견

```python
# 1_token_extract.py (정상 작동하는 코드)
prompt_text = """You are a helpful assistant.<|endofprompt|>안녕하세요. 저는 열다섯 살 여자입니다. 
인공지능은 사람의 사고, 학습, 문제 해결 능력을 컴퓨터로 구현한 기술입니다."""

# extract_tokens_api.py (문제가 있던 코드)
prompt_text = "안녕하세요. 저는 열다섯 살 여자입니다. ..."  # 프리픽스 누락!
```

**문제**: `extract_tokens_api.py`에서 토큰 추출 시 LLM 프리픽스가 빠져있었음

---

## 3. LLM 프리픽스가 중요한 이유

### 3.1 CosyVoice3는 LLM 기반 TTS

CosyVoice3는 **LLM(Large Language Model) 기반** TTS 시스템이다:

```
CosyVoice3 아키텍처:
┌─────────────────────────────────────────────────┐
│  LLM Core (Large Language Model)                │
│  ├── Instruction Understanding                  │
│  ├── Text-to-Speech Token Generation            │
│  └── Speaker Embedding Integration              │
└─────────────────────────────────────────────────┘
```

일반 TTS와 달리 **Instruction-Following** 방식으로 작동:
- 입력: `[시스템 지시] + [경계 표시] + [실제 텍스트]`
- LLM이 지시를 이해하고 적절한 음성 토큰 생성

### 3.2 프리픽스의 3가지 역할

#### 역할 1: 작업 컨텍스트 제공

```
"You are a helpful assistant."
```

- LLM에게 **"나는 도움을 주는 어시스턴트다"** 라는 역할 부여
- 모델이 TTS 작업임을 인지하게 함

#### 역할 2: 프롬프트 경계 표시

```
"<|endofprompt|>"
```

- **시스템 지시**와 **사용자 텍스트** 사이의 경계 표시
- LLM이 어디까지가 지시이고 어디부터가 합성할 텍스트인지 구분
- 이 토큰이 없으면 모델이 텍스트를 지시문의 일부로 오해할 수 있음

#### 역할 3: 학습 데이터와의 일관성

```
# CosyVoice3 학습 시 사용된 포맷:
"You are a helpful assistant.<|endofprompt|>{실제 음성 텍스트}"
```

- 모델이 **학습 시 본 데이터 포맷과 일치**해야 최적 성능 발휘
- 프리픽스 없이 입력하면 학습 분포에서 벗어나 예측 불가능한 결과 발생

### 3.3 일반 TTS vs LLM 기반 TTS 비교

| 구분 | 일반 TTS | LLM 기반 TTS (CosyVoice3) |
|------|----------|---------------------------|
| 입력 형식 | 텍스트만 | Instruction + 경계 + 텍스트 |
| 텍스트 해석 | 음소 변환만 | 문맥 이해 후 음성 생성 |
| 화자 임베딩 | 단순 특성 벡터 | 지시문과 함께 해석 |
| 프리픽스 필요성 | 불필요 | **필수** |

---

## 4. 프리픽스 누락 시 발생하는 문제

### 4.1 토큰 추출 단계

```python
# 프리픽스 없이 토큰 추출 시
extractor.extract_speaker_tokens(
    prompt_text="안녕하세요...",  # LLM이 이게 무슨 작업인지 모름
    prompt_wav="sample.wav"
)
```

**결과**: 
- 화자 특성은 추출되지만 **언어/발음 컨텍스트가 누락**
- 토큰에 한국어 발음 정보가 제대로 인코딩되지 않음

### 4.2 음성 합성 단계

```python
# 잘못 추출된 토큰으로 합성
engine.inference_with_tokens(
    text="안녕 고양이?",
    speaker_tokens=bad_tokens  # 컨텍스트 누락된 토큰
)
```

**결과**:
- 중국어 발음과 유사한 출력
- 문장을 제대로 읽지 못함 (토큰이 텍스트 해석 방법을 모름)
- TTS 품질 전반적 저하

---

## 5. 해결 방법

### 5.1 수정된 코드

**파일**: `cosyvoice_service/extract_tokens_api.py`

```python
@app.post("/extract_tokens")
async def extract_tokens(...):
    # ...
    
    # CosyVoice3는 "You are a helpful assistant.<|endofprompt|>" 프리픽스 필요
    # (1_token_extract.py와 동일 - 이 프리픽스가 없으면 한국어 발음이 중국어처럼 됨)
    full_prompt_text = f"You are a helpful assistant.<|endofprompt|>{prompt_text}"
    
    logger.info(f"prompt_text (with prefix): {full_prompt_text[:80]}...")
    
    speaker_tokens = extractor.extract_speaker_tokens(
        prompt_text=full_prompt_text,  # 프리픽스 포함!
        prompt_wav=temp_wav_path
    )
```

### 5.2 변경 전/후 비교

| 단계 | 변경 전 | 변경 후 |
|------|---------|---------|
| `prompt_text` 입력 | `"안녕하세요..."` | `"You are a helpful assistant.<|endofprompt|>안녕하세요..."` |
| 토큰 품질 | 언어 컨텍스트 누락 | 정상적인 한국어 발음 정보 포함 |
| TTS 출력 | 중국어 유사 발음 | 정상적인 한국어 발음 |

---

## 6. 다음 단계: 토큰 재추출

기존에 추출된 모든 기본 토큰은 **프리픽스 없이** 추출되었으므로 재추출 필요.

### 6.1 재추출 대상

```
server/src/main/resources/default_tokens/
├── male_10s.json    ← 재추출 필요
├── male_20s.json    ← 재추출 필요
├── male_30s.json    ← 재추출 필요
├── male_40s.json    ← 재추출 필요
├── male_50s.json    ← 재추출 필요
├── female_10s.json  ← 재추출 필요
├── female_20s.json  ← 재추출 필요
├── female_30s.json  ← 재추출 필요
├── female_40s.json  ← 재추출 필요
├── female_50s.json  ← 재추출 필요
└── neutral.json     ← 재추출 필요
```

### 6.2 재추출 절차

```powershell
# 1. cosyvoice_service 재시작 (수정된 extract_tokens_api.py 적용)
docker compose restart cosyvoice_service

# 2. 토큰 재추출 스크립트 실행
cd S14P11C203/cosyvoice_service
.\extract_default_tokens.ps1

# 3. 결과 검증 (TTS 테스트)
python test_default_tts.py
```

---

## 7. 교훈 및 권장사항

### 7.1 LLM 기반 모델 사용 시 주의점

| 항목 | 설명 |
|------|------|
| **Instruction Format 확인** | 모델 학습 시 사용된 입력 포맷을 반드시 확인 |
| **프리픽스/접미사 유지** | 시스템 지시, 경계 토큰 등을 누락하지 않도록 주의 |
| **예제 코드 참조** | 공식 예제 코드의 입력 형식을 그대로 따라할 것 |

### 7.2 CosyVoice3 사용 시 체크리스트

- [ ] 토큰 추출 시 `"You are a helpful assistant.<|endofprompt|>"` 프리픽스 포함
- [ ] 음성 합성 시 한글 텍스트는 `text_frontend=False` 옵션 고려
- [ ] 공식 `1_token_extract.py`, `2_audio_gen.py` 코드와 입력 형식 비교

---

## 8. 관련 문서

| 문서 | 내용 |
|------|------|
| `KOREAN_TTS_PRONUNCIATION_ANALYSIS.md` | text_frontend 관련 분석 |
| `DEFAULT_TTS_PLAN.md` | 기본 TTS 구현 계획 |

---

## 9. 요약

| 구분 | 내용 |
|------|------|
| **문제** | 한국어 TTS 발음이 중국어처럼 들리고 문장을 제대로 읽지 못함 |
| **근본 원인** | 토큰 추출 시 LLM 프리픽스 `"You are a helpful assistant.<|endofprompt|>"` 누락 |
| **왜 중요한가** | CosyVoice3는 LLM 기반으로, 이 프리픽스가 작업 컨텍스트·경계·학습 포맷 일치를 제공 |
| **해결** | `extract_tokens_api.py`에서 토큰 추출 시 프리픽스 자동 추가 |
| **다음 단계** | 모든 기본 토큰 재추출 필요 |
