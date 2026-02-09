# 기본 음성 토큰 (Default Voice Tokens)

목소리 학습 없이 TTS를 사용할 때, 사용자 프로필(나이/성별)에 맞는 기본 음성 토큰을 저장하는 디렉터리.

---

## 토큰 파일 구조

각 프로필별로 JSON 파일 하나씩:

```
default_tokens/
├── README.md
├── male_20s.json      # 남성 20대
├── male_40s.json      # 남성 40대
├── female_20s.json    # 여성 20대
├── female_40s.json    # 여성 40대
└── neutral.json       # 중립 (age/gender 없을 때 기본값)
```

---

## 토큰 추출 방법

1. **샘플 음성 준비**  
   각 프로필(성별·연령대)에 맞는 음성 샘플 WAV 파일 준비 (3~5초, 16kHz 권장).  
   예: `male_20s_sample.wav`, `female_40s_sample.wav` 등.

2. **CosyVoice `/extract_tokens` 호출**  
   로컬 Docker `cosyvoice_service` 실행 후:
   ```bash
   curl -X POST http://localhost:50001/extract_tokens \
     -F "prompt_text=안녕하세요 반갑습니다" \
     -F "audio_file=@male_20s_sample.wav" \
     > male_20s.json
   ```
   또는 프론트엔드 "보이스 클로닝" 화면에서 샘플 음성 업로드 → 응답 JSON을 복사해서 파일로 저장.

3. **JSON 파일 저장**  
   추출된 토큰 JSON을 이 디렉터리에 `{profile_id}.json` 형식으로 저장.  
   예: `male_20s.json`, `female_20s.json` 등.

---

## 프로필 ID 매핑 규칙

User의 age, gender → profile_id:

| age | gender | profile_id |
|-----|--------|------------|
| 10~29 | M | male_20s |
| 30~49 | M | male_40s |
| 50+ | M | male_40s (또는 male_60s 추가) |
| 10~29 | F | female_20s |
| 30~49 | F | female_40s |
| 50+ | F | female_40s (또는 female_60s 추가) |
| null | null | neutral |

백엔드 코드에서 위 규칙에 따라 `{profile_id}.json` 파일을 로드.

---

## 사용 예시 (백엔드)

```java
String profileId = getProfileId(user.getAge(), user.getGender()); // "male_20s"
String tokenPath = "classpath:default_tokens/" + profileId + ".json";
Resource resource = resourceLoader.getResource(tokenPath);
String tokensJson = new String(resource.getInputStream().readAllBytes());
Map<String, Object> tokens = objectMapper.readValue(tokensJson, Map.class);
// tokens를 /synthesize에 전달
```

---

## 참고

- 토큰 JSON 형식은 `/extract_tokens` 응답과 동일 (prompt_text_token, llm_embedding, flow_embedding 등).
- 샘플 음성은 저작권 문제 없는 것으로 준비 (직접 녹음 또는 오픈 데이터셋).
- 최소 2~4개 프로필(male_20s, male_40s, female_20s, female_40s) + neutral 하나면 충분.
