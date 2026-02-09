# Pi5 음성 재생 클라이언트

라즈베리파이5에서 MQTT로 재생 요청을 받아 WAV를 다운로드한 뒤 I2S 스피커로 출력하고, 재생 결과를 서버에 반영하는 방법입니다.

## 라즈베리파이에 코드 넣고 실행하기 (처음 쓸 때)

지금 PC에 있는 `scripts/pi5_audio_player.py`는 **나중에 라즈베리파이 위에서 실행할 스크립트**입니다. Pi를 쓰는 순서는 아래처럼 하면 됩니다.

1. **라즈베리파이 준비**
   - Raspberry Pi OS 설치, 네트워크 연결, SSH 또는 모니터+키보드로 터미널 사용 가능하게 둠.

2. **코드 복사**
   - **방법 A**: PC에서 Pi로 파일만 복사  
     - SCP: `scp S14P11C203/scripts/pi5_audio_player.py pi@라즈베리파이IP:~/pi5_audio_player.py`  
     - 또는 USB, Git 클론 등으로 `pi5_audio_player.py`를 Pi의 원하는 폴더(예: `~/scripts/`)에 넣음.
   - **방법 B**: Pi에서 이 저장소 클론  
     - `git clone ...` 후 `cd 프로젝트/scripts` 에서 실행.

3. **Python3 + 의존성**
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip alsa-utils   # aplay(I2S 재생) 포함
   pip3 install paho-mqtt
   ```

4. **서버/MQTT 주소 설정**
   - 서버와 MQTT가 **PC 또는 다른 머신**에 있으면, Pi에서 그 IP로 접속해야 함.
   ```bash
   export SERVER_BASE_URL="http://서버IP:8080/api"
   export MQTT_BROKER="tcp://MQTT서버IP:1883"
   ```
   - 서버와 MQTT가 같은 머신이면 위에서 `서버IP`와 `MQTT서버IP`를 같은 값으로.

5. **실행**
   ```bash
   cd ~/scripts   # 또는 파일 넣은 폴더
   python3 pi5_audio_player.py
   ```
   - 정상이면 "MQTT 구독 중..." 같은 로그가 나오고, 웹에서 TTS/무전 보내면 Pi에서 소리가 나야 함.

6. **백그라운드/재부팅 후 자동 실행 (선택)**
   - `nohup python3 pi5_audio_player.py &`  
   - 또는 systemd 서비스로 등록해 두면 재부팅 후에도 자동 실행 가능.

정리: **지금은 PC에서 서버만 돌려도 되고, 나중에 Pi를 준비했을 때 위 순서대로 Pi에 `pi5_audio_player.py`만 넣고 실행하면 됩니다.**

## 동작 흐름

1. 웹/서버에서 TTS 또는 무전기 음성 저장 → 서버가 로컬 폴더에 WAV 저장 + DB에 **CREATED**로 적재 (큐)
2. 서버는 **선입선출(FIFO) 큐**: 재생 중(PLAYING)인 항목이 없을 때만, 대기(CREATED) 중인 것 중 **가장 오래된 것 하나**를 골라 **MQTT 발행** (`pi5/audio/play`)하고 해당 행을 PLAYING으로 변경
3. Pi5의 `pi5_audio_player.py`가 해당 토픽 구독 → payload의 `audioUrl`로 WAV 다운로드 → `aplay`로 I2S 재생
4. 재생 완료/실패 시 서버 `PATCH /api/audio/{id}/status` (PLAYED / FAILED) → 서버가 다음 대기 항목이 있으면 그걸 MQTT로 한 건만 다시 발행 (한 번에 하나씩만 재생)

## Pi5 준비

```bash
# 의존성
pip install paho-mqtt

# ALSA 재생 확인 (I2S 카드가 hw:0,0 등으로 잡혀 있는지)
aplay -l
```

## 실행

```bash
cd scripts
# 기본: localhost MQTT, localhost 서버
python3 pi5_audio_player.py
```

### 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `MQTT_BROKER` | MQTT 브로커 주소 | `tcp://localhost:1883` |
| `MQTT_TOPIC` | 구독 토픽 | `pi5/audio/play` |
| `MQTT_USERNAME` | MQTT 사용자 (선택) | - |
| `MQTT_PASSWORD` | MQTT 비밀번호 (선택) | - |
| `SERVER_BASE_URL` | 서버 API base (상태 업데이트용) | `http://localhost:8080/api` |
| `ALSA_DEVICE` | aplay 디바이스 | `plughw:0,0` |

### 내부망에서 서버 주소만 바꿀 때

```bash
export SERVER_BASE_URL="http://192.168.0.10:8080/api"
export MQTT_BROKER="tcp://192.168.0.10:1883"
python3 pi5_audio_player.py
```

서버와 MQTT 브로커가 같은 호스트(192.168.0.10)면 위처럼 한 번만 설정하면 됩니다.

## 서버 설정

- `application.yml` (또는 환경변수)
  - `SERVER_BASE_URL`: Pi5가 다운로드·상태 업데이트에 쓸 URL (예: `http://192.168.0.10:8080/api`)
- 음성 파일은 `audio.upload-dir`(기본 `/app/uploads/audio`)에 저장되고, URL은 `{SERVER_BASE_URL}/uploads/audio/{fileName}` 형태로 MQTT에 실립니다.

## DB 상태

- `audio_playback.status`: `CREATED` → (Pi5 수신) → `PLAYING` → `PLAYED` 또는 `FAILED`
- Pi5가 `PATCH /api/audio/{id}/status` 호출 시 `played_at`, `error_message` 등이 갱신됩니다.

## 음성 저장 위치 (통일)

- **한 곳**: `audio.upload-dir` (기본 `/app/uploads/audio`)에 아래 세 가지가 모두 저장됩니다.
  - **무전기**: `walkie_{userId}_{timestamp}.wav` (업로드 → CosyVoice `/convert_to_wav` → 저장)
  - **기본 목소리 TTS**: `tts_default_{userId}_{timestamp}.wav` (Edge TTS → WAV 저장)
  - **내 목소리 TTS**: `tts_cloned_{userId}_{timestamp}.wav` (CosyVoice 합성 → WAV 저장)
- **목소리 학습** 시 녹음 파일도 같은 변환(`/convert_to_wav`)을 사용한 뒤 `voice_train_{userId}_{timestamp}.wav`로 같은 폴더에 저장하고, 해당 WAV로 토큰 추출(`/extract_tokens`)을 호출합니다.

## 트러블슈팅

- **"무전 전송 실패: No static resource audio/walkie"**  
  - 클라이언트는 `POST /api/audio/walkie`로 보냅니다 (axios baseURL `/api`).  
  - 서버는 `context-path: /api`이므로 컨트롤러 매핑은 `POST /audio/walkie`입니다.  
  - 404가 나면: **Spring Boot 서버(또는 Docker 이미지)를 다시 빌드**해 `AudioController`가 포함되었는지 확인하세요.  
  - 로컬 개발 시 Vite 프록시가 `/api` → `http://localhost:8080`으로 가도록 되어 있어야 합니다.
