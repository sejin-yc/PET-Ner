package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.Video;
import com.ssafy.robot_server.repository.VideoRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;

@RestController
@RequestMapping({"/video", "/videos", "/api/video", "/api/videos"})
@RequiredArgsConstructor
@Tag(name = "5. 영상 관리", description = "특이행동/사건사고 영상 API")
public class VideoController {

    private final VideoRepository videoRepository;

    // 1. 목록 조회
    @GetMapping
    @Operation(summary = "영상 목록 조회", description = "최신순으로 정렬하여 반환합니다.")
    public ResponseEntity<List<Video>> getVideos(@RequestParam Long userId) {
        return ResponseEntity.ok(videoRepository.findByUserIdOrderByCreatedAtDesc(userId));
    }

    // 2. 영상 생성
    @PostMapping
    @Operation(summary = "영상 정보 저장")
    public ResponseEntity<?> createVideo(@RequestBody Video video) {
        // 필수 정보 체크
        if (video.getUserId() == null) {
            return ResponseEntity.badRequest().body("userId는 필수입니다.");
        }
        if (video.getUrl() == null || video.getUrl().isEmpty()) {
            return ResponseEntity.badRequest().body("영상 URL은 필수입니다.");
        }

        video.setId(null);

        // 생성 시간 자동 설정 (없을 경우)
        if (video.getCreatedAt() == null) {
            String now = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
            video.setCreatedAt(now);
        }

        return ResponseEntity.ok(videoRepository.save(video));
    }

    // 3. 삭제
    @DeleteMapping("/{id}")
    @Operation(summary = "영상 삭제")
    public ResponseEntity<?> deleteVideo(@PathVariable Long id) {
        if (videoRepository.existsById(id)) {
            videoRepository.deleteById(id);
            return ResponseEntity.ok("영상이 삭제되었습니다.");
        } else {
            return ResponseEntity.status(404).body("해당 ID의 영상을 찾을 수 없습니다.");
        }
    }
}