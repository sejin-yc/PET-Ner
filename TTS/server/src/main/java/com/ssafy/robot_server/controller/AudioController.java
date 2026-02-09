package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.AudioPlayback;
import com.ssafy.robot_server.service.AudioPlaybackService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping(value = { "/audio", "/api/audio" })
@RequiredArgsConstructor
@Tag(name = "음성 재생(Pi5)", description = "무전기 업로드, Pi5 재생 상태 업데이트")
public class AudioController {

    private final AudioPlaybackService audioPlaybackService;

    @GetMapping(value = { "", "/list" })
    @Operation(summary = "최근 음성 재생 목록 (DB 저장 확인용)")
    public ResponseEntity<?> list() {
        try {
            return ResponseEntity.ok(audioPlaybackService.getRecentList());
        } catch (Exception e) {
            log.error("[audio] list failed", e);
            Map<String, Object> err = new HashMap<>();
            err.put("success", false);
            err.put("message", "목록 조회 실패: " + e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(err);
        }
    }

    @PostMapping("/walkie")
    @Operation(summary = "무전기 녹음 업로드")
    public ResponseEntity<?> uploadWalkie(
            @RequestParam("userId") Long userId,
            @RequestParam("audio") MultipartFile audio) {
        log.info("[audio] POST /walkie userId={} size={}", userId, audio.getSize());
        if (audio.isEmpty()) {
            Map<String, Object> err = new HashMap<>();
            err.put("success", false);
            err.put("message", "음성 파일이 없습니다.");
            return ResponseEntity.badRequest().body(err);
        }
        try {
            AudioPlayback playback = audioPlaybackService.saveWalkie(userId, audio);
            Map<String, Object> res = new HashMap<>();
            res.put("success", true);
            res.put("id", playback.getId());
            res.put("audioUrl", playback.getAudioUrl());
            res.put("message", "무전기 음성이 저장되었고 Pi5로 재생 요청이 전송되었습니다.");
            return ResponseEntity.ok(res);
        } catch (Exception e) {
            e.printStackTrace();
            String detail = e.getMessage();
            if (e.getCause() != null && e.getCause().getMessage() != null) {
                detail = detail + " (원인: " + e.getCause().getMessage() + ")";
            }
            Map<String, Object> err = new HashMap<>();
            err.put("success", false);
            err.put("message", "무전기 저장 실패: " + detail);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(err);
        }
    }

    @PatchMapping("/{id}/status")
    @Operation(summary = "Pi5 재생 상태 업데이트")
    public ResponseEntity<?> updateStatus(
            @PathVariable Long id,
            @RequestBody Map<String, String> body) {
        String status = body != null ? body.get("status") : null;
        String errorMessage = body != null ? body.get("errorMessage") : null;
        if (status == null || status.isBlank()) {
            Map<String, Object> err = new HashMap<>();
            err.put("success", false);
            err.put("message", "status 필수 (PLAYING, PLAYED, FAILED)");
            return ResponseEntity.badRequest().body(err);
        }
        return audioPlaybackService.updateStatus(id, status.trim(), errorMessage)
                .map(playback -> {
                    Map<String, Object> res = new HashMap<>();
                    res.put("success", true);
                    res.put("id", playback.getId());
                    res.put("status", playback.getStatus());
                    return ResponseEntity.ok(res);
                })
                .orElse(ResponseEntity.notFound().build());
    }
}
