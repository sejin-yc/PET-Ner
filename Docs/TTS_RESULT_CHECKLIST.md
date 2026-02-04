# 기본 토큰 TTS 결과 점검 체크리스트

기본 토큰으로 생성한 음성이 엉망일 때, 원인을 꼼꼼히 확인하기 위한 체크리스트.

---

## 1. 토큰 추출 단계 (extract_default_tokens.ps1 / extract_tokens_api.py)

| # | 확인 항목 | 확인 방법 | 정상 기준 |
|---|-----------|-----------|-----------|
| 1.1 | **LLM 프리픽스 적용** | `extract_tokens_api.py`에서 `full_prompt_text = f"You are a helpful assistant.<|endofprompt|>{prompt_text}"` 존재 여부 | 토큰 추출 시 **반드시** 위 프리픽스가 붙어 있어야 함. 없으면 한국어 발음/문장 인식이 깨짐. |
| 1.2 | **Docker 이미지 반영** | 토큰을 **언제** 추출했는지, 그 **이전에** `docker compose build cosyvoice_service` 했는지 | 프리픽스 수정 후 **이미지 재빌드** 후 추출한 토큰만 유효. restart만 하면 예전 코드로 추출된 토큰. |
| 1.3 | **prompt 텍스트 ↔ WAV 일치** | `sample_voices/{profile}_prompt.txt` 내용이 실제 WAV에 **들어 있는 말**과 동일한지 | 잘린 WAV(예: male_30s, male_50s 30초 이내)는 prompt도 잘린 구간에 맞게 수정되어 있어야 함. |
| 1.4 | **WAV 길이** | 샘플 WAV가 30초 이내인지 | CosyVoice 추출기는 **30초 초과** 오디오 지원 안 함. |
| 1.5 | **저장 경로** | 추출된 JSON이 `server/src/main/resources/default_tokens/*.json`에 저장되는지 | 스크립트가 이 경로에 쓰고, test_default_tts / DefaultTokenService가 여기서 읽음. |

---

## 2. 토큰 파일 형식 (default_tokens/*.json)

| # | 확인 항목 | 확인 방법 | 정상 기준 |
|---|-----------|-----------|-----------|
| 2.1 | **필수 키 존재** | JSON 최상위에 `tokens` 래핑 여부, 내부에 아래 키 존재 여부 | `prompt_text_token`, `prompt_text_token_len`, `llm_prompt_speech_token`, `llm_prompt_speech_token_len`, `flow_prompt_speech_token`, `flow_prompt_speech_token_len`, `prompt_speech_feat`, `prompt_speech_feat_len`, `llm_embedding`, `flow_embedding` |
| 2.2 | **_len 값 형식** | `*_len` 키가 숫자(스칼라) 또는 1개 원소 리스트인지 | `test_default_tts`의 `json_tokens_to_tensors`가 `[int(val)]`로 tensor 생성. 리스트가 아니면 `v[0]` 접근 시 예외 가능. |
| 2.3 | **float 키** | `prompt_speech_feat`, `llm_embedding`, `flow_embedding`이 리스트(숫자 배열)인지 | 합성 시 float32 tensor로 로드됨. |

### 2번 검사 결과 (실제 default_tokens/*.json 기준)

| 항목 | 결과 |
|------|------|
| **최상위** | `success`, `tokens` 두 키 존재 (API 응답 그대로 저장). |
| **tokens 래핑** | ✅ 있음. `data["tokens"]` 안에 실제 토큰 객체. |
| **필수 키 10개** | ✅ 모두 존재: `prompt_text_token`, `prompt_text_token_len`, `llm_prompt_speech_token`, `llm_prompt_speech_token_len`, `flow_prompt_speech_token`, `flow_prompt_speech_token_len`, `prompt_speech_feat`, `prompt_speech_feat_len`, `llm_embedding`, `flow_embedding`. |
| **_len 형식** | ✅ 모두 **int 스칼라** (예: `prompt_text_token_len: 167`). `test_default_tts`의 `val = v[0] if isinstance(v, list) and v else v`로 처리 가능. |
| **float 키** | ✅ `prompt_speech_feat`, `llm_embedding`, `flow_embedding` 모두 **list** (len=1, 내부에 실제 벡터). |

**결론**: 2번 토큰 파일 형식은 **정상**. `json_tokens_to_tensors`와 호환됨.

---

## 3. 합성 단계 – test_default_tts.py (로컬)

