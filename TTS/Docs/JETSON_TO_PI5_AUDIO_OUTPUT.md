# Jetson → Pi 5 오디오 출력 가이드

Jetson Orin Nano에서 TTS로 생성한 음성을 Raspberry Pi 5에서 스피커로 출력하는 구성을 정리한 문서.

---

## 1. 배경

- Jetson Orin Nano에 Audio 코덱을 직접 달기는 **가격·배송** 측면에서 부담이 큼.
- CosyVoice TTS는 Jetson에서 수행하고, **생성된 WAV를 Pi 5로 보내서 출력**하는 방식으로 설계.

---

## 2. Raspberry Pi 5 오디오 출력

### 2.1 Pi 5 오디오 특징

- **3.5mm 잭 없음** (Pi 4까지 있었던 단자가 제거됨)
- 출력 방식: **HDMI** 또는 **USB**

| 방법 | 설명 |
|------|------|
| HDMI | 듀얼 HDMI 포트로 디지털 오디오 → HDMI 모니터/리시버 스피커 |
| USB DAC/젠더 | USB 포트에 **USB 오디오 젠더** 연결 → 3.5mm 스피커/이어폰 |
| USB 스피커 | USB 스피커 (ALSA 호환 제품만 정상 동작) |

### 2.2 블루투스 스피커의 문제

- 사용하지 않으면 **Sleep 모드**로 들어감.
- 다시 깨우기가 어렵고, 지연/끊김 발생 가능.
- **상시 즉시 출력**이 필요한 경우에는 유선 방식이 더 적합.

### 2.3 권장: I2S 보드 + 스피커 (유선 GPIO)

**참고 링크:** [Audio Output with Pi, Simplified!](https://community.element14.com/products/raspberry-pi/raspberrypi_projects/b/blog/posts/audio-output-with-pi-simplified)

- **방식:** Pi GPIO → **I2S 보드** → 스피커
- **장점:**
  - 슬립 모드 없음, WAV 도착 시 바로 출력
  - 블루투스 페어링·슬립·깨우기 문제 없음
  - 구성이 단순하고 비용 저렴 (예: MAX98357 1~2천 원대)
- **I2S 보드 예:** MAX98357 I2S Board, PCM5102 (라인 출력)
- **연결:** 5선 (I2S 3선 + GND, 5V)
- **설정:** `/boot/config.txt` 수정 후 재부팅
- **검색어:** `MAX98357 I2S`, `라즈베리파이 I2S 오디오 보드`

---

## 3. GPIO란?

- **GPIO** = General Purpose Input/Output (범용 입출력 핀)
- 라즈베리파이/Jetson **보드 옆의 작은 핀**들.
- 각 핀을 **입력** 또는 **출력**으로 사용 가능.
- LED, 모터, **I2S 오디오 보드** 등을 점퍼선으로 직접 연결.
- I2S 보드는 이 GPIO 핀 5개에 선을 꽂아서 연결.

---

## 4. Jetson → Pi 5 WAV 전달

### 4.1 실제 흐름

```
[사용자] → [백엔드] → [Jetson /synthesize] → WAV 수신
                ↓
         [Pi 5로 WAV 전달] → [Pi 5 aplay]
```

- Jetson은 `/synthesize`로 **WAV만 생성**.
- **백엔드(Spring Boot)**가 Jetson에서 WAV를 받고, **Pi 5로 전달**하는 역할.
- 전달 방식은 백엔드 → Pi 5 구간에서 결정.

### 4.2 전달 방법 예시

| 방법 | 설명 |
|------|------|
| **HTTP POST** | Pi 5에 `/play` 같은 API를 만들고, 백엔드가 WAV를 POST. Pi 5는 저장 후 `aplay`로 재생. |
| **MQTT** | 백엔드가 WAV를 topic에 publish. Pi 5가 subscribe 후 저장·재생. 기존 MQTT 인프라 활용. |
| **WebSocket** | Pi 5가 백엔드와 WebSocket 연결. TTS 완료 시 WAV를 전송받아 재생. |
| **공유 경로** | Jetson/백엔드가 NFS 등 공유 경로에 WAV 저장. Pi 5가 파일을 읽어서 재생. |

### 4.3 권장: HTTP POST

**구성이 가장 단순함.**

1. **Pi 5**  
   - Flask/FastAPI로 `POST /play` API 구현  
   - Body: WAV 바이너리  
   - 저장: `/tmp/tts.wav`  
   - 재생: `aplay /tmp/tts.wav` (또는 subprocess)

2. **백엔드**  
   - Jetson `/synthesize`로 WAV 수신  
   - Pi 5 URL로 POST (예: `http://pi5-ip:5000/play`)  
   - `application.yml`에 `pi5.audio.url` 등으로 URL 설정

### 4.4 MQTT 사용 시

- topic 예: `robot/audio/play`
- payload: WAV 바이너리 또는 Base64
- Pi 5: 해당 topic subscribe → 저장 → `aplay`로 재생
- MQTT 메시지 크기 제한 확인 (예: 256KB~수 MB). 긴 TTS는 분할 전송 고려.

---

## 5. 요약

| 항목 | 내용 |
|------|------|
| Jetson 역할 | CosyVoice로 WAV 생성 (/synthesize) |
| 백엔드 역할 | WAV 수신 → Pi 5로 전달 |
| Pi 5 역할 | WAV 수신 → 스피커 출력 |
| 스피커 연결 | I2S 보드(MAX98357 등) + GPIO 유선 연결 권장 |
| 전달 방식 | HTTP POST가 단순. MQTT/WebSocket도 가능 |
