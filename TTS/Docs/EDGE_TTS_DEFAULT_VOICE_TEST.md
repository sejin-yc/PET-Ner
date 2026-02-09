# 기본 TTS (Edge TTS) 웹 테스트

- **기본 음성** (학습 없음 / useDefaultVoice): **Edge TTS** (한국어 SunHi/InJoon). 예전에 쓰던 default_tokens + CosyVoice /synthesize 는 사용 안 함.
- **사용자 음성 학습** 있음: **CosyVoice** /synthesize (학습된 토큰) 그대로 사용.

## 사양

- **음성**: 성별만 사용 → M = InJoon (남), F = SunHi (여). **DB에 성별 없으면 M.**
- **출력**: WAV, 모노, 16비트, 44.1 kHz
- **확인용 저장**: Edge TTS 호출 시 WAV 자동 저장
  - Docker: `S14P11C203/uploads/edge_tts_output/edge_tts_M_20260129_123456.wav` 형식
  - 로컬: `cosyvoice_service/uploads/edge_tts_output/`

## 웹에서 테스트 순서

1. **서비스 기동**
   ```bash
   cd S14P11C203
   docker compose up -d robot_db robot_mqtt cosyvoice_service robot_server robot_client robot_nginx
   ```

2. **cosyvoice_service 확인**  
   Edge TTS는 GPU 없이 동작. 헬스 확인:
   ```bash
   curl -s http://127.0.0.1:50001/health
   ```

3. **기본 TTS API 직접 호출 (선택)**
   ```bash
   curl -X POST "http://127.0.0.1:50001/synthesize_edge_tts" \
     -H "Content-Type: application/json" \
     -d "{\"text\":\"안녕하세요. 테스트입니다.\",\"gender\":\"M\"}" \
     -o test.wav
   ```
   `test.wav` 재생해서 확인.

4. **웹에서 테스트**
   - 로그인 후 대시보드(또는 TTS 입력 화면)로 이동
   - 텍스트 입력 후 **재생** 클릭
   - **학습한 목소리 없음** → 기본 음성(Edge TTS) 사용. 성별 없으면 남성(InJoon).
   - 재생이 되고 한국어가 자연스럽게 나오면 성공.

## 문제 시 확인

- 브라우저 콘솔: `[voice/speak]` 또는 네트워크 탭에서 `/user/voice/tts/speak` 요청/응답 확인
- 서버 로그: `Edge TTS 호출`, `Edge TTS OK` 또는 오류 메시지 확인
- 성별 반영: DB `user.gender` = M/F 여부 (없으면 M)
