#!/usr/bin/env python3
"""
CosyVoice 음성 토큰 추출 + TTS 합성 API 서버
- /extract_tokens: 음성 -> 토큰
- /synthesize: 텍스트 + 토큰 -> WAV (Jetson과 동일한 추론 엔진 사용, 현재 환경에서 테스트용)
"""
import asyncio
import os
import re
import sys
import json
import logging
import tempfile
from pathlib import Path

# CosyVoice 경로 추가
# - Docker: /app/CosyVoice (스크립트와 같은 디렉터리)
# - Jetson: 스크립트와 같은 디렉터리에 CosyVoice/ 풀어둔 경우
# - 로컬(PC): S14P11C203/cosyvoice_service 에서 실행 시 프로젝트 루트의 CosyVoice/ 사용
_script_dir = Path(__file__).resolve().parent
_cosy_root = _script_dir / "CosyVoice"
if not _cosy_root.exists() and _script_dir.parent.parent.is_dir():
    _cosy_root = _script_dir.parent.parent / "CosyVoice"
if _cosy_root.exists():
    sys.path.insert(0, str(_cosy_root))
else:
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).warning(f"CosyVoice not found at {_cosy_root}; tried also {_script_dir.parent.parent / 'CosyVoice'}")
# Jetson TTS 전용 모드가 아니면 Matcha-TTS 경로 추가 (토큰 추출용)
if os.getenv("JETSON_TTS_ONLY", "0").lower() not in ("1", "true", "yes") and _cosy_root.exists():
    _matcha = _cosy_root / "third_party" / "Matcha-TTS"
    if _matcha.exists():
        sys.path.insert(0, str(_matcha))

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn
import torch
import torchaudio
import subprocess

# CosyVoice 임포트 (Jetson TTS 전용 모드에서는 extractor 미사용)
SpeechTokenExtractor = None
if os.getenv("JETSON_TTS_ONLY", "0").lower() not in ("1", "true", "yes"):
    from cosyvoice.cli.extractor import SpeechTokenExtractor

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 전역 변수
extractor = None
inference_engine = None  # TTS 합성용 (서버 기동 시 미리 로드 가능)


def _resolve_model_dir() -> str:
    """이미 받은 모델이 있으면 로컬 경로 사용, 없을 때만 원격 ID (재다운로드 방지)."""
    env_dir = os.getenv("COSYVOICE_MODEL_DIR")
    if env_dir and Path(env_dir).exists() and (Path(env_dir) / "cosyvoice3.yaml").exists():
        return env_dir
    if env_dir:
        return env_dir  # Docker 등에서 절대 경로 지정한 경우 그대로 사용
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


def _log_vram(label: str = ""):
    """GPU 사용 중이면 VRAM 할당/예약/피크를 GB 단위로 로그 (LOG_VRAM=1 이면 synthesize 시에도 출력)"""
    if not torch.cuda.is_available():
        return
    torch.cuda.synchronize()
    alloc = torch.cuda.memory_allocated() / (1024**3)
    reserved = torch.cuda.memory_reserved() / (1024**3)
    peak = torch.cuda.max_memory_allocated() / (1024**3)
    logger.info(f"VRAM {label}: allocated={alloc:.2f} GB, reserved={reserved:.2f} GB, peak={peak:.2f} GB")


def _load_inference_engine_sync():
    """TTS 추론 엔진 동기 로드 (블로킹). 기본 FP16으로 VRAM 절약."""
    global inference_engine
    from cosyvoice.cli.inference_engine import JetsonInferenceEngine
    model_dir = _resolve_model_dir()
    use_fp16 = os.getenv("USE_FP16", "true").lower() in ("true", "1", "yes")
    logger.info(f"GPU available: {torch.cuda.is_available()}, FP16: {use_fp16}")
    inference_engine = JetsonInferenceEngine(model_dir=model_dir, fp16=use_fp16)
    _log_vram("(TTS 모델 로드 직후)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 토큰 추출 모델 + (선택) TTS 추론 엔진 로드/해제"""
    global extractor
    import asyncio
    model_dir = _resolve_model_dir()
    jetson_tts_only = os.getenv("JETSON_TTS_ONLY", "0").lower() in ("1", "true", "yes")
    try:
        if not jetson_tts_only and SpeechTokenExtractor is not None:
            logger.info(f"Loading CosyVoice extractor from: {model_dir}")
            extractor = SpeechTokenExtractor(model_dir=model_dir)
            logger.info("CosyVoice extractor loaded successfully")
        else:
            if jetson_tts_only:
                logger.info("JETSON_TTS_ONLY=1: skipping extractor (TTS only).")

        if os.getenv("PRELOAD_TTS", "true").lower() in ("true", "1", "yes"):
            logger.info("Preloading TTS inference engine (1~2분 소요 가능)...")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _load_inference_engine_sync)
            logger.info("TTS inference engine preloaded. 첫 재생 시 대기 없음.")
        else:
            logger.info("PRELOAD_TTS=false. TTS 엔진은 첫 /synthesize 호출 시 로드됩니다.")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise
    yield
    # shutdown (필요 시 정리)


