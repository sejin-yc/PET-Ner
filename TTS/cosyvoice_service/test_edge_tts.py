#!/usr/bin/env python3
"""
Edge TTS만 실험하는 스크립트 (CosyVoice/API 없음).

edge-tts: Microsoft Edge 브라우저용 온라인 TTS를 쓰는 Python 패키지 (API 키 불필요).
- 공식 사용: from edge_tts import Communicate  →  Communicate(텍스트, 음성이름)
- Azure Speech REST API와는 별개(유료·키 필요). 이 패키지는 무료.

사용:
  python test_edge_tts.py "합성할 문장" [M|F]
  python test_edge_tts.py --list-voices   # 사용 가능한 음성 목록 (API 조회)
M: 남성(ko-KR-InJoonNeural), F: 여성(ko-KR-SunHiNeural)
출력: out_edge_tts.mp3 (ffmpeg 있으면 out_edge_tts.wav)
"""
import asyncio
import sys
import subprocess
from pathlib import Path

from edge_tts import Communicate, list_voices

VOICES = {"M": "ko-KR-InJoonNeural", "F": "ko-KR-SunHiNeural"}


async def main():
    if len(sys.argv) >= 2 and sys.argv[1] in ("--list-voices", "-l"):
        voices = await list_voices()
        ko = [v for v in voices if v.get("Locale", "").startswith("ko")]
        print("한국어 음성 (ShortName으로 Communicate(text, ShortName) 사용):")
        for v in ko:
            print(f"  {v.get('ShortName', '')}  Gender={v.get('Gender', '')}  Locale={v.get('Locale', '')}")
        return

    text = (sys.argv[1] if len(sys.argv) > 1 else "안녕 고양이 ~ 잘 있었어?").strip()
    gender = (sys.argv[2] if len(sys.argv) > 2 else "M").upper()
    if gender not in VOICES:
        gender = "M"
    voice = VOICES[gender]
    print(f"텍스트: {text}")
    print(f"음성: {voice} ({'남' if gender == 'M' else '여'})")

    out_mp3 = Path(__file__).resolve().parent / "out_edge_tts.mp3"
    communicate = Communicate(text, voice)
    await communicate.save(str(out_mp3))
    print(f"저장됨: {out_mp3}")

    out_wav = Path(__file__).resolve().parent / "out_edge_tts.wav"
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(out_mp3), "-ac", "1", "-ar", "44100", "-acodec", "pcm_s16le", "-f", "wav", str(out_wav)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            print(f"WAV 변환됨: {out_wav}")
        else:
            print("ffmpeg 없음 또는 실패 → MP3만 사용")
    except FileNotFoundError:
        print("ffmpeg 없음 → MP3만 사용")


if __name__ == "__main__":
    asyncio.run(main())
