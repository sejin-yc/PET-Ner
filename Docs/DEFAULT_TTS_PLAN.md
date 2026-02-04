# 기본 TTS 구현 계획 (Default TTS Plan)

목소리 학습 없이 **나이/성별**에 따른 기본 음성으로 TTS를 제공하는 기능 구현 계획.

---

## 목표

- 사용자가 목소리를 학습하지 않아도 TTS 사용 가능
- User 프로필(나이, 성별)에 맞는 **기본 음성 토큰**으로 합성
- 로컬에서 Docker 등으로 실행·테스트하여 기본 TTS → 재생 흐름 검증

---

## 선행 조건

- **현재**: `POST /user/voice/tts/speak` 는 `UserVoice` 가 있을 때만 동작 (없으면 404)
- **목표**: `UserVoice` 없을 때 `User` 의 나이/성별로 **기본 토큰** 선택 후 합성

---

## 구현 단계

### 1. User 프로필에 나이/성별 추가

| 항목 | 내용 |
|------|------|
| **대상** | `User` 엔티티 |
| **추가 필드** | `age` (Integer, nullable), `gender` (String, nullable, 예: "M"/"F"/null) |
| **작업** | 엔티티 수정 → DB 마이그레이션(또는 수동 ALTER) → DTO/API 수정 |
| **참고** | 초기에는 nullable로 두고, 프로필 수정 시에만 설정 |

### 2. 프로필에 유저 기본 정보 입력/표시

| 항목 | 내용 |
|------|------|
| **백엔드** | 회원가입/프로필 수정 API에 `age`, `gender` 추가<br>프로필 조회 API에서 `age`, `gender` 반환 |
| **프론트** | 설정/프로필 화면에서 나이·성별 입력/수정 UI<br>대시보드 등에서 프로필 정보 표시 (필요 시) |
| **입력 방식** | 나이: 숫자 입력 또는 연령대 선택 (10대/20대/30대/…)<br>성별: M/F 드롭다운 또는 라디오 |

### 3. 기본 프로필 토큰 준비 (성별·연령대별 음성 샘플 토큰)

| 항목 | 내용 |
|------|------|
| **목표** | 성별·연령대 조합별로 미리 추출한 음성 토큰 준비 |
| **조합 예** | 남성/여성 × 청소년/청년/중년/노년 등 (예: 6~8개 프로필) |
| **작업** | PC에서 CosyVoice `/extract_tokens` 로 각 조합에 맞는 샘플 음성에서 토큰 추출<br>JSON 파일로 저장 (예: `default_tokens/male_20s.json`) |
| **저장 위치** | `server/src/main/resources/default_tokens/` 또는 별도 경로<br>또는 DB 테이블 `default_voice_profile` (id, gender, age_group, speech_tokens) |
| **매핑 규칙** | User.age, User.gender → profile_id (예: male_20s) → 해당 토큰 로드 |

### 4. Jetson에 기본 토큰 전달 방식 결정 및 구현

| 항목 | 내용 |
|------|------|
| **고려사항** | Jetson은 사용자별 토큰만 캐시할 수 있음. 기본 토큰은 프로필 ID만 전달하고, Jetson이 미리 가지고 있거나 백엔드가 매 요청마다 전달 |
| **옵션 A** | Jetson에 기본 토큰 파일들을 미리 배치 (default_tokens/). 요청 시 `profile_id`만 전달, Jetson이 로컬 파일에서 로드 |
| **옵션 B** | 백엔드가 기본 토큰을 DB/리소스에서 읽어 매 요청마다 `/synthesize`에 tokens와 함께 전달 (Jetson은 토큰 캐시 없이 동작) |
| **권장** | **옵션 B** (구현 단순). 기본 토큰은 용량이 크지 않고, Jetson 부담도 상대적으로 적음. 나중에 최적화 시 옵션 A 검토 |
| **작업** | 백엔드에서 `UserVoice` 없을 때 User.age/gender로 profile_id 결정 → 해당 기본 토큰 로드 → `/synthesize` 요청에 포함 |

### 5. 백엔드: 기본 토큰으로 TTS 합성

| 항목 | 내용 |
|------|------|
| **로직** | `VoiceController.speak()`:<br>1) `UserVoice` 조회<br>2) 없으면 `User` 조회 → age, gender로 기본 profile_id 결정<br>3) 기본 토큰 로드 (파일/DB)<br>4) `cosyvoice_service` `/synthesize` 호출 (text + tokens) |
| **기본값** | age/gender가 없으면 중립 프로필(예: female_20s 또는 male_30s) 사용 |
| **에러 처리** | 기본 토큰도 없으면 "기본 음성을 사용할 수 없습니다. 프로필을 설정하거나 목소리를 학습해 주세요." 등 안내 |

### 6. 프론트: 목소리 학습 없이 TTS 사용 및 재생 테스트

| 항목 | 내용 |
|------|------|
| **시나리오** | 1) 목소리 학습 안 한 유저로 로그인<br>2) 대시보드에서 텍스트 입력 후 재생 클릭<br>3) 백엔드가 기본 토큰으로 합성 → WAV 반환<br>4) 프론트가 WAV 재생 |
| **현재** | Dashboard는 `/tts/speak` 호출. `UserVoice` 없으면 404 → "학습된 목소리가 없습니다" 메시지 |
| **목표** | 404 대신 200 + WAV → 재생 성공 |
| **테스트** | 로컬 Docker (cosyvoice_service, robot_server, robot_client) 실행 후 위 시나리오 수행 |

### 7. 학습한 사용자도 기본 음성 선택 가능 (useDefaultVoice)

| 항목 | 내용 |
|------|------|
| **목표** | 학습 품질이 마음에 안 들 때 기본 음성으로 재생할 수 있도록 선택권 제공 |
| **백엔드** | `POST /user/voice/tts/speak` 에 `useDefaultVoice` (optional, default false) 파라미터 추가. `true` 이면 UserVoice 여부와 관계없이 프로필(나이/성별) 기반 기본 토큰으로 합성 |
| **프론트** | 대시보드 음성 제어 섹션에 "기본 음성 사용 (학습 품질이 마음에 안 들 때)" 체크박스 추가. 목소리 학습 완료 시에만 표시, 체크 시 `useDefaultVoice=true` 로 API 호출 |

---

## 작업 순서 요약

| # | 작업 | 산출물 |
|---|------|--------|
| 1 | User에 age, gender 추가 | 엔티티, 마이그레이션, DTO |
| 2 | 프로필 입력/표시 API·UI | API 수정, 프론트 설정 화면 |
| 3 | 기본 토큰 추출·저장 | default_tokens JSON 파일 또는 DB |
| 4 | 기본 토큰 전달 방식 결정 | 설계 확정 (권장: 옵션 B) |
| 5 | VoiceController.speak() 에 기본 토큰 fallback 추가 | 코드 수정 |
| 6 | 로컬 실행 테스트 (학습 없이 TTS → 재생) | 테스트 완료 |
| 7 | 학습자도 기본 음성 선택 가능 (useDefaultVoice + UI) | API 파라미터, 대시보드 체크박스 |

---

## 참고

- CosyVoice `/extract_tokens` 는 PC(Docker cosyvoice_service)에서 동작. 기본 토큰 추출은 PC에서 수행.
- Jetson 배포는 `Docs/REMAINING_TASKS.md` 에 따로 정리. 기본 TTS는 로컬 cosyvoice_service로 먼저 검증.
