"""
TTS 오디오 재생 모듈

백엔드 스토리지에서 TTS WAV 파일을 다운로드하여 I2S DAC를 통해 스피커로 출력합니다.
"""
import os
import requests
import logging
import threading
from typing import Optional

log = logging.getLogger(__name__)

try:
    import pyaudio
    import wave
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    log.warn("PyAudio가 설치되지 않았습니다. TTS 오디오 재생 기능을 사용할 수 없습니다.")


class TTSAudioPlayer:
    """TTS 오디오 재생 클래스"""
    
    def __init__(self, backend_url: str = "https://i14c203.p.ssafy.io", 
                 cache_dir: str = "/tmp/tts_cache",
                 device_index: Optional[int] = None):
        """
        TTS 오디오 플레이어 초기화
        
        Args:
            backend_url: 백엔드 서버 URL
            cache_dir: WAV 파일 캐시 디렉토리
            device_index: 오디오 출력 디바이스 인덱스 (None이면 자동 검색)
        """
        self.backend_url = backend_url.rstrip('/')
        self.cache_dir = cache_dir
        self.device_index = device_index
        os.makedirs(cache_dir, exist_ok=True)
        
        # PyAudio 초기화
        self.pyaudio = None
        self.current_stream = None
        self._play_lock = threading.Lock()
        
        if PYAUDIO_AVAILABLE:
            try:
                self.pyaudio = pyaudio.PyAudio()
                if self.device_index is None:
                    self.device_index = self.find_i2s_device()
                log.info(f"TTS 오디오 플레이어 초기화 완료 (디바이스 인덱스: {self.device_index})")
            except Exception as e:
                log.error(f"PyAudio 초기화 실패: {e}")
                self.pyaudio = None
        else:
            log.warn("PyAudio를 사용할 수 없습니다. TTS 오디오 재생 기능이 비활성화됩니다.")
    
    def download_audio(self, file_id: str) -> Optional[str]:
        """
        백엔드에서 TTS WAV 파일 다운로드
        
        Args:
            file_id: TTS 파일 ID
            
        Returns:
            다운로드된 파일 경로 또는 None
        """
        url = f"{self.backend_url}/storage/tts/{file_id}.wav"
        save_path = os.path.join(self.cache_dir, f"{file_id}.wav")
        
        try:
            log.info(f"TTS 오디오 다운로드 시작: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                file_size = os.path.getsize(save_path)
                log.info(f"TTS 오디오 다운로드 완료: {file_id} ({file_size} bytes)")
                return save_path
            else:
                log.error(f"TTS 오디오 다운로드 실패: HTTP {response.status_code}")
                return None
        except Exception as e:
            log.error(f"TTS 오디오 다운로드 오류: {e}")
            return None
    
    def find_i2s_device(self) -> Optional[int]:
        """
        I2S DAC 디바이스 찾기
        
        Returns:
            디바이스 인덱스 또는 None
        """
        if not self.pyaudio:
            return None
        
        try:
            device_count = self.pyaudio.get_device_count()
            log.info(f"사용 가능한 오디오 디바이스 수: {device_count}")
            
            # I2S 디바이스 검색
            for i in range(device_count):
                try:
                    info = self.pyaudio.get_device_info_by_index(i)
                    device_name = info['name'].upper()
                    # I2S 또는 DAC가 포함된 디바이스 찾기
                    if "I2S" in device_name or "DAC" in device_name or "HIFIBERRY" in device_name:
                        log.info(f"I2S 디바이스 발견: {info['name']} (index: {i}, channels: {info['maxOutputChannels']})")
                        return i
                except Exception as e:
                    log.debug(f"디바이스 {i} 정보 조회 실패: {e}")
                    continue
            
            # 기본 출력 디바이스 사용
            try:
                default_device = self.pyaudio.get_default_output_device_info()
                log.info(f"기본 오디오 디바이스 사용: {default_device['name']} (index: {default_device['index']})")
                return default_device['index']
            except Exception as e:
                log.error(f"기본 오디오 디바이스 조회 실패: {e}")
                return None
                
        except Exception as e:
            log.error(f"I2S 디바이스 검색 오류: {e}")
            return None
    
    def play_wav(self, wav_path: str, device_index: Optional[int] = None) -> bool:
        """
        WAV 파일 재생
        
        Args:
            wav_path: WAV 파일 경로
            device_index: 오디오 출력 디바이스 인덱스 (None이면 자동 선택)
            
        Returns:
            재생 성공 여부
        """
        if not PYAUDIO_AVAILABLE or not self.pyaudio:
            log.error("PyAudio를 사용할 수 없습니다.")
            return False
        
        if not os.path.exists(wav_path):
            log.error(f"WAV 파일 없음: {wav_path}")
            return False
        
        # 동시 재생 방지
        with self._play_lock:
            try:
                # 기존 재생 중지
                self.stop()
                
                wf = wave.open(wav_path, 'rb')
                
                if device_index is None:
                    device_index = self.device_index
                
                if device_index is None:
                    log.error("오디오 출력 디바이스를 찾을 수 없습니다.")
                    wf.close()
                    return False
                
                # 스트림 열기
                self.current_stream = self.pyaudio.open(
                    format=self.pyaudio.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                    output_device_index=device_index
                )
                
                log.info(f"TTS 오디오 재생 시작: {wav_path} (샘플레이트: {wf.getframerate()}Hz, 채널: {wf.getnchannels()})")
                
                # 오디오 재생
                chunk_size = 1024
                data = wf.readframes(chunk_size)
                while data:
                    self.current_stream.write(data)
                    data = wf.readframes(chunk_size)
                
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
                    try:
                        self.current_stream.stop_stream()
                        self.current_stream.close()
                    except:
                        pass
                    self.current_stream = None
                return False
    
    def play_tts(self, file_id: str) -> bool:
        """
        TTS 오디오 다운로드 및 재생
        
        Args:
            file_id: TTS 파일 ID
            
        Returns:
            재생 성공 여부
        """
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
        with self._play_lock:
            if self.current_stream:
                try:
                    self.current_stream.stop_stream()
                    self.current_stream.close()
                except:
                    pass
                self.current_stream = None
    
    def __del__(self):
        """소멸자"""
        self.stop()
        if self.pyaudio:
            try:
                self.pyaudio.terminate()
            except:
                pass
