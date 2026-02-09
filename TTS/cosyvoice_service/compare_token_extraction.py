#!/usr/bin/env python3
"""
1_token_extract.py 방식 vs 우리 API 방식 토큰 추출 비교

동일한 WAV·프롬프트로:
  1) CosyVoice SpeechTokenExtractor 직접 호출 (1_token_extract.py와 동일) → ref_tokens.pt
  2) extract_tokens API 호출 (같은 파일·텍스트) → api_tokens.json
  3) 두 결과의 키·shape·값 비교

사용법:
  # cosyvoice_service 폴더에서 실행 (CosyVoice, sample_voices 경로 자동)
  python compare_token_extraction.py [프로필명]

  예: python compare_token_extraction.py male_20s
  (프로필 생략 시 male_20s 사용)

  * API 비교를 위해 cosyvoice_service가 떠 있어야 함 (docker compose up -d cosyvoice_service)
  * 직접 추출만 하려면: SKIP_API=1 python compare_token_extraction.py male_20s
  * 모델이 이미 있으면 재다운로드 방지: COSYVOICE_MODEL_DIR을 로컬 경로로 설정하거나
    --model-dir 로컬경로 (예: ..\\cosyvoice_models\\hub\\FunAudioLLM\\Fun-CosyVoice3-0.5B-2512)
"""
import argparse
import json
import os
import sys
from pathlib import Path

# CosyVoice 경로 (extract_tokens_api.py와 동일)
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

# 원격 ID는 os.path.exists()가 False → CosyVoice extractor가 snapshot_download() 호출해 재다운로드함.
# 이미 받은 모델이 있으면 로컬 경로를 쓰도록 후보를 먼저 찾고, 없을 때만 원격 ID 사용.
def _default_model_dir(script_dir: Path) -> str:
    remote_id = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
    # ModelScope 캐시/볼륨 경로 (cosyvoice_models/hub/.../Fun-CosyVoice3-0___5B-2512) 우선
    candidates = [
        os.getenv("COSYVOICE_MODEL_DIR"),
        script_dir.parent / "cosyvoice_models" / "hub" / "FunAudioLLM" / "Fun-CosyVoice3-0___5B-2512",
        script_dir.parent / "cosyvoice_models" / "hub" / "FunAudioLLM" / "Fun-CosyVoice3-0.5B-2512",
        _cosy_root / "pretrained_models" / "Fun-CosyVoice3-0.5B",
    ]
    for p in candidates:
        if not p:
            continue
        path = Path(p) if not isinstance(p, Path) else p
        if path.exists() and (path / "cosyvoice3.yaml").exists():
            return str(path)
    return remote_id


def _json_tokens_to_tensors(tokens: dict) -> dict:
    """API JSON 토큰을 extractor가 반환한 것과 같은 tensor 형태로 변환"""
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


