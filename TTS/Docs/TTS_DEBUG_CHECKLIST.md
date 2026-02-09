# TTS / 서버 상태 확인 방법

## 1. useDefaultVoice · 어떤 경로로 갔는지

### 브라우저 (Network)
1. **F12** → **Network** 탭
2. TTS 재생 버튼 클릭
3. **speak** 요청 클릭
4. **Headers** 탭에서 확인:
   - **Request URL**  
     - `useDefaultVoice=true` → Edge TTS (기본 목소리, GPU 미사용)  
     - `useDefaultVoice=false` → CosyVoice (내 목소리, GPU 사용)
   - **Payload** 탭에서 본문 `userId`, `text`, `useDefaultVoice` 값 확인

### 브라우저 (Console)
- TTS 호출 시 `[TTS] userId=... useClonedVoice=... useDefaultVoice=...` 로그가 찍힘  
  → useDefaultVoice가 true/false 중 무엇으로 나가는지 확인

---

## 2. Spring 서버 로그 (어떤 경로로 요청이 갔는지)

### Docker로 실행 중일 때
```powershell
docker logs robot_server -f --tail 100
```
- TTS 요청 시 예시:
  - `[voice/speak] userId=2 useDefaultVoice=true hasTokens=true → useDefault=true → Edge TTS`
  - `[voice/speak] userId=2 useDefaultVoice=false hasTokens=true → useDefault=false → CosyVoice`

### IDE에서 Spring 실행 중일 때
- 실행 중인 터미널/콘솔 창에서 위와 같은 `[voice/speak]` 로그 확인

---

## 3. CosyVoice 서비스 로그 (Edge TTS vs CosyVoice)

### Docker로 실행 중일 때
```powershell
docker logs cosyvoice_service -f --tail 100
```
- **기본 목소리(Edge TTS)** 요청이 들어오면:
  - `Edge TTS 요청 수신 (GPU 미사용 경로)` 로그 출력
- **내 목소리(CosyVoice)** 요청이 들어오면:
  - `CosyVoice /synthesize 요청 수신 (GPU 사용)` 로그 출력
- CUDA OOM이 나면 같은 로그 뒤에 `RuntimeError: CUDA error: out of memory` 스택 트레이스가 찍힘

### 로컬에서 Python으로 실행 중일 때
- `extract_tokens_api.py` 를 실행한 터미널에서 위와 같은 로그 확인

---

## 4. GPU 사용량 (CUDA OOM 원인 확인)

### nvidia-smi
```powershell
nvidia-smi
```
- **Memory-Usage**: 현재 GPU 메모리 사용량
- **Processes**: 어떤 프로세스가 GPU를 쓰는지
- CosyVoice TTS 실행 중/직후에 사용량이 크게 올라가면 VRAM 부족 가능

### 주기적으로 보기
```powershell
nvidia-smi -l 2
```
- 2초마다 갱신

---

## 5. 환경 변수 (USE_FP16, PRELOAD_TTS 등)

### Docker Compose 사용 시
- `S14P11C203/docker-compose.yml` 안의 `cosyvoice_service` → `environment:` 확인
- 예: `USE_FP16: "true"`, `USE_STREAM_INFERENCE: "true"` 등

### 컨테이너 안에서 확인
```powershell
docker exec cosyvoice_service env | findstr -i "FP16 PRELOAD STREAM"
```

---

## 6. 한 번에 확인하는 순서 (TTS 500 / OOM 시)

1. **Network**  
   - speak 요청의 `useDefaultVoice` 값 확인 (true → Edge TTS, false → CosyVoice)
2. **Spring 로그**  
   - `→ Edge TTS` / `→ CosyVoice` 로 실제 호출 경로 확인
3. **cosyvoice_service 로그**  
   - `Edge TTS 요청 수신` vs `CosyVoice /synthesize 요청 수신` 확인  
   - OOM이면 그 뒤에 CUDA 에러 스택 확인
4. **nvidia-smi**  
   - GPU 메모리 사용량·프로세스 확인

이 순서로 보면 “어디서”, “어떤 경로로”, “왜” 실패했는지 구분할 수 있습니다.
