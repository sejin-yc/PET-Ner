package com.ssafy.robot_server.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.domain.UserVoice;
import com.ssafy.robot_server.repository.UserRepository;
import com.ssafy.robot_server.repository.UserVoiceRepository;
import com.ssafy.robot_server.service.DefaultTokenService;
import com.ssafy.robot_server.service.VoiceJetsonSyncService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.*;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.Duration;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/user/voice")
@RequiredArgsConstructor
@Tag(name = "목소리 학습", description = "목소리 학습 및 음성 토큰 관리 API")
public class VoiceController {

    private final UserVoiceRepository userVoiceRepository;
    private final UserRepository userRepository;
    private final VoiceJetsonSyncService voiceJetsonSyncService;
    private final DefaultTokenService defaultTokenService;
    private final RestTemplate restTemplate = createRestTemplateWithLongTimeout();
    private final ObjectMapper objectMapper = new ObjectMapper();

    /** CosyVoice /synthesize 첫 호출 시 모델 로딩으로 시간이 걸리므로 읽기 타임아웃 2분 */
    private static RestTemplate createRestTemplateWithLongTimeout() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(10));
        factory.setReadTimeout(Duration.ofSeconds(120));
        RestTemplate rt = new RestTemplate();
        rt.setRequestFactory(factory);
        return rt;
    }

    private static final String UPLOAD_DIR = "/app/uploads/voices/";

    @Value("${cosyvoice.service.url:http://cosyvoice_service:50001}")
    private String cosyvoiceServiceUrl;

    @PostMapping("/train")
    @Operation(summary = "목소리 학습")
    @Transactional
    public ResponseEntity<?> trainVoice(
            @RequestParam("userId") Long userId,
            @RequestParam("promptText") String promptText,
            @RequestParam("audio") MultipartFile audioFile) {

        try {
            Path uploadPath = Paths.get(UPLOAD_DIR);
            Files.createDirectories(uploadPath);

            String fileName = userId + "_" + System.currentTimeMillis() + ".wav";
            Path filePath = uploadPath.resolve(fileName);
            audioFile.transferTo(filePath.toFile());

            if (!Files.exists(filePath)) {
                throw new IOException("파일 저장 후 확인 실패: " + filePath);
            }

            String audioUrl = "/uploads/voices/" + fileName;

            String speechTokens = null;
            String embeddings = null;

            try {
                HttpHeaders headers = new HttpHeaders();
                headers.setContentType(MediaType.MULTIPART_FORM_DATA);
                MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
                body.add("prompt_text", promptText);
                body.add("audio_file", new FileSystemResource(filePath.toFile()));
                HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

                ResponseEntity<Map> response = restTemplate.postForEntity(
                    cosyvoiceServiceUrl + "/extract_tokens",
                    requestEntity,
                    Map.class
                );

                if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                    Map<String, Object> responseBody = response.getBody();
                    if (Boolean.TRUE.equals(responseBody.get("success"))) {
                        Map<String, Object> tokens = (Map<String, Object>) responseBody.get("tokens");
                        speechTokens = objectMapper.writeValueAsString(tokens);
                        embeddings = objectMapper.writeValueAsString(Map.of(
                            "llm_embedding", tokens.get("llm_embedding"),
                            "flow_embedding", tokens.get("flow_embedding")
                        ));
                    } else {
                        speechTokens = "{\"error\": \"CosyVoice success=false\"}";
                        embeddings = "{\"error\": \"CosyVoice success=false\"}";
                    }
                } else {
                    speechTokens = "{\"error\": \"CosyVoice response not OK\"}";
                    embeddings = "{\"error\": \"CosyVoice response not OK\"}";
                }
            } catch (Exception e) {
                speechTokens = "{\"error\": \"토큰 추출 실패: " + e.getMessage() + "\"}";
                embeddings = "{\"error\": \"임베딩 추출 실패: " + e.getMessage() + "\"}";
            }

            // 해당 사용자의 기존 활성 음성 모두 비활성화 (사용자당 하나의 활성 음성만 유지)
            userVoiceRepository.deactivateAllByUserId(userId);

            UserVoice userVoice = UserVoice.builder()
                    .userId(userId)
                    .promptText(promptText)
                    .audioUrl(audioUrl)
                    .speechTokens(speechTokens)
                    .embeddings(embeddings)
                    .createdAt(LocalDateTime.now())
                    .isActive(true)
                    .build();

            UserVoice saved = userVoiceRepository.save(userVoice);

            // 학습 완료 직후 해당 유저 토큰을 Jetson으로 전송 (JETSON_VOICE_URL 설정 시만)
            voiceJetsonSyncService.syncTokenToJetson(userId);

            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "목소리 학습이 완료되었습니다.");
            response.put("voiceId", saved.getId());
            response.put("audioUrl", audioUrl);

            return ResponseEntity.ok(response);

        } catch (IOException e) {
            Map<String, Object> error = new HashMap<>();
            error.put("success", false);
            error.put("message", "파일 저장 실패: " + e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("success", false);
            error.put("message", "목소리 학습 실패: " + e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }

    @GetMapping("/all")
    @Operation(summary = "DB 전체 음성·토큰 목록 조회")
    public ResponseEntity<?> getAllVoices() {
        List<UserVoice> all = userVoiceRepository.findAll();
        Map<String, Object> response = new HashMap<>();
        response.put("total", all.size());
        response.put("voices", all);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/{userId}")
    @Operation(summary = "사용자 목소리 정보 조회")
    public ResponseEntity<?> getUserVoice(@PathVariable Long userId) {
        Optional<UserVoice> userVoice = userVoiceRepository.findByUserIdAndIsActiveTrueOrderByCreatedAtDesc(userId);
        if (userVoice.isPresent()) {
            return ResponseEntity.ok(userVoice.get());
        }
        Map<String, Object> response = new HashMap<>();
        response.put("hasVoice", false);
        response.put("message", "학습된 목소리가 없습니다.");
        return ResponseEntity.ok(response);
    }

    /**
     * 로그인 후 등에서 호출: 해당 userId의 음성 토큰이 있으면 Jetson으로 미리 전송.
     * JETSON_VOICE_URL이 설정된 경우에만 동작.
     */
    @PostMapping("/jetson/sync")
    @Operation(summary = "Jetson 음성 토큰 동기화 (해당 유저 토큰 전송)")
    public ResponseEntity<?> syncTokenToJetson(@RequestParam("userId") Long userId) {
        voiceJetsonSyncService.syncTokenToJetson(userId);
        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("message", "Jetson 동기화 요청 완료 (Jetson URL 미설정 시 전송되지 않음)");
        return ResponseEntity.ok(response);
    }

    @GetMapping("/{userId}/status")
    @Operation(summary = "목소리 학습 상태 확인")
    public ResponseEntity<?> getVoiceStatus(@PathVariable Long userId) {
        List<UserVoice> voices = userVoiceRepository.findByUserIdAndIsActiveTrue(userId);
        Map<String, Object> response = new HashMap<>();
        response.put("hasVoice", !voices.isEmpty());
        response.put("count", voices.size());
        if (!voices.isEmpty()) {
            response.put("latestVoice", voices.get(0));
        }
        return ResponseEntity.ok(response);
    }

    /**
     * TTS: 사용자 입력 텍스트 + 해당 사용자 음성 토큰으로 합성 음성 반환
     * 경로는 반드시 /tts/speak 만 사용 (POST /speak 은 GET /{userId} 와 충돌하여 405 발생)
     */
    @PostMapping("/tts/speak")
    @Operation(summary = "TTS 합성 (텍스트 + 사용자 음성 토큰 → WAV)")
    public ResponseEntity<?> speak(
            @RequestParam("userId") Long userId,
            @RequestParam("text") String text,
            @RequestParam(required = false, defaultValue = "false") boolean useDefaultVoice) {
        System.out.println("[voice/speak] 요청 userId=" + userId + " useDefaultVoice=" + useDefaultVoice);
        Optional<UserVoice> opt = userVoiceRepository.findByUserIdAndIsActiveTrueOrderByCreatedAtDesc(userId);
        if (opt.isEmpty()) {
            opt = userVoiceRepository.findFirstByUserIdOrderByCreatedAtDesc(userId);
            if (opt.isPresent()) {
                System.out.println("[voice/speak] userId=" + userId + " 활성 행 없음 → 같은 user_id 최신 행 사용 (id=" + opt.get().getId() + ")");
            }
        }
        String speechTokensJson;
        String tokenSource; // 로그용: "user_voice" 또는 "default_{profileId}"
        boolean useDefault = useDefaultVoice || opt.isEmpty();

        if (useDefault) {
            // useDefaultVoice 요청이거나 UserVoice 없음 → 기본 토큰 사용
            System.out.println("[voice/speak] userId=" + userId + (useDefaultVoice ? " 기본 음성 사용 요청 → 기본 토큰 사용" : " UserVoice 없음 → 기본 토큰 사용"));
            Optional<User> userOpt = userRepository.findById(userId);
            if (userOpt.isEmpty()) {
                Map<String, Object> error = new HashMap<>();
                error.put("success", false);
                error.put("message", "사용자를 찾을 수 없습니다.");
                return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
            }
            User user = userOpt.get();
            try {
                String profileId = defaultTokenService.getProfileId(user.getAge(), user.getGender());
                Map<String, Object> defaultTokens = defaultTokenService.loadDefaultTokens(profileId);
                speechTokensJson = objectMapper.writeValueAsString(defaultTokens);
                tokenSource = "default_" + profileId;
                System.out.println("[voice/speak] 기본 토큰 로드 완료: " + profileId);
            } catch (IOException e) {
                System.err.println("[voice/speak] 기본 토큰 로드 실패: " + e.getMessage());
                Map<String, Object> error = new HashMap<>();
                error.put("success", false);
                error.put("message", "학습된 목소리가 없고, 기본 음성 토큰도 준비되지 않았습니다. 프로필(나이/성별)을 설정하거나 목소리를 학습해 주세요.");
                return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
            }
        } else {
            System.out.println("[voice/speak] userId=" + userId + " 토큰 조회됨 (voiceId=" + opt.get().getId() + "), CosyVoice 호출");
            UserVoice voice = opt.get();
            speechTokensJson = voice.getSpeechTokens();
            tokenSource = "user_voice_" + voice.getId();
        }
        if (speechTokensJson == null || speechTokensJson.contains("\"error\"")) {
            Map<String, Object> error = new HashMap<>();
            error.put("success", false);
            error.put("message", "유효한 음성 토큰이 없습니다.");
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(error);
        }
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> tokens = objectMapper.readValue(speechTokensJson, Map.class);
            Map<String, Object> body = new HashMap<>();
            body.put("text", text);
            body.put("tokens", tokens);
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(body, headers);
            String synthesizeUrl = cosyvoiceServiceUrl + "/synthesize";
            System.out.println("[voice/speak] CosyVoice 호출: " + synthesizeUrl + " (토큰 출처: " + tokenSource + ")");
            ResponseEntity<byte[]> response = restTemplate.postForEntity(
                    synthesizeUrl,
                    requestEntity,
                    byte[].class
            );
            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                HttpHeaders outHeaders = new HttpHeaders();
                outHeaders.setContentType(MediaType.parseMediaType("audio/wav"));
                return new ResponseEntity<>(response.getBody(), outHeaders, HttpStatus.OK);
            }
            Map<String, Object> error = new HashMap<>();
            error.put("success", false);
            error.put("message", "TTS 합성 실패 (CosyVoice 응답 이상 또는 빈 본문)");
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        } catch (HttpStatusCodeException e) {
            System.err.println("[voice/speak] CosyVoice 오류: " + e.getStatusCode() + " " + e.getResponseBodyAsString());
            Map<String, Object> error = new HashMap<>();
            String body = e.getResponseBodyAsString();
            String detail = e.getMessage();
            if (body != null && !body.isBlank()) {
                try {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> json = objectMapper.readValue(body, Map.class);
                    if (json.containsKey("detail")) detail = String.valueOf(json.get("detail"));
                    else if (json.containsKey("message")) detail = String.valueOf(json.get("message"));
                } catch (Exception ignored) { detail = body.length() > 200 ? body.substring(0, 200) : body; }
            }
            error.put("success", false);
            error.put("message", "TTS 합성 실패: " + detail);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        } catch (Exception e) {
            e.printStackTrace();
            String cause = e.getClass().getSimpleName() + ": " + (e.getMessage() != null ? e.getMessage() : e.toString());
            Map<String, Object> error = new HashMap<>();
            error.put("success", false);
            error.put("message", "TTS 합성 실패: " + cause);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }
}