| # | 확인 항목 | 확인 방법 | 정상 기준 |
|---|-----------|-----------|-----------|
| 3.1 | **한글 시 text_frontend** | `test_default_tts.py`에서 합성 텍스트가 한글일 때 `text_frontend=False` 사용하는지 | 한글은 **text_frontend=False** 여야 함. True면 wetext 영어 정규화가 한글을 망침. (extract_tokens_api의 synthesize와 동일 로직) |
| 3.2 | **fp16** | `JetsonInferenceEngine(MODEL_DIR, fp16=False)` 여부 | 2_audio_gen.py와 동일하게 **fp16=False** 권장. |
| 3.3 | **모델 경로** | `MODEL_DIR`이 실제 모델이 있는 디렉터리인지 | `cosyvoice_models/hub/...` 또는 `CosyVoice/pretrained_models/...` 등. |
| 3.4 | **토큰 디렉터리** | `TOKEN_DIR`이 `server/.../default_tokens`를 가리키는지 | 추출 스크립트가 저장한 JSON과 동일 경로. |

---

## 4. 합성 단계 – extract_tokens_api.py /synthesize (API)

| # | 확인 항목 | 확인 방법 | 정상 기준 |
|---|-----------|-----------|-----------|
| 4.1 | **한글 시 text_frontend** | `_contains_hangul(text)` 후 `text_frontend = not _contains_hangul(text)` 사용하는지 | 한글 입력 시 **text_frontend=False**로 합성. |
| 4.2 | **JSON → tensor 변환** | `_json_tokens_to_tensors`가 API로 받은 토큰 JSON을 inference_engine이 기대하는 tensor dict로 바꾸는지 | 키 이름·dtype(_len=long, embedding/feat=float) 일치. |

---

## 5. 2_audio_gen.py와의 차이 (참고)

| 항목 | 2_audio_gen.py | test_default_tts.py / API |
|------|----------------|---------------------------|
| 토큰 입력 | `.pt` 파일 경로 (torch.load) | JSON → tensor 변환 |
| text_frontend | 미지정 → 기본 True | **한글일 때 False**로 맞춰야 함 |
| 토큰 추출 | 1_token_extract.py (프리픽스 포함) | extract_tokens_api (프리픽스 포함해야 함) |

2_audio_gen이 괜찮았던 이유: (1) 토큰이 1_token_extract로 **프리픽스 포함**해 추출됨, (2) 테스트 텍스트/환경 차이로 wetext 영향이 적었을 수 있음. 기본 토큰 파이프라인에서는 **추출 시 프리픽스** + **합성 시 한글이면 text_frontend=False** 둘 다 지키는 것이 안전함.

---

## 6. 빠른 점검 순서 (결과가 엉망일 때)

1. **토큰이 프리픽스 적용 후 다시 추출된 것인지**  
   → extract_tokens_api.py에 프리픽스 있는지 확인 후, **있으면** Docker **재빌드** 후 `extract_default_tokens.ps1` **재실행**.
2. **test_default_tts.py 한글 처리**  
   → 합성 텍스트가 한글일 때 `text_frontend=False` 사용하는지 확인 및 수정.
3. **JSON 경로/키**  
   → `default_tokens/*.json` 존재, `tokens` 래핑 및 필수 키 있는지 확인.
4. **prompt ↔ WAV**  
   → 30초 이내로 자른 WAV는 해당 구간과 prompt 텍스트가 일치하는지 확인.

---

## 7. 수정 포인트 요약

| 위치 | 수정 내용 |
|------|-----------|
| `extract_tokens_api.py` | 토큰 추출 시 `full_prompt_text = "You are a helpful assistant.<|endofprompt|>" + prompt_text` 사용. |
| `extract_tokens_api.py` | synthesize 시 한글 감지하면 `text_frontend=False`. |
| `test_default_tts.py` | 합성 텍스트에 한글이 있으면 `text_frontend=False` 사용. |
| 토큰 | 프리픽스 반영한 **API로 재추출**한 JSON 사용. |

위 체크리스트대로 확인 후, 누락된 항목만 고치면 기본 토큰 TTS 결과가 정상에 가깝게 나와야 함.

---

## 8. 다시 봐야 할 부분 (프리픽스·형식 확인 후에도 결과가 나쁠 때)

아래는 **1번(프리픽스)·2번(토큰 형식)은 확인됐는데도** TTS가 엉망일 때 점검할 항목.

### 8.1 이미 확인된 것 (다시 안 봐도 됨)

| 항목 | 상태 |
|------|------|
| 토큰 추출 시 LLM 프리픽스 | ✅ 컨테이너에 반영됨 (`docker exec ... grep` 확인) |
| 토큰 파일 형식 (JSON 키·형식) | ✅ 정상 (2번 검사 결과) |
| test_default_tts 한글 시 text_frontend | ✅ 한글일 때 `text_frontend=False` 적용됨 |