def extract_ref(profile: str, model_dir: str, sample_dir: Path, out_dir: Path) -> Path:
    """1_token_extract.py 방식: SpeechTokenExtractor 직접 호출 → .pt 저장"""
    from cosyvoice.cli.extractor import SpeechTokenExtractor

    wav_path = sample_dir / f"{profile}.wav"
    prompt_path = sample_dir / f"{profile}_prompt.txt"
    if not wav_path.exists() or not prompt_path.exists():
        raise FileNotFoundError(f"WAV 또는 prompt 없음: {wav_path}, {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        ref_text = f.read().strip()
    full_prompt = f"You are a helpful assistant.<|endofprompt|>{ref_text}"

    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "ref_tokens.pt"

    print(f"[1/2] 직접 추출 (1_token_extract.py 방식): {wav_path.name}")
    extractor = SpeechTokenExtractor(model_dir=model_dir)
    speaker_tokens = extractor.extract_speaker_tokens(
        prompt_text=full_prompt,
        prompt_wav=str(wav_path),
        save_path=str(save_path),
    )
    # save_path로 이미 저장됨; 반환값으로 shape만 확인
    for k, v in speaker_tokens.items():
        if isinstance(v, torch.Tensor):
            print(f"  {k}: shape={v.shape}, dtype={v.dtype}")
        else:
            print(f"  {k}: {v}")
    print(f"  -> 저장: {save_path}")
    return save_path


def extract_via_api(profile: str, sample_dir: Path, out_dir: Path, base_url: str) -> Path:
    """extract_tokens API 호출 → JSON 저장"""
    try:
        import requests
    except ImportError:
        print("API 비교를 위해 pip install requests 필요", file=sys.stderr)
        raise

    wav_path = sample_dir / f"{profile}.wav"
    prompt_path = sample_dir / f"{profile}_prompt.txt"
    if not wav_path.exists() or not prompt_path.exists():
        raise FileNotFoundError(f"WAV 또는 prompt 없음: {wav_path}, {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_text = f.read().strip()

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "api_tokens.json"

    print(f"[2/2] API 추출: POST {base_url}/extract_tokens")
    with open(wav_path, "rb") as f:
        r = requests.post(
            f"{base_url}/extract_tokens",
            data={"prompt_text": prompt_text},
            files={"audio_file": (wav_path.name, f, "audio/wav")},
            timeout=600,
        )
    r.raise_for_status()
    data = r.json()
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  -> 저장: {json_path}")
    return json_path


def compare(ref_pt_path: Path, api_json_path: Path) -> None:
    """ref .pt와 API JSON을 tensor로 맞춘 뒤 키·shape·값 비교"""
    try:
        ref = torch.load(ref_pt_path, map_location="cpu", weights_only=True)
    except TypeError:
        ref = torch.load(ref_pt_path, map_location="cpu")
    with open(api_json_path, "r", encoding="utf-8") as f:
        api_raw = json.load(f)
    api = _json_tokens_to_tensors(api_raw)

    ref_keys = set(ref.keys())
    api_keys = set(api.keys())
    common = ref_keys & api_keys
    only_ref = ref_keys - api_keys
    only_api = api_keys - ref_keys

    print("\n" + "=" * 60)
    print("비교 결과")
    print("=" * 60)
    print(f"  ref 키: {sorted(ref_keys)}")
    print(f"  api 키: {sorted(api_keys)}")
    if only_ref:
        print(f"  ref에만 있음: {only_ref}")
    if only_api:
        print(f"  api에만 있음: {only_api}")

    all_ok = True
    for k in sorted(common):
        r, a = ref[k], api[k]
        if not isinstance(r, torch.Tensor) or not isinstance(a, torch.Tensor):
            print(f"  {k}: 타입 불일치 (ref={type(r).__name__}, api={type(a).__name__})")
            all_ok = False
            continue
        shape_ok = r.shape == a.shape
        if not shape_ok:
            print(f"  {k}: shape 불일치 ref={r.shape} api={a.shape}")
            all_ok = False
            continue
        if r.dtype in (torch.float32, torch.float16):
            val_ok = torch.allclose(r.float(), a.float(), rtol=1e-4, atol=1e-5)
        else:
            val_ok = torch.equal(r, a)
        if val_ok:
            print(f"  {k}: OK (shape={r.shape})")
        else:
            diff = (r.float() - a.float()).abs().max().item() if r.is_floating_point() or a.is_floating_point() else (r != a).sum().item()
            print(f"  {k}: 값 불일치 (shape={r.shape}, diff={diff})")
            all_ok = False

    if all_ok and not only_ref and not only_api:
        print("\n  => ref와 API 추출 결과가 동일합니다.")
    else:
        print("\n  => 차이가 있습니다. (API는 WAV를 16kHz 모노로 변환할 수 있어 미세 차이 가능)")


def main():
    parser = argparse.ArgumentParser(description="1_token_extract vs API 토큰 추출 비교")
    parser.add_argument("profile", nargs="?", default="male_20s", help="sample_voices 프로필 (예: male_20s)")
    parser.add_argument("--model-dir", default=None, help="CosyVoice 모델 로컬 경로 (미설정 시 cosyvoice_models/... 또는 원격 ID 사용)")
    parser.add_argument("--base-url", default="http://127.0.0.1:50001", help="extract_tokens API base URL")
    parser.add_argument("--out-dir", default=None, help="출력 디렉터리 (기본: compare_output)")
    args = parser.parse_args()

    model_dir = args.model_dir or os.getenv("COSYVOICE_MODEL_DIR") or _default_model_dir(_script_dir)
    sample_dir = _script_dir / "sample_voices"
    out_dir = Path(args.out_dir) if args.out_dir else _script_dir / "compare_output"

    skip_api = os.getenv("SKIP_API", "").strip().lower() in ("1", "true", "yes")

    print(f"프로필: {args.profile}, 모델: {model_dir}")
    print(f"sample_voices: {sample_dir}")
    print(f"출력: {out_dir}")
    if skip_api:
        print("SKIP_API=1 → API 호출 생략, 직접 추출만 수행")

    ref_path = extract_ref(args.profile, model_dir, sample_dir, out_dir)

    if skip_api:
        print("\n직접 추출만 완료. API 비교는 SKIP_API를 제거하고 서버 기동 후 다시 실행하세요.")
        return

    try:
        api_path = extract_via_api(args.profile, sample_dir, out_dir, args.base_url)
    except Exception as e:
        print(f"\nAPI 추출 실패: {e}")
        print("  cosyvoice_service가 실행 중인지 확인: docker compose up -d cosyvoice_service")
        return

    compare(ref_path, api_path)


if __name__ == "__main__":
    main()