app = FastAPI(title="CosyVoice Token Extraction & TTS API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/extract_tokens")
async def extract_tokens(
    prompt_text: str = Form(...),
    audio_file: UploadFile = File(...)
):
    """
    음성 파일에서 토큰 추출
    
    Args:
        prompt_text: 녹음한 문구
        audio_file: 오디오 파일 (WAV 형식 권장)
    
    Returns:
        JSON: 추출된 토큰 정보
    """
    if extractor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    temp_audio_path = None
    temp_wav_path = None
    try:
        # 임시 파일로 저장 (원본 형식)
        temp_audio_path = f"/tmp/{audio_file.filename}"
        with open(temp_audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        logger.info(f"Received audio file: {audio_file.filename}, content_type: {audio_file.content_type}")
        
        base_name = audio_file.filename.rsplit('.', 1)[0]
        ext = audio_file.filename.rsplit('.', 1)[-1].lower() if '.' in audio_file.filename else ''
        temp_wav_path = f"/tmp/{base_name}_converted.wav"

        def try_convert_to_wav():
            """원본을 ffmpeg로 WAV 변환. 실패 시 torchaudio 시도."""
            import subprocess
            check_result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
            if check_result.returncode != 0:
                raise FileNotFoundError("ffmpeg not found in PATH")
            result = subprocess.run(
                ['ffmpeg', '-i', temp_audio_path, '-ar', '16000', '-ac', '1', '-f', 'wav', temp_wav_path, '-y'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and os.path.exists(temp_wav_path):
                logger.info(f"Converted to WAV using ffmpeg: {temp_wav_path}")
                return
            raise Exception(f"ffmpeg failed: {result.stderr}")

        if ext == 'wav':
            # 확장자가 .wav여도 실제 내용이 WebM 등일 수 있음(백엔드가 .wav로 저장한 경우). 로드 가능한지 검사
            try:
                torchaudio.load(temp_audio_path, backend='soundfile')
                temp_wav_path = temp_audio_path
                logger.info(f"WAV 파일 → 검증 OK, 원본 사용: {temp_wav_path}")
            except Exception as e:
                logger.warning(f"WAV로 열기 실패 (실제 형식이 다를 수 있음): {e}. ffmpeg 변환 시도.")
                try:
                    try_convert_to_wav()
                except FileNotFoundError:
                    try:
                        waveform, sample_rate = torchaudio.load(temp_audio_path)
                        if waveform.shape[0] > 1:
                            waveform = waveform.mean(dim=0, keepdim=True)
                        if sample_rate != 16000:
                            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                            waveform = resampler(waveform)
                        torchaudio.save(temp_wav_path, waveform, 16000)
                        logger.info(f"Converted to WAV using torchaudio: {temp_wav_path}")
                    except Exception as torch_error:
                        logger.error(f"torchaudio conversion failed: {torch_error}")
                        raise
                except Exception as ffmpeg_error:
                    logger.error(f"ffmpeg conversion failed: {ffmpeg_error}")
                    raise
        else:
            # WebM/기타 형식 → WAV로 변환
            logger.info(f"Non-WAV → 변환 시도: {temp_audio_path} -> {temp_wav_path}")
            try:
                try_convert_to_wav()
            except FileNotFoundError:
                try:
                    waveform, sample_rate = torchaudio.load(temp_audio_path)
                    if waveform.shape[0] > 1:
                        waveform = waveform.mean(dim=0, keepdim=True)
                    if sample_rate != 16000:
                        resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                        waveform = resampler(waveform)
                    torchaudio.save(temp_wav_path, waveform, 16000)
                    logger.info(f"Converted to WAV using torchaudio: {temp_wav_path}")
                except Exception as torch_error:
                    logger.error(f"torchaudio conversion failed: {torch_error}")
                    temp_wav_path = temp_audio_path
                    logger.info(f"Using original file as-is: {temp_wav_path}")
            except Exception as ffmpeg_error:
                logger.error(f"ffmpeg conversion failed: {ffmpeg_error}")
                temp_wav_path = temp_audio_path
                logger.info(f"Using original file as-is: {temp_wav_path}")
        
        # 음성 토큰 추출 (WAV 파일 사용)
        # CosyVoice3는 "You are a helpful assistant.<|endofprompt|>" 프리픽스 필요
        # (1_token_extract.py와 동일 - 이 프리픽스가 없으면 한국어 발음이 중국어처럼 됨)
        full_prompt_text = f"You are a helpful assistant.<|endofprompt|>{prompt_text}"
        logger.info(f"Extracting tokens from WAV file: {temp_wav_path}")
        logger.info(f"prompt_text (with prefix): {full_prompt_text[:80]}...")
        # 블로킹 호출을 스레드 풀에서 실행 → 이벤트 루프 유지, /health 등 다른 요청 정상 응답
        loop = asyncio.get_event_loop()
        speaker_tokens = await loop.run_in_executor(
            None,
            lambda: extractor.extract_speaker_tokens(
                prompt_text=full_prompt_text,
                prompt_wav=temp_wav_path
            )
        )
        
        # CPU로 변환하고 리스트로 변환 (JSON 직렬화 가능하도록)
        def tensor_to_list(t):
            """Tensor를 리스트로 변환하는 헬퍼 함수"""
            if isinstance(t, torch.Tensor):
                return t.cpu().tolist()
            return t
        
        def tensor_to_item(t):
            """Tensor를 스칼라 값으로 변환하는 헬퍼 함수"""
            if isinstance(t, torch.Tensor):
                return t.cpu().item()
            return t
        
        result = {
            "prompt_text_token": tensor_to_list(speaker_tokens['prompt_text_token']),
            "prompt_text_token_len": tensor_to_item(speaker_tokens['prompt_text_token_len']),
            "llm_prompt_speech_token": tensor_to_list(speaker_tokens['llm_prompt_speech_token']),
            "llm_prompt_speech_token_len": tensor_to_item(speaker_tokens['llm_prompt_speech_token_len']),
            "flow_prompt_speech_token": tensor_to_list(speaker_tokens['flow_prompt_speech_token']),
            "flow_prompt_speech_token_len": tensor_to_item(speaker_tokens['flow_prompt_speech_token_len']),
            "prompt_speech_feat": tensor_to_list(speaker_tokens['prompt_speech_feat']),
            "prompt_speech_feat_len": tensor_to_item(speaker_tokens['prompt_speech_feat_len']),
            "llm_embedding": tensor_to_list(speaker_tokens['llm_embedding']),
            "flow_embedding": tensor_to_list(speaker_tokens['flow_embedding']),
        }
        
        # 임시 파일 삭제
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        if temp_wav_path and os.path.exists(temp_wav_path) and temp_wav_path != temp_audio_path:
            os.remove(temp_wav_path)
        
        # 추출 순서 영향 완화: 다음 요청 전에 CUDA 캐시 정리 (첫 번째만 괜찮고 나머지 엉망일 때 시도)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        logger.info("Token extraction completed successfully")
        return JSONResponse(content={"success": True, "tokens": result})
        
    except Exception as e:
        logger.error(f"Error extracting tokens: {e}", exc_info=True)
        # 임시 파일 정리
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        if temp_wav_path and os.path.exists(temp_wav_path) and temp_wav_path != temp_audio_path:
            os.remove(temp_wav_path)
        raise HTTPException(status_code=500, detail=f"Token extraction failed: {str(e)}")


def _get_inference_engine(force_fp16=None):
    """TTS 합성용 JetsonInferenceEngine. force_fp16=True면 FP16으로 로드 (OOM 완화용)."""
    global inference_engine
    if force_fp16 is not None:
        # OOM 재시도 등으로 FP16 강제 시 기존 엔진 제거 후 재생성
        if inference_engine is not None:
            try:
                del inference_engine
            except Exception:
                pass
            inference_engine = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
    if inference_engine is None:
        import time
        t0 = time.perf_counter()
        from cosyvoice.cli.inference_engine import JetsonInferenceEngine
        model_dir = _resolve_model_dir()
        use_fp16 = (
            force_fp16 if force_fp16 is not None
            else os.getenv("USE_FP16", "true").lower() in ("true", "1", "yes")
        )
        logger.warning("TTS 엔진이 아직 로드되지 않음. 지금 로드 중 (1~2분 소요, PRELOAD_TTS=true 로 서버 기동 시 미리 로드 권장)...")
        logger.info(f"GPU available: {torch.cuda.is_available()}, FP16: {use_fp16}")
        inference_engine = JetsonInferenceEngine(model_dir=model_dir, fp16=use_fp16)
        logger.info(f"JetsonInferenceEngine 로드 완료 (소요: {time.perf_counter() - t0:.1f}초)")
    return inference_engine


def _contains_hangul(text: str) -> bool:
    """한글이 포함되어 있으면 True (wetext 중국어/영어 정규화는 한글에 부적합 → text_frontend=False 사용)"""
    return bool(re.search(r'[\uAC00-\uD7A3\u3130-\u318F]', text or ''))


def _json_tokens_to_tensors(tokens: dict) -> dict:
    """DB/API에서 온 JSON 토큰을 JetsonInferenceEngine이 기대하는 tensor 형태로 변환"""
    # 기본 토큰은 API 응답 그대로 저장돼 { "success", "tokens" } 래핑 → 내부 tokens만 사용
    if "tokens" in tokens and isinstance(tokens.get("tokens"), dict):
        tokens = tokens["tokens"]
    out = {}
    float_keys = {"prompt_speech_feat", "llm_embedding", "flow_embedding"}
    for k, v in tokens.items():
        try:
            if k.endswith("_len"):
                val = v
                if isinstance(v, list) and len(v) > 0:
                    val = v[0]
                out[k] = torch.tensor([int(val)], dtype=torch.long)
            elif isinstance(v, list):
                dtype = torch.float32 if k in float_keys else torch.long
                out[k] = torch.tensor(v, dtype=dtype)
            else:
                out[k] = torch.tensor([v], dtype=torch.long)
        except Exception as e:
            raise ValueError(f"token key '{k}': {e}") from e
    return out


@app.post("/synthesize")
async def synthesize(
    text: str = Body(..., embed=True),
    tokens: dict = Body(..., embed=True)
):
    """
    저장된 음성 토큰 + 텍스트로 TTS 합성 (Jetson과 동일한 추론 엔진 사용)
    
    Args:
        text: 합성할 텍스트
        tokens: extract_tokens로 추출된 토큰 JSON (DB에 저장된 speech_tokens 형식)
    
    Returns:
        WAV 오디오 바이너리 (audio/wav)
    """
    logger.info("CosyVoice /synthesize 요청 수신 (GPU 사용)")
    if not text or not tokens:
        raise HTTPException(status_code=400, detail="text and tokens are required")

    def _do_synth(engine, speaker_tensors, use_stream, text_frontend):
        chunks = []
        for model_output in engine.inference_with_tokens(
            text, speaker_tensors, stream=use_stream, speed=1.0, text_frontend=text_frontend
        ):
            chunks.append(model_output["tts_speech"].cpu())
        return chunks

    try:
        import time
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        if os.getenv("LOG_VRAM", "").lower() in ("1", "true", "yes") and torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        already_loaded = inference_engine is not None
        engine = _get_inference_engine()
        logger.info("TTS 추론 시작 (엔진 미리 로드됨)" if already_loaded else "TTS 추론 시작 (방금 엔진 로드 완료)")
        speaker_tokens = _json_tokens_to_tensors(tokens)
        use_stream = os.getenv("USE_STREAM_INFERENCE", "false").lower() in ("true", "1", "yes")
        text_frontend = not _contains_hangul(text)
        if not text_frontend:
            logger.info("한글 감지 → text_frontend=False (wetext 정규화 생략)")
        chunks = None
        last_error = None
        for attempt in range(2):
            try:
                chunks = _do_synth(engine, speaker_tokens, use_stream, text_frontend)
                break
            except RuntimeError as e:
                err_msg = str(e).lower()
                if "out of memory" in err_msg or "cuda error" in err_msg:
                    last_error = e
                    if attempt == 0 and torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                        logger.warning("CUDA OOM → reloading engine with FP16 and retrying once...")
                        engine = _get_inference_engine(force_fp16=True)
                        continue
                raise
        if chunks is None:
            logger.error("Synthesis failed after retry: %s", last_error)
            raise last_error or RuntimeError("Synthesis failed")
        t1 = time.perf_counter()
        logger.info(f"TTS 추론 소요: {t1 - t0:.2f}초 (텍스트 길이: {len(text)})")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("CUDA cache cleared after synthesis")
        if os.getenv("LOG_VRAM", "").lower() in ("1", "true", "yes"):
            _log_vram("(방금 추론 직후)")
        if not chunks:
            raise HTTPException(status_code=500, detail="No audio generated")
        wav = torch.cat(chunks, dim=1)
        sample_rate = engine.sample_rate
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            torchaudio.save(f.name, wav, sample_rate)
            with open(f.name, "rb") as rf:
                wav_bytes = rf.read()
            os.unlink(f.name)
        return Response(content=wav_bytes, media_type="audio/wav")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Synthesis failed: {e}", exc_info=True)
        detail = f"{type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=500, detail=detail)


# Edge TTS: 기본 음성용 (test_edge_tts.py와 동일 방식)
try:
    from edge_tts import Communicate as EdgeCommunicate
except ImportError:
    EdgeCommunicate = None
EDGE_TTS_VOICES = {"M": "ko-KR-InJoonNeural", "F": "ko-KR-SunHiNeural"}


@app.post("/synthesize_edge_tts")
async def synthesize_edge_tts(text: str = Body(..., embed=True), gender: str = Body("M", embed=True)):
    """
    Edge TTS로 기본 음성 합성 (GPU 미사용).
    - gender: "M" → InJoon (남), "F" → SunHi (여). 없으면 M.
    - 반환: audio/wav (모노, 16비트, 44100 Hz)
    """
    logger.info("Edge TTS 요청 수신 (GPU 미사용 경로)")
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    if EdgeCommunicate is None:
        raise HTTPException(status_code=503, detail="edge-tts not installed")
    voice = EDGE_TTS_VOICES.get((gender or "M").upper(), EDGE_TTS_VOICES["M"])
    try:
        communicate = EdgeCommunicate(text.strip(), voice)
        tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        try:
            await communicate.save(tmp_mp3)
            # WAV 변환: 모노, 16비트, 44.1 kHz
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", tmp_mp3,
                    "-ac", "1", "-ar", "44100", "-acodec", "pcm_s16le", "-f", "wav", tmp_wav
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0 or not os.path.exists(tmp_wav):
                raise RuntimeError(f"ffmpeg WAV 변환 실패: {result.stderr or result.stdout}")
            with open(tmp_wav, "rb") as rf:
                audio_bytes = rf.read()
            # 저장은 Spring에서 uploads/audio + DB로 통일. 여기서는 바이트만 반환.
            logger.info(f"Edge TTS OK: voice={voice}, WAV len={len(audio_bytes)} bytes")
            return Response(content=audio_bytes, media_type="audio/wav")
        finally:
            for p in (tmp_mp3, tmp_wav):
                if os.path.exists(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
    except Exception as e:
        logger.error(f"Edge TTS failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/convert_to_wav")
async def convert_to_wav(audio_file: UploadFile = File(...)):
    """
    업로드된 음성 파일(webm/mp4 등)을 WAV(16kHz mono)로 변환해 바이트 반환.
    무전기 녹음 업로드 후 서버에서 Pi5 재생용 WAV로 저장할 때 사용.
    """
    import subprocess
    temp_audio_path = None
    temp_wav_path = None
    try:
        temp_audio_path = f"/tmp/convert_{audio_file.filename or 'upload'}"
        with open(temp_audio_path, "wb") as f:
            f.write(await audio_file.read())
        base = (audio_file.filename or "upload").rsplit(".", 1)[0]
        temp_wav_path = f"/tmp/{base}_out.wav"
        result = subprocess.run(
            ["ffmpeg", "-i", temp_audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", temp_wav_path, "-y"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or not os.path.exists(temp_wav_path):
            raise HTTPException(status_code=400, detail=f"ffmpeg conversion failed: {result.stderr}")
        with open(temp_wav_path, "rb") as f:
            wav_bytes = f.read()
        return Response(content=wav_bytes, media_type="audio/wav")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="ffmpeg not found")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Conversion timeout")
    finally:
        for p in (temp_audio_path, temp_wav_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@app.get("/health")
async def health_check():
    """헬스 체크 (추출 모델 + 합성 엔진 로드 여부)"""
    return {
        "status": "ok",
        "extractor_loaded": extractor is not None,
        "inference_engine_loaded": inference_engine is not None,
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 50001))
    uvicorn.run(app, host="0.0.0.0", port=port)
