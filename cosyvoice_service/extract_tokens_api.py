#!/usr/bin/env python3
"""
CosyVoice 음성 토큰 추출 + TTS 합성 API 서버
- /extract_tokens: 음성 -> 토큰
- /synthesize: 텍스트 + 토큰 -> WAV (Jetson과 동일한 추론 엔진 사용, 현재 환경에서 테스트용)
"""
import os
import sys
import json
import logging
import tempfile
from pathlib import Path

# CosyVoice 경로 추가
sys.path.insert(0, str(Path(__file__).parent / "CosyVoice"))
sys.path.insert(0, str(Path(__file__).parent / "CosyVoice" / "third_party" / "Matcha-TTS"))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn
import torch
import torchaudio
import subprocess

# CosyVoice 임포트
from cosyvoice.cli.extractor import SpeechTokenExtractor

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CosyVoice Token Extraction & TTS API")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 변수
extractor = None
inference_engine = None  # TTS 합성용 (서버 기동 시 미리 로드 가능)

def _load_inference_engine_sync():
    """TTS 추론 엔진 동기 로드 (블로킹)"""
    global inference_engine
    from cosyvoice.cli.inference_engine import JetsonInferenceEngine
    model_dir = os.getenv("COSYVOICE_MODEL_DIR", "FunAudioLLM/Fun-CosyVoice3-0.5B-2512")
    inference_engine = JetsonInferenceEngine(model_dir=model_dir, fp16=False)

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 토큰 추출 모델 + (선택) TTS 추론 엔진 미리 로드"""
    global extractor
    import asyncio
    try:
        model_dir = os.getenv("COSYVOICE_MODEL_DIR", "FunAudioLLM/Fun-CosyVoice3-0.5B-2512")
        logger.info(f"Loading CosyVoice extractor from: {model_dir}")
        extractor = SpeechTokenExtractor(model_dir=model_dir)
        logger.info("CosyVoice extractor loaded successfully")

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
        
        # WebM/기타 형식을 WAV로 변환 (출력 파일명을 다르게 설정)
        base_name = audio_file.filename.rsplit('.', 1)[0]
        temp_wav_path = f"/tmp/{base_name}_converted.wav"
        
        # 1. 먼저 ffmpeg로 변환 시도 (WebM/Opus 등 지원)
        logger.info(f"Attempting to convert audio file: {temp_audio_path} -> {temp_wav_path}")
        try:
            import subprocess
            logger.info("Checking if ffmpeg is available...")
            # ffmpeg 존재 확인
            check_result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
            if check_result.returncode != 0:
                raise FileNotFoundError("ffmpeg not found in PATH")
            
            logger.info("ffmpeg found, starting conversion...")
            result = subprocess.run(
                ['ffmpeg', '-i', temp_audio_path, '-ar', '16000', '-ac', '1', '-f', 'wav', temp_wav_path, '-y'],
                capture_output=True,
                text=True,
                timeout=30
            )
            logger.info(f"ffmpeg return code: {result.returncode}")
            if result.returncode == 0 and os.path.exists(temp_wav_path):
                logger.info(f"Successfully converted audio to WAV using ffmpeg: {temp_wav_path}")
            else:
                logger.error(f"ffmpeg stderr: {result.stderr}")
                raise Exception(f"ffmpeg conversion failed: {result.stderr}")
        except FileNotFoundError as e:
            logger.warning(f"ffmpeg not found: {e}, trying torchaudio...")
            # 2. ffmpeg가 없으면 torchaudio로 시도
            try:
                waveform, sample_rate = torchaudio.load(temp_audio_path)
                logger.info(f"Successfully loaded audio with torchaudio: sample_rate={sample_rate}")
                
                # 모노로 변환 (스테레오인 경우)
                if waveform.shape[0] > 1:
                    waveform = waveform.mean(dim=0, keepdim=True)
                
                # 16kHz로 리샘플링
                if sample_rate != 16000:
                    resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                    waveform = resampler(waveform)
                
                # WAV 파일로 저장
                torchaudio.save(temp_wav_path, waveform, 16000)
                logger.info(f"Converted audio to WAV using torchaudio: {temp_wav_path}")
            except Exception as torch_error:
                logger.error(f"torchaudio conversion failed: {torch_error}")
                # 변환 실패 시 원본 파일 사용 (이미 WAV일 수도 있음)
                temp_wav_path = temp_audio_path
                logger.info(f"Using original file as-is: {temp_wav_path}")
        except Exception as ffmpeg_error:
            logger.error(f"ffmpeg conversion failed: {ffmpeg_error}")
            # 변환 실패 시 원본 파일 사용
            temp_wav_path = temp_audio_path
            logger.info(f"Using original file as-is: {temp_wav_path}")
        
        # 음성 토큰 추출 (WAV 파일 사용)
        logger.info(f"Extracting tokens from WAV file: {temp_wav_path}")
        speaker_tokens = extractor.extract_speaker_tokens(
            prompt_text=prompt_text,
            prompt_wav=temp_wav_path
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


def _get_inference_engine():
    """TTS 합성용 JetsonInferenceEngine (서버 기동 시 미리 로드됐으면 그대로 사용)"""
    global inference_engine
    if inference_engine is None:
        import time
        t0 = time.perf_counter()
        from cosyvoice.cli.inference_engine import JetsonInferenceEngine
        model_dir = os.getenv("COSYVOICE_MODEL_DIR", "FunAudioLLM/Fun-CosyVoice3-0.5B-2512")
        logger.warning("TTS 엔진이 아직 로드되지 않음. 지금 로드 중 (1~2분 소요, PRELOAD_TTS=true 로 서버 기동 시 미리 로드 권장)...")
        inference_engine = JetsonInferenceEngine(model_dir=model_dir, fp16=False)
        logger.info(f"JetsonInferenceEngine 로드 완료 (소요: {time.perf_counter() - t0:.1f}초)")
    return inference_engine


def _json_tokens_to_tensors(tokens: dict) -> dict:
    """DB/API에서 온 JSON 토큰을 JetsonInferenceEngine이 기대하는 tensor 형태로 변환"""
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
    if not text or not tokens:
        raise HTTPException(status_code=400, detail="text and tokens are required")
    try:
        import time
        t0 = time.perf_counter()
        already_loaded = inference_engine is not None
        engine = _get_inference_engine()
        logger.info("TTS 추론 시작 (엔진 미리 로드됨)" if already_loaded else "TTS 추론 시작 (방금 엔진 로드 완료)")
        speaker_tokens = _json_tokens_to_tensors(tokens)
        chunks = []
        for model_output in engine.inference_with_tokens(
            text, speaker_tokens, stream=False, speed=1.0, text_frontend=True
        ):
            chunks.append(model_output["tts_speech"].cpu())
        t1 = time.perf_counter()
        logger.info(f"TTS 추론 소요: {t1 - t0:.2f}초 (텍스트 길이: {len(text)})")
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
