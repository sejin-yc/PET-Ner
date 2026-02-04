# 기본 TTS 로컬 테스트 가이드

목소리 학습 없이 기본 토큰으로 TTS를 사용하는 기능을 로컬에서 테스트하는 방법.

---

## 전제 조건

1. **기본 토큰 파일 준비**  
   `server/src/main/resources/default_tokens/` 에 최소 `neutral.json` 하나는 있어야 함.
   
2. **토큰 추출 방법**  
   - 로컬 Docker `cosyvoice_service` 실행  
   - 샘플 음성 WAV 파일 하나 준비 (3~5초, 아무 목소리나)  
   - 프론트엔드 "보이스 클로닝" 또는 curl로 `/extract_tokens` 호출:
     ```bash
     curl -X POST http://localhost:50001/extract_tokens \
       -F "prompt_text=안녕하세요 반갑습니다" \
       -F "audio_file=@sample.wav" \
       -o neutral.json
     ```
   - 생성된 `neutral.json` 을 `server/src/main/resources/default_tokens/` 에 복사

3. **Docker 서비스 실행**  
   ```bash
   cd S14P11C203
   docker compose up -d robot_db robot_mqtt cosyvoice_service robot_server robot_client robot_nginx
   ```

---

## 테스트 시나리오

### 1. 목소리 학습 안 한 유저 준비

- 회원가입 또는 기존 유저 중 `user_voices` 테이블에 행이 없는 유저 선택
- 또는 `user_voices` 에서 해당 userId 행을 모두 삭제

### 2. 프로필 설정 (선택)

- 로그인 → 설정 화면 → 나이/성별 입력 후 저장
- 예: 나이 25, 성별 M → `male_20s.json` 사용 (파일 있으면)
- 나이/성별 없으면 → `neutral.json` 사용

### 3. TTS 재생 테스트

1. 대시보드 → 텍스트 입력 (예: "안녕하세요 테스트입니다")
2. "재생" 버튼 클릭
3. **예상 동작:**
   - 백엔드: UserVoice 없음 → User age/gender로 기본 토큰 로드 → `/synthesize` 호출
   - CosyVoice: 기본 토큰 + 텍스트로 WAV 생성
   - 프론트: WAV 수신 → 재생
4. **확인:**
   - 콘솔 로그: `[voice/speak] 기본 토큰 로드 완료: neutral` (또는 male_20s 등)
   - 브라우저: 음성 재생 성공

### 4. 에러 케이스

- 기본 토큰 파일도 없으면:  
  `"학습된 목소리가 없고, 기본 음성 토큰도 준비되지 않았습니다. 프로필(나이/성별)을 설정하거나 목소리를 학습해 주세요."`

---

## 체크리스트

- [ ] `default_tokens/neutral.json` 생성 (샘플 음성 → `/extract_tokens`)
- [ ] (선택) `male_20s.json`, `female_20s.json` 등 추가 프로필 생성
- [ ] Docker 서비스 실행 (`docker compose up -d`)
- [ ] 목소리 학습 안 한 유저로 로그인
- [ ] 대시보드에서 텍스트 입력 → 재생 클릭
- [ ] 음성 재생 성공 확인
- [ ] 백엔드 로그에서 "기본 토큰 로드 완료" 메시지 확인

---

## 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| "기본 음성 토큰도 준비되지 않았습니다" | `neutral.json` 없음 | 위 "토큰 추출 방법"으로 생성 |
| "사용자를 찾을 수 없습니다" | userId가 DB에 없음 | 로그인한 유저 ID 확인 |
| 500 에러 | cosyvoice_service 안 떠 있음 | `docker compose up -d cosyvoice_service` |
