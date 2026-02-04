# 나중에 할 일 (REMAINING TASKS)

Jetson이 없거나 다른 우선순위로 미루어 둔 작업들. 추후 진행 시 이 문서를 업데이트한다.

---

## 1. Jetson 배포·검증 (Jetson 확보 후)

### 1.1 CosyVoice TTS Jetson 실행

| 항목 | 내용 |
|------|------|
| **목표** | Jetson Orin Nano에서 CosyVoice TTS 추론 서버(`extract_tokens_api.py`) 실행 |
| **선행** | `Docs/JETSON_PYTORCH_SETUP.md`, `scripts/README_cosyvoice_inference_zip.md` 참고 |
| **체크리스트** | [ ] JetPack 6.2 / PyTorch 2.8.0 + torchvision 0.23.0 설치<br>[ ] CosyVoice_inference_only.zip 압축 해제<br>[ ] 모델 5개(c cosyvoice3.yaml, llm.pt, flow.pt, hift.pt, CosyVoice-BlankEN/) 배치<br>[ ] extract_tokens_api.py 복사, JETSON_TTS_ONLY=1, COSYVOICE_MODEL_DIR 설정<br>[ ] `python3 extract_tokens_api.py` 실행<br>[ ] `POST /synthesize` (text + tokens) → WAV 응답 확인 |
| **참고** | 백엔드 `COSYVOICE_SERVICE_URL`을 Jetson IP:50001로 설정 필요 |

### 1.2 VoiceJetsonSyncService → Jetson 연동

| 항목 | 내용 |
|------|------|
| **목표** | 로그인/목소리 학습 시 음성 토큰을 Jetson으로 미리 전송 |
| **현황** | 백엔드 `VoiceJetsonSyncService`, `JETSON_VOICE_URL` 설정 준비됨 |
| **체크리스트** | [ ] Jetson에 `POST {url}/voices/upload_token` API 구현 (또는 기존 CosyVoice 서비스에 추가)<br>[ ] 백엔드 `application.yml`에 `jetson.voice.url` (JETSON_VOICE_URL) 설정<br>[ ] 로그인 시 `syncTokenToJetson(userId)` 호출 확인<br>[ ] 목소리 학습 완료 시 `syncTokenToJetson(userId)` 호출 확인 |
| **참고** | Jetson 쪽 토큰 캐시 API 스펙은 `VoiceJetsonSyncService` payload 참고 |

---

## 2. Jetson → Pi 5 오디오 출력 (Jetson + Pi 5 모두 확보 후)

### 2.1 Pi 5 오디오 출력 하드웨어

| 항목 | 내용 |
|------|------|
| **목표** | Pi 5에서 스피커로 음성 출력 (블루투스 슬립 이슈 회피) |
| **권장** | I2S 보드(MAX98357 등) + GPIO 유선 연결 |
| **체크리스트** | [ ] I2S 보드 구매 (검색어: MAX98357 I2S, 라즈베리파이 I2S 오디오)<br>[ ] Pi 5 GPIO 5선 연결 (I2S 3선 + GND, 5V)<br>[ ] `/boot/config.txt` 수정 (dtparam=i2s=on, dtoverlay 등)<br>[ ] `aplay test.wav` 동작 확인 |
| **참고** | `Docs/JETSON_TO_PI5_AUDIO_OUTPUT.md` |

### 2.2 WAV 전달 (백엔드 → Pi 5)

| 항목 | 내용 |
|------|------|
| **목표** | 백엔드가 TTS WAV를 Pi 5로 전달 → Pi 5에서 재생 |
| **권장** | HTTP POST 방식 (Pi 5에 `/play` API, 백엔드가 POST) |
| **체크리스트** | [ ] Pi 5에 Flask/FastAPI로 `POST /play` 구현 (WAV 수신 → aplay)<br>[ ] 백엔드에 `pi5.audio.url` (PI5_AUDIO_URL) 설정<br>[ ] TTS 합성 완료 시 해당 URL로 WAV POST 로직 추가<br>[ ] Pi 5 재생 테스트 (WAV 전송 → 스피커 출력 확인) |
| **대안** | MQTT topic으로 WAV publish, Pi 5 subscribe 후 재생 (메시지 크기 제한 확인) |
| **참고** | `Docs/JETSON_TO_PI5_AUDIO_OUTPUT.md` 섹션 4 |

---

## 3. 기타 (추후 추가)

- [ ] VRAM 모니터링/로깅 (LOG_VRAM=1)으로 Jetson 실제 사용량 측정
- [ ] (필요 시) USE_STREAM_INFERENCE, FREE_CUDA_CACHE_AFTER_SYNTH 환경변수 지원 코드 추가 (`Docs/MEMORY_SAVING.md` 참고)

---

## 업데이트 이력

- 2025-01-29: 최초 작성 (Jetson 배포·Pi 5 오디오·WAV 전달 체크리스트)
