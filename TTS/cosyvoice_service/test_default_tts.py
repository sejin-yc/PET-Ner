#!/usr/bin/env python3
"""
기본 토큰(default_tokens JSON)으로 TTS 합성 (2_audio_gen.py와 유사)
- sample_voices에 대응하는 모든 프로필(male_10s ~ female_50s, neutral)에 대해
  default_tokens/{profile}.json 로드 → JetsonInferenceEngine으로 합성 → sample_output/{profile}.wav 저장
- cosyvoice_models에 모델이 있으면 해당 경로 사용 (재다운로드 방지)

사용법 (cosyvoice 등 torch/CosyVoice 환경에서):
  cd S14P11C203/cosyvoice_service
  python test_default_tts.py

전제: server/src/main/resources/default_tokens/*.json 이 있어야 함 (extract_default_tokens.ps1 실행 후)

옵션:
  --profile male_20s   한 프로필만 합성 (순서/캐시 영향 확인용)
  --no-cuda-clear      프로필 간 CUDA 캐시 정리 안 함 (기본: 매 프로필 후 정리)
  1. 추출/합성 순서·한 번에 돌리기 영향
영향 있을 수 있습니다.
토큰 추출(extract_default_tokens.ps1 → API): 같은 프로세스에서 male_10s → male_20s → … 순으로 돌리면, GPU 메모리/캐시가 첫 요청 이후로 쌓여서 두 번째부터 결과가 이상해질 수 있음.
TTS 합성(test_default_tts.py): 같은 엔진으로 male_10s → male_20s → … 순으로 돌리면, 첫 번째만 괜찮고 나머지가 엉망인 현상이 나올 수 있음.
그래서 추출 순서 / 한 번에 돌리는 것이 원인일 가능성을 줄이려고, 아래 두 가지를 넣었습니다.
2. 적용한 수정
(1) test_default_tts.py (TTS 합성)
프로필마다 CUDA 캐시 정리: 각 프로필 합성 직후 torch.cuda.empty_cache() + synchronize() 호출.
한 프로필만 실행 옵션
python test_default_tts.py --profile male_20s
→ male_20s만 돌려서, “male_20s 단독”이 괜찮은지 확인 가능.
캐시 정리 끄기 옵션
python test_default_tts.py --no-cuda-clear
→ 캐시 정리 없이 돌려서, 캐시 정리 유무에 따라 품질이 달라지는지 비교 가능.
(2) extract_tokens_api.py (토큰 추출)
추출 한 번 끝날 때마다 CUDA 캐시 정리: /extract_tokens 응답 보내기 직전에 torch.cuda.empty_cache() + synchronize() 호출.
→ 다음 추출(male_20s, male_30s, …)이 더 “깨끗한” GPU 상태에서 돌도록 함.
3. 확인 방법
말씀하신 “추출된 거”가 토큰 추출(API)인지, TTS 합성(sample_output WAV)인지에 따라:
구분	확인 방법
토큰 추출	1) 수정된 API로 extract_default_tokens.ps1 다시 한 번에 돌린 뒤, male_20s·female_10s 등 JSON으로 만든 음성이 괜찮은지 확인. 2) 그래도 나머지가 엉망이면, 한 프로필씩만 추출 (예: male_20s만 curl로 호출 → 컨테이너 재시작 → male_30s만 호출 …) 해보고, 그때는 괜찮은지 비교.
TTS 합성	1) python test_default_tts.py (캐시 정리 켜진 상태)로 전체 다시 돌려서, male_20s·female_10s 등 WAV가 나아졌는지 확인. 2) python test_default_tts.py --profile male_20s 로 male_20s만 돌려서, male_20s 단독은 괜찮은지 확인. male_20s 단독은 괜찮은데 전체 돌리면 나머지만 엉망이면, “한 번에 돌리는 것” 영향일 가능성이 큼.
정리하면, 추출 순서 / 한 번에 돌리는 것이 원인일 수 있어서, 위처럼 순서·캐시를 건드리는 수정을 넣었고, 단일 프로필 실행으로 그게 맞는지 확인해보면 됩니다.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# CosyVoice 경로 (extract_tokens_api.py / compare_token_extraction.py와 동일)
_script_dir = Path(__file__).resolve().parent
_cosy_root = _script_dir / "CosyVoice"
if not _cosy_root.exists() and _script_dir.parent.parent.is_dir():
    _cosy_root = _script_dir.parent.parent / "CosyVoice"
if _cosy_root.exists():
    sys.path.insert(0, str(_cosy_root))
else:
    print(f"CosyVoice not found at {_cosy_root}", file=sys.stderr)
    sys.exit(1)
_matcha = _cosy_root / "third_party" / "Matcha-TTS"
if _matcha.exists():
    sys.path.insert(0, str(_matcha))

import torch
import torchaudio

# 설정
TOKEN_DIR = _script_dir.parent / "server" / "src" / "main" / "resources" / "default_tokens"
OUTPUT_DIR = _script_dir / "sample_output"
TEST_TEXT = "안녕하세요. 기본 음성 테스트입니다. 오늘 날씨가 좋네요."

# sample_voices에 있는 프로필 + neutral (extract_default_tokens.ps1와 동일)
# PROFILES = [
#     "male_10s", "male_20s", "male_30s", "male_40s", "male_50s",
#     "female_10s", "female_20s", "female_30s", "female_40s", "female_50s",
#     "neutral",
# ]
PROFILES = [
    "male_20s"
]

def _resolve_model_dir() -> str:
    """cosyvoice_models에 모델이 있으면 사용, 없을 때만 원격 ID."""
    env_dir = os.getenv("COSYVOICE_MODEL_DIR")
    if env_dir and Path(env_dir).exists() and (Path(env_dir) / "cosyvoice3.yaml").exists():
        return env_dir
    if env_dir:
        return env_dir
    remote_id = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
    candidates = [
        _script_dir.parent / "cosyvoice_models" / "hub" / "FunAudioLLM" / "Fun-CosyVoice3-0___5B-2512",
        _script_dir.parent / "cosyvoice_models" / "hub" / "FunAudioLLM" / "Fun-CosyVoice3-0.5B-2512",
        _cosy_root / "pretrained_models" / "Fun-CosyVoice3-0.5B",
    ]
    for p in candidates:
        if p.exists() and (p / "cosyvoice3.yaml").exists():
            return str(p)
    return remote_id


def _contains_hangul(text: str) -> bool:
    return bool(re.search(r"[\uAC00-\uD7A3\u3130-\u318F]", text or ""))


def _json_tokens_to_tensors(tokens: dict) -> dict:
    """default_tokens JSON → JetsonInferenceEngine이 기대하는 tensor dict."""
    if "tokens" in tokens and isinstance(tokens.get("tokens"), dict):
        tokens = tokens["tokens"]
    out = {}
    float_keys = {"prompt_speech_feat", "llm_embedding", "flow_embedding"}
    for k, v in tokens.items():
        if k.endswith("_len"):
            val = v[0] if isinstance(v, list) and len(v) > 0 else v
            out[k] = torch.tensor([int(val)], dtype=torch.long)
        elif isinstance(v, list):
            dtype = torch.float32 if k in float_keys else torch.long
            out[k] = torch.tensor(v, dtype=dtype)
        else:
            out[k] = torch.tensor([v], dtype=torch.long)
    return out


def main():
    parser = argparse.ArgumentParser(description="기본 토큰으로 TTS 합성 (2_audio_gen 스타일)")
    parser.add_argument("--profile", type=str, default=None, help="한 프로필만 실행 (예: male_20s). 순서/캐시 영향 확인용.")
    parser.add_argument("--no-cuda-clear", action="store_true", help="프로필 간 CUDA 캐시 정리 안 함")
    args = parser.parse_args()

    profiles_to_run = [args.profile] if args.profile else PROFILES
    if args.profile and args.profile not in PROFILES:
        print(f"알 수 없는 프로필: {args.profile}. 사용 가능: {PROFILES}")
        sys.exit(1)

    model_dir = _resolve_model_dir()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"모델: {model_dir}")
    print(f"토큰 디렉터리: {TOKEN_DIR}")
    print(f"출력 디렉터리: {OUTPUT_DIR}")
    print(f"테스트 문장: {TEST_TEXT}")
    print(f"한글 → text_frontend=False")
    if args.profile:
        print(f"실행 프로필: {args.profile} (단일)")
    print(f"프로필 간 CUDA 캐시 정리: {'안 함' if args.no_cuda_clear else '함'}")
    print()

    if not TOKEN_DIR.exists():
        print(f"토큰 디렉터리가 없습니다: {TOKEN_DIR}")
        print("먼저 extract_default_tokens.ps1 로 default_tokens/*.json 을 생성하세요.")
        sys.exit(1)

    # JetsonInferenceEngine 로드 (2_audio_gen.py와 동일: fp16=False)
    from cosyvoice.cli.inference_engine import JetsonInferenceEngine

    print("[1/2] 모델 로딩 중... (LLM, Flow, HiFT)")
    t0 = time.perf_counter()
    engine = JetsonInferenceEngine(model_dir=model_dir, fp16=False)
    print(f"      로드 완료 ({time.perf_counter() - t0:.2f}초)\n")

    text_frontend = not _contains_hangul(TEST_TEXT)
    print("[2/2] 프로필별 TTS 합성 중...")

    success = 0
    for profile in profiles_to_run:
        token_path = TOKEN_DIR / f"{profile}.json"
        if not token_path.exists():
            print(f"  [SKIP] {profile} - {token_path.name} 없음")
            continue
        out_path = OUTPUT_DIR / f"{profile}.wav"
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            speaker_tokens = _json_tokens_to_tensors(data)
            # 엔진이 inference_with_tokens 내부에서 device로 이동함

            chunks = []
            for out in engine.inference_with_tokens(
                TEST_TEXT,
                speaker_tokens,
                stream=False,
                speed=1.0,
                text_frontend=text_frontend,
            ):
                chunks.append(out["tts_speech"].cpu())
            if not chunks:
                print(f"  [FAIL] {profile} - 음성 생성 없음")
                continue
            wav = torch.cat(chunks, dim=1)
            torchaudio.save(str(out_path), wav, engine.sample_rate)
            sec = wav.shape[1] / engine.sample_rate
            print(f"  [OK] {profile} -> {out_path.name} ({sec:.2f}초)")
            success += 1
            # 프로필마다 CUDA 캐시 정리 (한 번에 돌릴 때 두 번째부터 엉망인 현상 완화 시도)
            if not args.no_cuda_clear and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception as e:
            print(f"  [FAIL] {profile} - {e}")

    print(f"\n완료: {success}/{len(profiles_to_run)} 프로필 저장 -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
