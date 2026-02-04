# 음성 토큰 추출 체크리스트

목소리 학습 시 DB에 `speech_tokens` / `embeddings`가 `pending`이거나 비어 있을 때, 아래 항목을 **순서대로** 확인하세요.

---

## 1. 인프라 (Docker)

| # | 항목 | 확인 방법 | 통과 예시 |
|---|------|-----------|-----------|
| 1.1 | Docker Desktop 실행 중 | 작업 표시줄에 Docker 아이콘 | 실행 중 |
| 1.2 | `cosyvoice_service` 컨테이너 기동 | `docker compose ps` | `cosyvoice_service` Up |
| 1.3 | CosyVoice 모델 로드 완료 | `docker compose logs cosyvoice_service` | `CosyVoice model loaded successfully` |
| 1.4 | `robot_server` 컨테이너 기동 | `docker compose ps` | `robot_server` Up |
| 1.5 | `robot_db` 컨테이너 기동 | `docker compose ps` | `robot_db` Up |

**실패 시:**  
- 1.2~1.4: `docker compose up -d` 후 `docker compose logs -f <서비스명>` 으로 로그 확인  
- 1.3: 모델 첫 다운로드 시 오래 걸릴 수 있음. `Loading CosyVoice model from: FunAudioLLM/Fun-CosyVoice3-0.5B-2512` 후 완료 대기  

---

## 2. CosyVoice 서비스 (토큰 추출 API)

| # | 항목 | 확인 방법 | 통과 예시 |
|---|------|-----------|-----------|
| 2.1 | `/health` 응답 | `Invoke-WebRequest http://localhost:50001/health` 또는 브라우저 | `{"status":"ok","model_loaded":true}` |
| 2.2 | `/extract_tokens` 호출 가능 | 아래 "수동 테스트" 참고 | 200 + `{"success":true,"tokens":{...}}` |

**수동 테스트 (PowerShell):**
```powershell
$wav = Get-Item ".\uploads\voices\1_1769624393354.wav"  # 실제 있는 파일로 변경
$form = @{
  prompt_text = "안녕하세요"
  audio_file = $wav
}
Invoke-WebRequest -Uri "http://localhost:50001/extract_tokens" -Method POST -Form $form
```

---

## 3. 백엔드 (Spring Boot)

| # | 항목 | 확인 방법 | 통과 예시 |
|---|------|-----------|-----------|
| 3.1 | `COSYVOICE_SERVICE_URL` 설정 | `docker-compose.yml` → `robot_server` env | `http://cosyvoice_service:50001` |
| 3.2 | `robot_server` ↔ `cosyvoice_service` 네트워크 | 같은 `robot_network` | `docker compose` 기본으로 동일 네트워크 |
| 3.3 | `/user/voice/train` 호출 시 CosyVoice 호출 | `docker compose logs robot_server` | `CosyVoice 토큰 추출 실패` **없음** |
| 3.4 | 업로드 디렉터리 | 컨테이너 내 `/app/uploads/voices/` ↔ 호스트 `./uploads` | 볼륨 마운트로 공유 |

**실패 시:**  
- 3.3: 로그에 `CosyVoice 토큰 추출 실패: ...` 있으면 → 2번(CosyVoice) + 3.1, 3.2 확인  
- 3.4: `docker compose` volume `./uploads:/app/uploads` 확인  

---

## 4. 프론트엔드 (클라이언트)

| # | 항목 | 확인 방법 | 통과 예시 |
|---|------|-----------|-----------|
| 4.1 | 목소리 학습 API URL | `RobotContext` → `sendVoiceToServer` | `http://localhost:8080/user/voice/train` |
| 4.2 | FormData 필드명 | `userId`, `promptText`, `audio` | 백엔드 `@RequestParam`과 동일 |
| 4.3 | `Content-Type` (multipart) | **설정하지 않음** (axios 자동) | `multipart/form-data; boundary=...` |
| 4.4 | `user.id` 전달 | 로그인 상태에서 목소리 학습 | `formData.append('userId', user.id)` |

**주의:**  
- 4.3: `Content-Type: multipart/form-data` 를 **수동으로** 넣으면 boundary가 빠져서 multipart 파싱 실패 → **제거**해야 함.

---

## 5. API 계약 (필드명 일치)

| 구간 | 필드 | 기대값 |
|------|------|--------|
| 프론트 → 백엔드 | `userId`, `promptText`, `audio` | ✓ 일치 |
| 백엔드 → CosyVoice | `prompt_text`, `audio_file` | ✓ 일치 |
| CosyVoice 응답 | `success`, `tokens`(→ `llm_embedding`, `flow_embedding`) | ✓ VoiceController에서 사용 |

---

## 6. DB 확인

| # | 항목 | 확인 방법 |
|---|------|-----------|
| 6.1 | 최신 행 조회 | `SELECT id, created_at, LEFT(speech_tokens,80), LEFT(embeddings,80) FROM user_voices WHERE user_id=1 ORDER BY created_at DESC LIMIT 1;` |
| 6.2 | `pending` / `error` | `speech_tokens` 또는 `embeddings`에 `"status":"pending"` / `"error"` 포함 여부 |

**해석:**  
- `pending`: 예전 로직으로 저장된 데이터일 가능성 (현재 코드에는 없음).  
- `"error":"..."`: CosyVoice 호출 실패 → 2, 3번 재확인.  
- 실제 토큰 JSON(배열 등): 정상 동작.

---

## 7. 권장 확인 순서 (요약)

1. **1번** → Docker·서비스 모두 Up, CosyVoice 로그에서 `model loaded` 확인  
2. **2번** → `/health` → `/extract_tokens` 수동 테스트  
3. **4.3** → FormData 요청 시 `Content-Type` 수동 설정 제거  
4. **3번** → `robot_server` 로그에서 CosyVoice 에러 여부 확인  
5. **6번** → DB에서 최신 행 `speech_tokens` / `embeddings` 확인  

---

## 8. 자주 나오는 원인

| 증상 | 가능 원인 | 조치 |
|------|-----------|------|
| DB에 `pending` | 예전 코드로 저장된 행 | **새로** 목소리 학습 한 번 더 한 뒤 6번으로 확인 |
| DB에 `"error":"..."` | CosyVoice 호출 실패 | 2번, 3.1, 3.2, 3.3 확인 |
| 파일 저장 실패 (4xx/5xx) | `/app/uploads/voices` 없음/권한 | volume 마운트·경로 확인, `uploads/voices` 생성 |
| multipart 파싱 에러 | `Content-Type` 수동 설정 | 4.3 적용 후 FormData만 보내기 |
| CosyVoice 503 | 모델 미로드 | 1.3, 2.1 확인 |

이 체크리스트대로 진행해도 계속 실패하면,  
`docker compose logs robot_server` / `docker compose logs cosyvoice_service` 의  
**에러 로그 일부**를 붙여 주면 원인 좁히기 좋습니다.
