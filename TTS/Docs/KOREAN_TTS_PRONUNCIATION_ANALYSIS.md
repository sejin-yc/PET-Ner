# CosyVoice 한국어 TTS 발음 품질 저하 원인 분석 및 해결

기본 토큰으로 생성한 TTS 음성의 한국어 발음 품질이 떨어지는 현상에 대한 원인 분석과 해결 방법을 정리한 문서.

---

## 1. 문제 상황

| 항목 | 내용 |
|------|------|
| **현상** | 기본 토큰(male_20s, female_20s 등)으로 생성한 TTS의 **한국어 발음 품질이 저하**됨 |
| **비교** | CosyVoice `2_audio_gen.py` 등으로 음성 복제 테스트 시에는 발음 품질이 양호함 |
| **질문** | 동일한 CosyVoice 엔진을 사용하는데, 기본 토큰 TTS만 발음이 떨어지는 이유 |

---

## 2. CosyVoice 텍스트 전처리 구조

### 2.1 text_normalize 흐름

CosyVoice는 TTS 추론 전에 `frontend.text_normalize()`를 통해 텍스트를 정규화·분할한다.

```
텍스트 입력 → text_normalize(text, split=True, text_frontend=True)
           → 언어 판별 (contains_chinese)
           → zh 경로 또는 en 경로
           → wetext 정규화 (zh_tn_model / en_tn_model)
           → split_paragraph로 문장 분할
           → 토크나이저로 전달
```

**파일**: `CosyVoice/cosyvoice/cli/frontend.py` (line 143~176)

### 2.2 언어 판별 로직

```python
# frontend_utils.py
chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]+')

def contains_chinese(text):
    return bool(chinese_char_pattern.search(text))

# frontend.py text_normalize()
if contains_chinese(text):
    # 중국어 경로: zh_tn_model.normalize(), split_paragraph(..., "zh", ...)
    ...
else:
    # 영어 경로: en_tn_model.normalize(), spell_out_number(), split_paragraph(..., "en", ...)
    ...
```

| 유니코드 범위 | 의미 |
|---------------|------|
| `\u4e00-\u9fff` | CJK 통합 한자 (중국어·일본어 한자 등) |
| `\uAC00-\uD7A3` | 한글 음절 (가~힣) |
| `\u3130-\u318F` | 한글 호환 자모 |

**핵심**: `contains_chinese()`는 **한자(CJK)**만 검사한다. **한글(조합형 음절, 자모)은 이 범위에 포함되지 않는다.**

---

## 3. 원인 분석

### 3.1 한글이 영어 경로로 처리되는 이유

한국어 텍스트 예: `"안녕 고양이? 잘 지내고 있어? 보고싶어"`

1. `contains_chinese("안녕 고양이? 잘 지내고 있어? 보고싶어")` → **False**
   - 한글(가~힣)은 `\u4e00-\u9fff` 범위 밖
   - 중국어 한자가 없으므로 False

2. **else 분기(영어 경로)** 진입
   - `en_tn_model.normalize(text)` 실행
   - `spell_out_number(text, inflect_parser)` 실행
   - `split_paragraph(..., "en", token_max_n=80, ...)` 실행

### 3.2 wetext 영어 정규화가 한글에 미치는 영향

| 단계 | 역할 | 한글에 대한 영향 |
|------|------|------------------|
| `en_tn_model.normalize()` | 영어 텍스트 정규화 | 한글 문자를 영어 규칙으로 처리 → **왜곡 가능** |
| `spell_out_number()` | 숫자를 영어 단어로 변환 | 숫자만 해당, 한글 자체에는 영향 적음 |
| `split_paragraph(..., "en")` | 영어 기준 문장 분할 | 영어 구두점(`.?!;:`) 중심 분할, 한글 `。？！` 미지원 |

**결론**: wetext의 **ZhNormalizer**와 **EnNormalizer**는 각각 중국어·영어용이다. 한글은 둘 다 대상이 아니며, 영어 경로로 가면 **영어 정규화가 한글에 잘못 적용**되어 발음 품질이 떨어진다.

### 3.3 text_frontend=False 시 동작

```python
# frontend.py
if text_frontend is False or text == '':
    return [text] if split is True else text
```

