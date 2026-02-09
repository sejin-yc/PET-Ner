# TTS 오디오 재생 구현 가이드

## 개요

웹에서 등록한 TTS WAV 파일을 백엔드 스토리지에서 다운로드하여 라즈베리파이의 I2S DAC를 통해 스피커로 출력하는 기능을 구현합니다.

---

## 하드웨어 구성

### 연결 구조

```
라즈베리파이
    ├─ I2S DAC (예: MAX98357A, PCM5102A 등)
    │   ├─ BCLK (Bit Clock)
    │   ├─ LRCLK (Left/Right Clock)
    │   └─ DIN (Data Input)
    └─ 아두이노 50mm 미니 스피커
        ├─ 8옴
        └─ 0.5W
```

---

## 구현 방법

### 방법 1: PyAudio 사용 (권장) ✅

**장점**:
- I2S DAC 지원
- 다양한 오디오 포맷 지원
- 실시간 재생 가능

**필요 패키지**:
```bash
pip install pyaudio
```

**I2S 설정**:
- 라즈베리파이에서 I2S DAC 활성화 필요
- `/boot/config.txt` 설정

---

### 방법 2: ALSA 직접 사용

**장점**:
- 시스템 레벨 제어
- I2S 직접 제어 가능

**필요 패키지**:
```bash
pip install pyalsaaudio
```

---

### 방법 3: aplay 명령어 사용

**장점**:
- 간단한 구현
- 시스템 명령어 활용

**단점**:
- Python에서 제어가 제한적

---

## 구현 구조

### 1. 백엔드에서 WAV 파일 다운로드

**API 엔드포인트**:
- 백엔드 스토리지 URL (예: `https://i14c203.p.ssafy.io/storage/tts/{file_id}.wav`)

**다운로드 방법**:
```python
import requests

def download_tts_audio(file_id: str, save_path: str):
    """백엔드 스토리지에서 TTS WAV 파일 다운로드"""
    url = f"https://i14c203.p.ssafy.io/storage/tts/{file_id}.wav"
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return save_path
    return None
```

---

### 2. I2S DAC를 통한 오디오 재생

**PyAudio 사용 예시**:
```python
import pyaudio
import wave

def play_wav_i2s(wav_path: str, device_index: int = None):
    """I2S DAC를 통해 WAV 파일 재생"""
    # WAV 파일 열기
    wf = wave.open(wav_path, 'rb')
    
    # PyAudio 초기화
    p = pyaudio.PyAudio()
    
    # I2S 디바이스 찾기 (또는 기본 디바이스 사용)
    if device_index is None:
        # I2S DAC 디바이스 찾기
        device_index = find_i2s_device(p)
    
    # 스트림 열기
    stream = p.open(
        format=p.get_format_from_width(wf.getsampwidth()),
        channels=wf.getnchannels(),
        rate=wf.getframerate(),
        output=True,
        output_device_index=device_index
    )
    
    # 오디오 재생
    data = wf.readframes(1024)
    while data:
        stream.write(data)
        data = wf.readframes(1024)
    
    # 정리
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf.close()
```

---

### 3. WebSocket/HTTP API로 재생 요청 수신

**WebSocket 메시지 형식**:
```json
{
  "type": "tts_play",
  "file_id": "12345"
}
```

**HTTP API 엔드포인트**:
```python
@app.post("/tts/play")
async def play_tts(file_id: str):
    """TTS 오디오 재생 요청"""
    # 백엔드에서 WAV 파일 다운로드
    wav_path = download_tts_audio(file_id, f"/tmp/tts_{file_id}.wav")
    
    if wav_path:
        # I2S DAC를 통해 재생
        play_wav_i2s(wav_path)
        return {"status": "success"}
    else:
        return {"status": "error", "message": "Failed to download audio"}
```

---

## I2S DAC 설정

### 라즈베리파이 설정

**`/boot/config.txt`에 추가**:
```
# I2S 활성화
dtparam=i2s=on

# I2S DAC 설정 (예: MAX98357A)
dtoverlay=hifiberry-dac
# 또는
dtoverlay=i2s-mmap
```

**재부팅 후 확인**:
```bash
# 오디오 디바이스 확인
aplay -l

# I2S 디바이스 확인
cat /proc/asound/cards
```

---

## 구현 파일 구조

### 새 파일 생성

