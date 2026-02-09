package com.ssafy.robot_server.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.domain.AudioPlayback;
import com.ssafy.robot_server.repository.AudioPlaybackRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class AudioPlaybackService {

    private final AudioPlaybackRepository audioPlaybackRepository;
    private final MqttService mqttService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${audio.upload-dir:/app/uploads/audio}")
    private String uploadDir;

    @Value("${audio.base-url:http://localhost:8080/api}")
    private String baseUrl;

    @Value("${audio.mqtt-topic-play:pi5/audio/play}")
    private String mqttTopicPlay;

    @Value("${cosyvoice.service.url:http://cosyvoice_service:50001}")
    private String cosyvoiceServiceUrl;

    private static final DateTimeFormatter FILE_TIME = DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSS");

    /**
     * TTS 결과 WAV 저장 → DB 큐 적재(CREATED) → 대기 중이면 맨 앞 항목만 Pi5에 재생 요청(FIFO)
     */
    public AudioPlayback saveTts(Long userId, boolean useDefaultVoice, String text, byte[] wavBytes) throws IOException {
        String type = useDefaultVoice ? "tts_default" : "tts_cloned";
        String fileName = buildFileName(type, userId);
        Path dir = Paths.get(uploadDir);
        Files.createDirectories(dir);
        Path filePath = dir.resolve(fileName);
        Files.write(filePath, wavBytes);

        String audioUrl = baseUrl + "/uploads/audio/" + fileName;
        AudioPlayback playback = AudioPlayback.builder()
                .userId(userId)
                .type(type)
                .text(text)
                .audioUrl(audioUrl)
                .fileName(fileName)
                .status("CREATED")
                .build();
        playback = audioPlaybackRepository.save(playback);

        trySendNextToPi5();
        return playback;
    }

    /**
     * 무전기 녹음: 업로드 파일을 CosyVoice로 WAV 변환 후 저장 → DB 큐 적재 → 필요 시 다음 재생 요청
     */
    public AudioPlayback saveWalkie(Long userId, MultipartFile audioFile) throws IOException {
        byte[] wavBytes = convertToWavViaCosyVoice(audioFile);
        String type = "walkie";
        String fileName = buildFileName(type, userId);
        Path dir = Paths.get(uploadDir);
        Files.createDirectories(dir);
        Path filePath = dir.resolve(fileName);
        Files.write(filePath, wavBytes);

        String audioUrl = baseUrl + "/uploads/audio/" + fileName;
        AudioPlayback playback = AudioPlayback.builder()
                .userId(userId)
                .type(type)
                .text(null)
                .audioUrl(audioUrl)
                .fileName(fileName)
                .status("CREATED")
                .build();
        playback = audioPlaybackRepository.save(playback);

        trySendNextToPi5();
        return playback;
    }

    private String buildFileName(String type, Long userId) {
        String time = LocalDateTime.now().format(FILE_TIME);
        return type + "_" + userId + "_" + time + ".wav";
    }

    /**
     * 큐(FIFO): 재생 중인 항목이 없으면 대기(CREATED) 중인 것 중 가장 오래된 것을
     * PLAYING으로 바꾸고 MQTT로 Pi5에만 전송. 한 번에 하나만 재생 요청.
     */
    @Transactional
    public void trySendNextToPi5() {
        if (audioPlaybackRepository.existsByStatus("PLAYING")) {
            return;
        }
        Optional<AudioPlayback> next = audioPlaybackRepository.findFirstByStatusOrderByCreatedAtAsc("CREATED");
        if (next.isEmpty()) {
            return;
        }
        AudioPlayback playback = next.get();
        playback.setStatus("PLAYING");
        audioPlaybackRepository.save(playback);

        try {
            Map<String, Object> payload = new HashMap<>();
            payload.put("id", playback.getId());
            payload.put("audioUrl", playback.getAudioUrl());
            payload.put("userId", playback.getUserId());
            payload.put("type", playback.getType());
            String json = objectMapper.writeValueAsString(payload);
            mqttService.sendCommand(mqttTopicPlay, json);
            log.info("[audio] 큐 → MQTT 발행 (FIFO) id={} type={}", playback.getId(), playback.getType());
        } catch (Exception e) {
            log.warn("[audio] MQTT publish failed: {}", e.getMessage());
            playback.setStatus("CREATED");
            playback.setErrorMessage("MQTT 발행 실패: " + e.getMessage());
            audioPlaybackRepository.save(playback);
        }
    }

    /** 무전기·목소리 학습 공통: 업로드 파일을 CosyVoice /convert_to_wav로 WAV 변환 */
    public byte[] convertUploadToWav(MultipartFile audioFile) throws IOException {
        return convertToWavViaCosyVoice(audioFile);
    }

    private byte[] convertToWavViaCosyVoice(MultipartFile audioFile) throws IOException {
        RestTemplate rt = new RestTemplate();
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("audio_file", new ByteArrayResource(audioFile.getBytes()) {
            @Override
            public String getFilename() {
                return audioFile.getOriginalFilename() != null ? audioFile.getOriginalFilename() : "upload.webm";
            }
        });
        HttpEntity<MultiValueMap<String, Object>> request = new HttpEntity<>(body, headers);
        String url = cosyvoiceServiceUrl + "/convert_to_wav";
        try {
            ResponseEntity<byte[]> response = rt.postForEntity(url, request, byte[].class);
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                return response.getBody();
            }
            throw new IOException("CosyVoice convert_to_wav failed: " + response.getStatusCode());
        } catch (ResourceAccessException e) {
            String hint = "로컬 실행 시 CosyVoice가 localhost:50001에서 떠 있어야 합니다. "
                    + "환경변수 COSYVOICE_SERVICE_URL=http://localhost:50001 로 설정했는지 확인하세요.";
            log.warn("[audio] CosyVoice 연결 실패 url={} error={}", url, e.getMessage());
            throw new IOException("CosyVoice 서비스 연결 실패: " + e.getMessage() + ". " + hint, e);
        }
    }

    /** 최근 재생 목록 (DB 저장 확인용) */
    public List<AudioPlayback> getRecentList() {
        var page = PageRequest.of(0, 50, Sort.by(Sort.Direction.DESC, "createdAt"));
        return audioPlaybackRepository.findAllByOrderByCreatedAtDesc(page);
    }

    public Optional<AudioPlayback> updateStatus(Long id, String status, String errorMessage) {
        Optional<AudioPlayback> updated = audioPlaybackRepository.findById(id).map(playback -> {
            playback.setStatus(status);
            if ("PLAYED".equals(status) || "FAILED".equals(status)) {
                playback.setPlayedAt(LocalDateTime.now());
            }
            if (errorMessage != null) {
                playback.setErrorMessage(errorMessage);
            }
            return audioPlaybackRepository.save(playback);
        });
        if (updated.isPresent() && ("PLAYED".equals(status) || "FAILED".equals(status))) {
            trySendNextToPi5();
        }
        return updated;
    }
}
