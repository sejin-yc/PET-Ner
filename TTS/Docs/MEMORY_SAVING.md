# CosyVoice 서비스 메모리 절약 방법 (Jetson 등)

공간(메모리)이 부족할 때 아래 순서로 적용하면 사용량을 줄일 수 있습니다.

---

## 1. 우리 쪽에서 할 수 있는 것 (환경변수)

| 옵션 | 효과 |
|------|------|
| **USE_FP16=true** | 모델 가중치를 FP16으로 로드 → **메모리 약 절반** (이미 코드에 반영 가능) |
| **USE_STREAM_INFERENCE=true** | TTS를 `stream=True`로 호출 → 한 번에 처리하는 길이를 줄여 **피크 메모리 감소** |
| **FREE_CUDA_CACHE_AFTER_SYNTH=true** | 합성 끝날 때마다 `torch.cuda.empty_cache()` 호출 → **파편화 완화**, 다음 요청 전 여유 확보 |

**예시 (docker-compose)**  
```yaml
environment:
  USE_FP16: "true"
  USE_STREAM_INFERENCE: "true"           # 메모리 매우 부족할 때
  FREE_CUDA_CACHE_AFTER_SYNTH: "true"
```

> **참고**: `USE_STREAM_INFERENCE`, `FREE_CUDA_CACHE_AFTER_SYNTH`는 `extract_tokens_api.py`에서 해당 환경변수를 읽어 동작하도록 코드가 추가되어 있어야 합니다.

---

## 2. CosyVoice 라이브러리 쪽 (CV3-test/CosyVoice 수정)

**파일**: `CosyVoice/cosyvoice/cli/frontend.py`

**내용**: `split_paragraph(..., token_max_n=80, token_min_n=60, merge_len=20)` 에서 **`token_max_n`을 40 또는 60** 으로 줄이면, 한 조각당 처리 길이가 짧아져 **피크 메모리 감소**.

- 한글: 167–168줄 근처 (`"zh"` 경로)
- 영어/한국어: 173줄 근처 (`"en"` 경로)

`token_min_n`, `merge_len` 도 비슷한 비율로 줄이면 됨 (예: `token_min_n=30`, `merge_len=15`).

- **트레이드오프**: 조각 수가 늘어나서 처리 시간이 조금 늘어날 수 있음.

---

## 3. 적용 순서 (메모리 부족할 때)

1. **USE_FP16=true**
2. **USE_STREAM_INFERENCE=true**
3. **FREE_CUDA_CACHE_AFTER_SYNTH=true**
4. 그래도 부족하면 **CosyVoice `token_max_n` 40~60으로 축소**

---

## 4. 그 외

- Jetson에서 **다른 서비스(카메라·영상 등) 줄이기**
- 더 작은 CosyVoice 모델이 있으면 **그걸로 교체** 검토
