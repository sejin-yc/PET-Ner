package com.ssafy.robot_server.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.domain.UserVoice;
import com.ssafy.robot_server.repository.UserVoiceRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * 로그인 시 / 목소리 학습 완료 시 해당 유저의 음성 토큰을 Jetson으로 미리 전송.
 * Jetson URL이 없거나 전송 실패 시 로그만 남기고 예외를 던지지 않음.
 */
@Service
@RequiredArgsConstructor
public class VoiceJetsonSyncService {

    private final UserVoiceRepository userVoiceRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${jetson.voice.url:}")
    private String jetsonVoiceUrl;

    private static final String UPLOAD_TOKEN_PATH = "/voices/upload_token";
    private static final int CONNECT_TIMEOUT_SEC = 5;
    private static final int READ_TIMEOUT_SEC = 15;

    private static RestTemplate createRestTemplate() {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory =
                new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(CONNECT_TIMEOUT_SEC));
        factory.setReadTimeout(Duration.ofSeconds(READ_TIMEOUT_SEC));
        RestTemplate rt = new RestTemplate();
        rt.setRequestFactory(factory);
        return rt;
    }

    private final RestTemplate restTemplate = createRestTemplate();

    /**
     * 해당 userId의 활성 음성 토큰이 있으면 Jetson으로 전송.
     * URL 미설정 또는 전송 실패 시 무시(로그만).
     * 비동기로 실행되어 로그인/학습 응답 지연 없음.
     */
    @Async
    public void syncTokenToJetson(Long userId) {
        if (userId == null) return;
        String baseUrl = jetsonVoiceUrl != null ? jetsonVoiceUrl.trim() : "";
        if (baseUrl.isEmpty()) {
            return;
        }

        Optional<UserVoice> opt = userVoiceRepository.findByUserIdAndIsActiveTrueOrderByCreatedAtDesc(userId);
        if (opt.isEmpty()) {
            opt = userVoiceRepository.findFirstByUserIdOrderByCreatedAtDesc(userId);
        }
        if (opt.isEmpty()) return;

        UserVoice voice = opt.get();
        String speechTokensJson = voice.getSpeechTokens();
        if (speechTokensJson == null || speechTokensJson.contains("\"error\"")) return;

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> tokens = objectMapper.readValue(speechTokensJson, Map.class);
            String url = baseUrl.replaceAll("/$", "") + UPLOAD_TOKEN_PATH;

            Map<String, Object> body = new HashMap<>();
            body.put("userId", userId);
            body.put("voiceId", voice.getId());
            body.put("tokens", tokens);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

            ResponseEntity<String> response = restTemplate.postForEntity(url, request, String.class);
            if (response.getStatusCode().is2xxSuccessful()) {
                // 성공 시 로그는 선택 (디버깅 시 유용)
            }
        } catch (Exception e) {
            // Jetson 미가동/미구현 시 예상되는 실패 → 로그만, 호출자에는 영향 없음
            System.err.println("[VoiceJetsonSync] userId=" + userId + " Jetson 전송 실패 (무시): " + e.getMessage());
        }
    }
}