**`src/tts_audio_player.py`**:
```python
import os
import requests
import pyaudio
import wave
import logging
from typing import Optional

log = logging.getLogger(__name__)

class TTSAudioPlayer:
    """TTS 오디오 재생 클래스"""
    
    def __init__(self, backend_url: str = "https://i14c203.p.ssafy.io", 
                 cache_dir: str = "/tmp/tts_cache"):
        self.backend_url = backend_url
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # PyAudio 초기화
        self.pyaudio = pyaudio.PyAudio()
        self.current_stream = None
        
    def download_audio(self, file_id: str) -> Optional[str]:
        """백엔드에서 TTS WAV 파일 다운로드"""
        url = f"{self.backend_url}/storage/tts/{file_id}.wav"
        save_path = os.path.join(self.cache_dir, f"{file_id}.wav")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                log.info(f"TTS 오디오 다운로드 완료: {file_id}")
                return save_path
            else:
                log.error(f"TTS 오디오 다운로드 실패: {response.status_code}")
                return None
        except Exception as e:
            log.error(f"TTS 오디오 다운로드 오류: {e}")
            return None
    
    def find_i2s_device(self) -> Optional[int]:
        """I2S DAC 디바이스 찾기"""
        device_count = self.pyaudio.get_device_count()
        for i in range(device_count):
            info = self.pyaudio.get_device_info_by_index(i)
            # I2S 디바이스 확인 (이름에 "I2S" 또는 "DAC" 포함)
            if "I2S" in info['name'].upper() or "DAC" in info['name'].upper():
                log.info(f"I2S 디바이스 발견: {info['name']} (index: {i})")
                return i
        # 기본 출력 디바이스 사용
        default_device = self.pyaudio.get_default_output_device_info()
        log.info(f"기본 오디오 디바이스 사용: {default_device['name']}")
        return default_device['index']
    
    def play_wav(self, wav_path: str, device_index: Optional[int] = None):
        """WAV 파일 재생"""
        if not os.path.exists(wav_path):
            log.error(f"WAV 파일 없음: {wav_path}")
            return False
        
        try:
            wf = wave.open(wav_path, 'rb')
            
            if device_index is None:
                device_index = self.find_i2s_device()
            
            # 스트림 열기
            self.current_stream = self.pyaudio.open(
                format=self.pyaudio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=device_index
            )
            
            # 오디오 재생
            data = wf.readframes(1024)
            while data:
                self.current_stream.write(data)
                data = wf.readframes(1024)
            
            # 정리
            self.current_stream.stop_stream()
            self.current_stream.close()
            self.current_stream = None
            wf.close()
            
            log.info(f"TTS 오디오 재생 완료: {wav_path}")
            return True
            
        except Exception as e:
            log.error(f"TTS 오디오 재생 오류: {e}")
            if self.current_stream:
                self.current_stream.close()
                self.current_stream = None
            return False
    
    def play_tts(self, file_id: str) -> bool:
        """TTS 오디오 다운로드 및 재생"""
        # 캐시 확인
        cache_path = os.path.join(self.cache_dir, f"{file_id}.wav")
        if not os.path.exists(cache_path):
            # 다운로드
            cache_path = self.download_audio(file_id)
            if not cache_path:
                return False
        
        # 재생
        return self.play_wav(cache_path)
    
    def stop(self):
        """현재 재생 중지"""
        if self.current_stream:
            self.current_stream.stop_stream()
            self.current_stream.close()
            self.current_stream = None
    
    def __del__(self):
        """소멸자"""
        self.stop()
        if self.pyaudio:
            self.pyaudio.terminate()
```

---

## WebSocket/HTTP API 통합

### `src/web_ws_server.py`에 추가

```python
from src.tts_audio_player import TTSAudioPlayer

# 전역 TTS 플레이어
tts_player = None

def init_tts_player():
    """TTS 플레이어 초기화"""
    global tts_player
    backend_url = os.getenv("BACKEND_URL", "https://i14c203.p.ssafy.io")
    tts_player = TTSAudioPlayer(backend_url=backend_url)

@app.post("/tts/play")
async def play_tts(file_id: str):
    """TTS 오디오 재생 API"""
    if tts_player is None:
        return {"status": "error", "message": "TTS player not initialized"}
    
    success = tts_player.play_tts(file_id)
    if success:
        return {"status": "success", "file_id": file_id}
    else:
        return {"status": "error", "message": "Failed to play audio"}

@app.post("/tts/stop")
async def stop_tts():
    """TTS 오디오 재생 중지"""
    if tts_player:
        tts_player.stop()
    return {"status": "success"}
```

---

## WebSocket 메시지 처리

```python
# WebSocket 핸들러에 추가
if message.get("type") == "tts_play":
    file_id = message.get("file_id")
    if file_id and tts_player:
        tts_player.play_tts(file_id)
```

---

## 의존성 추가

### `requirements.txt`에 추가

```
pyaudio>=0.2.11
requests>=2.31.0
```

**주의**: PyAudio는 시스템 라이브러리가 필요할 수 있음
```bash
# 라즈베리파이에서
sudo apt-get install portaudio19-dev python3-pyaudio
```

---

## 테스트 방법

### 1. I2S DAC 연결 확인

```bash
# 오디오 디바이스 확인
aplay -l

# 테스트 오디오 재생
aplay test.wav
```

### 2. Python 테스트

```python
from src.tts_audio_player import TTSAudioPlayer

player = TTSAudioPlayer()
player.play_tts("test_file_id")
```

---

## 주의사항

### 1. I2S DAC 설정

- 라즈베리파이에서 I2S 활성화 필요
- `/boot/config.txt` 설정 후 재부팅

### 2. 권한

- 오디오 디바이스 접근 권한 필요
- Docker 사용 시 `--device` 옵션 필요

### 3. 동시 재생 방지

- 한 번에 하나의 오디오만 재생
- 재생 중 새로운 요청 시 대기 또는 중지

---

## 작성일

2026-01-27