### 8.2 검사 결과 (sample_voices·샘플 음원 제외)

| 항목 | 결과 | 비고 |
|------|------|------|
| **서버 → CosyVoice 토큰 구조** | ❌ **버그 있음 → 수정함** | DefaultTokenService는 파일 전체 `{"success", "tokens"}`를 로드해 `body.tokens`로 전송. API `_json_tokens_to_tensors`는 **내부 tokens만** 기대하는데 래핑 해제를 안 함. → `tokens` 키가 있으면 내부 `tokens`만 쓰도록 **extract_tokens_api.py**에 로직 추가함. |
| **test_default_tts vs API** | ✅ test_default_tts는 `data.get("tokens", data)`로 내부 tokens 사용. API는 위 수정으로 동일 처리. | |
| **모델·환경 일치** | ✅ **fp16=False** 둘 다 사용 (test_default_tts 83행, 2_audio_gen 53행). 모델 경로는 env/로컬에 따라 다를 수 있음. | |

**조치**: `extract_tokens_api.py`의 `_json_tokens_to_tensors` 상단에 `{"success", "tokens"}` 래핑 해제 추가. **이미지 재빌드 후** 웹에서 기본 음성 재생 시 정상 동작하는지 확인 필요.

### 8.3 다시 볼 부분 (우선순위)

| 순서 | 확인할 것 | 내용 |
|------|-----------|------|
| 1 | **sample_voices 품질·일치** | WAV 음질, 노이즈, **prompt.txt가 WAV에 나오는 말과 완전 일치**하는지. 2_audio_gen은 1_token_extract용 ref.wav/ref_text와 정확히 맞춰져 있음. |
| 2 | **서버 → CosyVoice 토큰 구조** | DefaultTokenService가 `{"success", "tokens"}` 전체를 로드해 `/synthesize`에 `body.tokens`로 보냄. CosyVoice 측 `_json_tokens_to_tensors`가 `data.get("tokens", data)`로 **내부 tokens만** 쓰는지 확인. (이미 그렇게 되어 있으면 패스) |
| 3 | **test_default_tts vs API 경로** | 로컬 `test_default_tts.py`는 괜찮은데 **웹/API로 재생하면 엉망**이면 → 서버가 보내는 토큰 JSON 구조·키가 API 기대와 같은지 확인. |
| 4 | **모델·환경 일치** | test_default_tts와 2_audio_gen이 **같은 모델 디렉터리·버전** 쓰는지. fp16 여부(권장: False). |
| 5 | **샘플 음원 특성** | 기본 토큰용 WAV가 2_audio_gen용 ref보다 짧거나, 화자/녹음 환경이 다르면 품질 차이 가능. 필요 시 샘플을 2_audio_gen용과 비슷한 길이·품질로 맞춰보기. |

### 8.4 점검 순서 요약

1. **sample_voices**: prompt.txt ↔ WAV 내용 일치, WAV 30초 이내, 음질 확인.  
2. **API 경로**: 웹에서 “기본 음성” 재생 시 서버 로그로 `/synthesize` 요청·응답 확인.  
3. **동일 입력 비교**: 같은 문장으로 2_audio_gen(.pt 토큰) vs test_default_tts(기본 토큰 JSON) 출력 비교 → 차이 크면 **화자 토큰(샘플 품질/일치)** 쪽 재점검.

### 8.5 토큰 추출 방식 비교 (1_token_extract vs API)

**같은 WAV·프롬프트**로 CosyVoice `1_token_extract.py` 방식과 우리 `extract_tokens` API 결과가 동일한지 비교할 때 사용.

| 항목 | 내용 |
|------|------|
| **스크립트** | `cosyvoice_service/compare_token_extraction.py` |
| **실행** | `cd cosyvoice_service` 후 `python compare_token_extraction.py [프로필]` (예: `male_20s`) |
| **전제** | API 비교를 위해 **cosyvoice_service가 떠 있어야 함** (`docker compose up -d cosyvoice_service`). 직접 추출만 하려면 `SKIP_API=1 python compare_token_extraction.py male_20s` |
| **출력** | `compare_output/ref_tokens.pt` (직접 추출), `compare_output/api_tokens.json` (API 응답). 스크립트가 키·shape·값 자동 비교 후 결과 출력. |
| **해석** | "ref와 API 추출 결과가 동일합니다"면 추출 파이프라인은 동일. 차이가 있으면 API 쪽 WAV 변환(16kHz 모노) 등 전처리 영향일 수 있음. |