`text_frontend=False`이면:
- wetext 정규화(**zh_tn_model / en_tn_model**) **전부 생략**
- `split_paragraph` **생략**
- **원문 그대로** 토크나이저로 전달
- 토크나이저(`multilingual_zh_ja_yue_char_del.tiktoken`)는 다국어 지원 → 한글 처리 가능

---

## 4. 해결 방안

### 4.1 적용한 해결책: 한글 감지 시 text_frontend=False

한글이 포함된 텍스트일 때는 **text_frontend=False**로 두어 wetext 정규화를 건너뛴다.

```python
# 한글 감지 (Hangul Syllables + Hangul Compatibility Jamo)
import re
def _contains_hangul(text: str) -> bool:
    return bool(re.search(r'[\uAC00-\uD7A3\u3130-\u318F]', text or ''))

# synthesize API 내부
text_frontend = not _contains_hangul(text)  # 한글이 있으면 False
for model_output in engine.inference_with_tokens(
    text, speaker_tokens, stream=..., speed=1.0, text_frontend=text_frontend
):
    ...
```

### 4.2 선례

| 출처 | 내용 |
|------|------|
| `CosyVoice/example.py` | "reproduce results on cosyvoice2 → add **text_frontend=False**" |
| `examples/libritts/.../prepare_reject_sample.py` | 다국어 데이터에 `inference_zero_shot(..., text_frontend=False)` 사용 |

한국어·다국어 입력에 대해 `text_frontend=False`를 쓰는 것이 CosyVoice 예제에서도 권장되는 패턴이다.

---

## 5. 수정된 코드 위치

| 파일 | 변경 내용 |
|------|----------|
| `cosyvoice_service/extract_tokens_api.py` | `_contains_hangul()` 추가, `synthesize`에서 한글 감지 시 `text_frontend=False` 전달 |

### 5.1 핵심 코드

```python
def _contains_hangul(text: str) -> bool:
    """한글이 포함되어 있으면 True (wetext 중국어/영어 정규화는 한글에 부적합)"""
    return bool(re.search(r'[\uAC00-\uD7A3\u3130-\u318F]', text or ''))

# synthesize() 내부
text_frontend = not _contains_hangul(text)
if not text_frontend:
    logger.info("한글 감지 → text_frontend=False (wetext 정규화 생략)")
for model_output in engine.inference_with_tokens(
    text, speaker_tokens, stream=use_stream, speed=1.0, text_frontend=text_frontend
):
    ...
```

---

## 6. 적용 및 검증

### 6.1 적용 방법

```powershell
docker compose restart cosyvoice_service
```

### 6.2 검증

1. `test_default_tts.py` 실행
2. `sample_output/*.wav` 재생
3. "안녕 고양이? 잘 지내고 있어? 보고싶어" 등 한글 문장 발음 품질 확인

---

## 7. 참고: 2_audio_gen.py와의 차이

| 항목 | 2_audio_gen.py | cosyvoice_service /synthesize |
|------|----------------|-------------------------------|
| 토큰 입력 | `.pt` 파일 경로 | JSON → tensor 변환 |
| inference_with_tokens | `text_frontend` 미지정 (기본 True) | 한글 감지 시 **text_frontend=False** |
| text_normalize | 동일 엔진 사용 | 한글만 우회 처리 |

2_audio_gen.py도 기본값으로 `text_frontend=True`를 사용한다. 다만, 복제용 토큰 품질이 높거나 테스트 텍스트가 상대적으로 짧아 차이가 덜 드러났을 수 있다.  
기본 토큰 TTS에서는 **한글 전용 우회(text_frontend=False)** 로 발음 품질을 확실히 개선하는 것이 안전하다.

---

## 8. 요약

| 구분 | 내용 |
|------|------|
| **원인** | CosyVoice `contains_chinese()`가 한자만 검사 → 한글이 영어 경로로 처리 → wetext 영어 정규화가 한글에 잘못 적용 |
| **해결** | 한글 포함 시 `text_frontend=False`로 wetext 정규화 생략, 원문을 토크나이저에 직접 전달 |
| **효과** | 한국어 발음 품질 향상 |
