# API 404, 500, 403 에러 해결 과정 정리

> TTS 브랜치를 FE,BE,Infra에 머지한 후 발생한 API 에러들의 원인과 해결 방법을 정리한 문서입니다.

---

## 목차

1. [요약](#1-요약)
2. [404 에러 (경로 없음)](#2-404-에러-경로-없음)
3. [500 에러 (서버 내부 오류)](#3-500-에러-서버-내부-오류)
4. [403 에러 (인증 거부)](#4-403-에러-인증-거부)
5. [최종 결과 및 검증](#5-최종-결과-및-검증)

---

## 1. 요약

| 순서 | 에러 | 원인 | 해결 |
|------|------|------|------|
| 1 | 404 | 프론트 경로(`/api/user/logs`) ≠ 백엔드(`/api/logs`) | 프론트 경로 수정 |
| 2 | 404 | VoiceController에 `/api/user/voice` 미매핑 | RequestMapping 추가 |
| 3 | 404 | context-path 미설정, 경로 혼재 | context-path: /api, 컨트롤러 경로 단순화 |
| 4 | 500 | JWT_SECRET 16자 (256비트 미만) | JWT_SECRET 32자 이상으로 변경 |
| 5 | 500 | PostgreSQL 비밀번호 인증 실패 (한글/인코딩) | .env 비밀번호 ASCII로 통일 |
| 6 | 500 | `postgres_data` bind mount에 예전 DB 남아 있음 | postgres_data 폴더 삭제 후 재시작 |
| 7 | 403 | context-path `/api` 환경에서 Security 경로 매칭 실패 | permitAll에 `/api` 포함·미포함 경로 모두 추가 |
| 8 | 500 | 컨트롤러 예외 발생 시 로그/응답 부족 | GlobalExceptionHandler 추가 |

---

## 2. 404 에러 (경로 없음)

### 2.1 프론트-백엔드 경로 불일치

**증상**
- `GET /api/cats?userId=2` → 404
- `GET /api/logs?userId=2` → 404

**원인**
- TTS 머지 시 프론트가 `/api/user/logs`, `/api/user/cats`로 호출
- 백엔드 LogController, CatController는 `/api/logs`, `/api/cats`만 노출 (FE,BE,Infra 설계)

**해결**
- `RobotContext.jsx`: `/user/logs` → `/logs`, `/user/logs/${id}` → `/logs/${id}`
- `PetContext.jsx`: `/user/cats` → `/cats`, `/user/cats` (POST) → `/cats`

### 2.2 VoiceController 경로 누락

**증상**
- `POST /api/user/voice/tts/speak` → 404
- `GET /api/user/voice/2/status` → 404

**원인**
- Vite 프록시가 `/api` prefix를 그대로 전달 → 백엔드는 `/api/user/voice/...` 수신
- VoiceController는 `@RequestMapping("/user/voice")`만 있어 `/api` prefix와 매칭되지 않음

**해결**
```java
@RequestMapping({"/user/voice", "/api/user/voice"})
```

### 2.3 context-path 설정 및 경로 통일

**증상**
- API 전체 404 (cats, logs, robot/state, user/voice 등)

**원인**
- context-path 미설정, 여러 경로 패턴 혼재로 Spring Boot가 일관되게 매핑하지 못함

**해결**
- `application.yml`:
  ```yaml
  server:
    port: 8080
    servlet:
      context-path: /api
  ```
- 컨트롤러는 짧은 경로만 사용: `/logs`, `/cats`, `/robot`, `/user/voice` 등
- 프론트 요청 `/api/logs` → context `/api` + 매핑 `/logs` → 정상 처리

---

## 3. 500 에러 (서버 내부 오류)

### 3.1 JWT WeakKeyException (Tomcat 기동 실패)

**증상**
```
Caused by: io.jsonwebtoken.security.WeakKeyException: The specified key byte array is 120 bits 
which is not secure enough for any JWT HMAC-SHA algorithm.
```

**원인**
- `JWT_SECRET=your-jwt-secret` (16자 = 128비트)
- JWT HMAC-SHA 알고리즘은 최소 256비트(32자) 요구

**해결**
- `.env`:
  ```
  JWT_SECRET=your-jwt-secret-key-must-be-at-least-32-characters-long
  ```

### 3.2 PostgreSQL 비밀번호 인증 실패

**증상**
```
Caused by: org.postgresql.util.PSQLException: FATAL: password authentication failed for user "postgres"
```

**원인**
- `.env`에 `SPRING_DATASOURCE_PASSWORD=비밀번호` (한글)
- Docker/PostgreSQL 환경에서 인코딩·전달 문제 가능성

**해결**
- `.env`:
  ```
  SPRING_DATASOURCE_USERNAME=postgres
  SPRING_DATASOURCE_PASSWORD=postgres123
  ```

### 3.3 postgres_data bind mount (DB 초기화 안 됨)

**증상**
- `.env` 비밀번호 수정 후에도 동일한 `password authentication failed` 에러 지속

**원인**
- `docker-compose down -v`는 **named volume**만 제거
- `postgres_data`는 **bind mount** (`./postgres_data:/var/lib/postgresql/data`)
- 로컬 폴더는 `-v`로 삭제되지 않음
- 예전 비밀번호로 초기화된 DB가 그대로 사용됨

**해결**
```powershell
docker-compose down
Remove-Item -Recurse -Force postgres_data
docker-compose up -d
```

> ⚠️ **주의**: `postgres_data` 삭제 시 DB 데이터가 모두 삭제됩니다. 테스트 환경에서만 사용하세요.

### 3.4 GlobalExceptionHandler 추가

**목적**
- 컨트롤러/서비스에서 예외 발생 시 로그·응답 형식 부족
- 실제 예외 원인 파악 어려움

**해결**
- `GlobalExceptionHandler.java` 생성
- `@RestControllerAdvice`로 전역 예외 처리
- 예외 로그 출력 + JSON 응답 반환

```java
@ExceptionHandler(Exception.class)
public ResponseEntity<Map<String, Object>> handleException(Exception e) {
    log.error("API 예외 발생: ", e);
    Map<String, Object> body = new HashMap<>();
    body.put("success", false);
    body.put("message", e.getMessage());
    body.put("type", e.getClass().getSimpleName());
    return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(body);
}
```

---

## 4. 403 에러 (인증 거부)

### 4.1 Spring Security 경로 매칭 실패

**증상**
- DB 연결 성공, 백엔드 기동 완료 후
- `GET /api/cats?userId=2` → 403 Forbidden
- `GET /api/logs?userId=2` → 403 Forbidden
- `GET /api/user/voice/2/status` → 403 Forbidden

**원인**
- `context-path: /api` 적용 시, Spring Security가 받는 경로 형식이 달라질 수 있음
- 일부 환경에서는 `/api/cats`가 아닌 `/cats`로 전달될 수 있음
- `requestMatchers("/api/cats/**")`만 있으면 매칭되지 않아 `anyRequest().authenticated()`로 떨어짐
- JWT 없이 요청 시 403 반환

**해결**
- `SecurityConfig.java`에서 permitAll 패턴에 **두 가지 형식 모두** 추가:

```java
.requestMatchers("/api/user/**", "/api/users/**", "/user/**", "/users/**").permitAll()
.requestMatchers("/api/cat/**", "/api/cats/**", "/cat/**", "/cats/**", 
                 "/api/video/**", "/api/videos/**", "/video/**", "/videos/**", 
                 "/api/uploads/**", "/uploads/**").permitAll()
.requestMatchers("/api/log/**", "/api/logs/**", "/log/**", "/logs/**").permitAll()
.requestMatchers("/api/robot/**", "/robot/**").permitAll()
.requestMatchers("/api/ros2/**", "/ros2/**", "/api/signal", "/signal", 
                 "/api/ws/**", "/ws/**").permitAll()
.requestMatchers("/api/swagger-ui/**", "/swagger-ui/**", 
                 "/api/v3/api-docs/**", "/v3/api-docs/**", "/api/error", "/error").permitAll()
```

---

## 5. 최종 결과 및 검증

### 5.1 수정된 파일 목록

| 파일 | 변경 내용 |
|------|-----------|
| `client/src/contexts/RobotContext.jsx` | `/user/logs` → `/logs`, `api.get/post/delete` 경로 수정 |
| `client/src/contexts/PetContext.jsx` | `/user/cats` → `/cats` |
| `server/.../controller/VoiceController.java` | `@RequestMapping`에 `/api/user/voice` 추가 (이후 context-path로 단순화) |
| `server/.../resources/application.yml` | `server.servlet.context-path: /api` 추가 |
| `server/.../controller/*.java` | RequestMapping 경로 단순화 (`/logs`, `/cats` 등) |
| `server/.../config/SecurityConfig.java` | permitAll 패턴에 `/api` 포함·미포함 경로 추가 |
| `server/.../security/JwtAuthenticationFilter.java` | try-catch 추가, null-safe, 디버그 로그 제거 |
| `server/.../config/GlobalExceptionHandler.java` | 신규 생성, 전역 예외 처리 |
| `.env` | JWT_SECRET 32자 이상, SPRING_DATASOURCE_PASSWORD ASCII로 변경 |

### 5.2 최종 .env 예시

```env
DB_NAME=robot_db
DB_USER=robot_user
DB_PASSWORD=robot_password
SPRING_DATASOURCE_USERNAME=postgres
SPRING_DATASOURCE_PASSWORD=postgres123
JWT_SECRET=your-jwt-secret-key-must-be-at-least-32-characters-long
MQTT_USERNAME=ssafy
MQTT_PASSWORD=ssafy1
```

### 5.3 검증 방법

1. **백엔드 기동 확인**
   ```powershell
   docker logs robot_server --tail 30
   ```
   - `Started ServerApplication` 출력 확인

2. **API 200 응답 확인**
   - 브라우저 F12 → Network
   - 로그인 후 대시보드 새로고침
   - `cats`, `logs`, `state`, `status` 요청이 **200 OK** 인지 확인

3. **TTS 동작 확인**
   - 기본 목소리 / 내 목소리 토글 후 TTS 재생
   - `POST /api/user/voice/tts/speak` → 200 + audio/wav 응답

### 5.4 Docker 재시작 시 주의사항

- **postgres_data**: bind mount이므로 `docker-compose down -v`로 삭제되지 않음
- 비밀번호 변경 시 `postgres_data` 폴더를 삭제해야 새 DB가 생성됨
- 컨테이너 이름 충돌 시: `docker rm -f robot_db` 또는 `docker rm -f robot_mqtt` 후 재시작

---

## 참고

- [TTS_DEBUG_CHECKLIST.md](./TTS_DEBUG_CHECKLIST.md): TTS 관련 디버깅 방법
- Spring Boot context-path: [공식 문서](https://docs.spring.io/spring-boot/docs/current/reference/html/application-properties.html#application-properties.server.server.servlet.context-path)
- Docker Compose volumes: bind mount vs named volume 동작 차이
