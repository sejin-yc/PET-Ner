# 목소리 학습 오디오 형식 (WebM / WAV) 정리

> 웹 녹음 → 서버 저장 → CosyVoice 토큰 추출 과정에서 발생한 "Format not recognised" 원인과 수정 내용을 정리한 문서입니다.

---

## 1. 문제 현상

- **증상**: 목소리 학습 후 DB `user_voices`의 `speech_tokens`에 `{"error": "토큰 추출 실패: ... Format not recognised"}` 저장됨.
- **CosyVoice 로그**: `Error opening '/tmp/1_xxx.wav': Format not recognised.` (soundfile.LibsndfileError)

---

## 2. 원인

### 2.1 실제 vs 이름

- **브라우저 녹음**: `MediaRecorder`는 브라우저마다 다른 형식으로 녹음함 (Chrome/Firefox → **WebM**, Safari → **MP4** 등). 실제 바이너리는 그 형식(예: WebM).
- **문제**: 파일 **내용**은 WebM인데, **이름(확장자)**만 `.wav`로 저장·전달되고 있었음.

### 2.2 왜 잘못된 확장자로 저장됐는지

| 단계 | 예전 동작 | 결과 |
|------|-----------|------|
| **프론트** | Blob은 WebM인데 파일명을 `voice.wav`로 전송 | "wav 파일"처럼 보임 |
| **백엔드** | 저장 시 항상 `userId_타임스탬프.wav`로 생성 (확장자 고정) | 내용은 WebM인데 .wav로 저장 |
| **CosyVoice** | 확장자가 .wav면 "WAV다"라고 보고 **변환 생략** | WebM 내용을 WAV로 열려다 → Format not recognised |

정리하면, **실제 형식(WebM)이 아닌데 확장자만 .wav로 저장**된 상태였음.

---

## 3. 수정 내용

### 3.1 원칙

- **실제 녹음 형식으로 저장**하고, WAV가 아니면 CosyVoice/ffmpeg에서 **WAV로 변환한 뒤** 토큰 추출.

### 3.2 프론트 (RobotContext.jsx)

- **녹음 형식**: `MediaRecorder`에 형식 지정 없이 생성 → 브라우저 기본 형식 사용.
- **실제 형식**: `mediaRecorder.mimeType`으로 확정 (예: `audio/webm`, `audio/mp4`).
- **확장자**: MIME에서 추출. `audio/webm;codecs=opus` → `webm`, `audio/mp4` → `mp4`, `audio/x-wav` → `wav` 등. 그 외는 `audio/xxx`에서 `xxx` 사용.
- **전송 파일명**: `voice.${ext}` (예: `voice.webm`, `voice.mp4`).

### 3.3 백엔드 (VoiceController.java)

- **저장 시 확장자**: 클라이언트가 보낸 **원본 파일명의 확장자**를 그대로 사용.
  - `getOriginalFilename()`에서 확장자 추출 → `userId_타임스탬프.확장자` (예: `.webm`, `.mp4`)로 저장.
- 이렇게 해야 CosyVoice에 넘길 때도 올바른 확장자로 전달됨.

### 3.4 CosyVoice (extract_tokens_api.py)

- **.wav라고 해도 믿지 않음**: 확장자가 `.wav`여도 **먼저 soundfile로 실제 로드** 시도.
- **로드 실패 시** (실제는 WebM 등):
  - 로그: `WAV로 열기 실패 (실제 형식이 다를 수 있음). ffmpeg 변환 시도.`
  - **ffmpeg**로 WAV 변환 (`-ar 16000 -ac 1 -f wav`) 후, **변환된 파일**로만 토큰 추출.
- **확장자가 .webm 등인 경우**: 원래대로 ffmpeg로 WAV 변환 후 토큰 추출.

즉, **이름만 .wav인 WebM**이 와도 CosyVoice 쪽에서 ffmpeg로 한 번 더 WAV로 바꾼 뒤 토큰 추출하도록 함.

---

## 4. 왜 “갑자기” 되는지

- **예전**: CosyVoice가 ".wav면 변환 생략"만 해서, **내용이 WebM인 .wav**를 그대로 열려다 실패.
- **수정 후**:  
  - `.wav`여도 **먼저 열어보기** → 실패하면 **ffmpeg로 변환** → **변환된 WAV**로만 토큰 추출.
- **재시작 후**에는 이 새 코드가 적용되므로, 백엔드가 여전히 `.wav` 이름으로 보내도 CosyVoice가 "열기 실패 → ffmpeg → 성공"으로 처리해서 **갑자기 되기 시작한 것**처럼 보임.

---

## 5. ffmpeg 변환

- 브라우저 녹음 형식(WebM, MP4, Ogg 등)은 **ffmpeg 한 번 거치면 WAV**로 변환 가능.
- CosyVoice Dockerfile에 ffmpeg 설치되어 있음.
- 사용 예: `ffmpeg -i (입력) -ar 16000 -ac 1 -f wav (출력.wav) -y`

---

## 6. 적용/배포 시 참고

| 변경 | 반영 방법 |
|------|------------|
| CosyVoice (extract_tokens_api.py) | 파일 볼륨 마운트 → **컨테이너 재시작**만 하면 됨 (`docker restart cosyvoice_service`) |
| 백엔드 (VoiceController.java) | **이미지 재빌드** 후 컨테이너 재시작 (`docker-compose up -d --build robot_server`) |
| 프론트 (RobotContext.jsx) | 로컬 `npm run dev`면 저장만으로 반영. Docker로 띄운 경우 클라이언트 이미지 재빌드 후 재시작 |

---

## 7. 관련 문서

- [API_ERROR_RESOLUTION_500_403.md](./API_ERROR_RESOLUTION_500_403.md) – API 404/500/403 해결
- [TTS_DEBUG_CHECKLIST.md](./TTS_DEBUG_CHECKLIST.md) – TTS/목소리 학습 디버깅
