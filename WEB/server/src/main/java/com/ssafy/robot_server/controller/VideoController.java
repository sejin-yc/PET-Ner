package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.Video;
import com.ssafy.robot_server.repository.VideoRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping({"/video", "/videos"})
@RequiredArgsConstructor
@Tag(name = "5. 영상 관리", description = "특이행동/사건사고 영상 API")
public class VideoController {

    private final VideoRepository videoRepository;

    @Value("${app.uploads.video:/app/uploads/video}")
    private String uploadDir;

    // 1. 목록 조회
    @GetMapping
    @Operation(summary = "영상 목록 조회")
    public ResponseEntity<List<Video>> getVideos(@RequestParam Long userId) {
        return ResponseEntity.ok(videoRepository.findByUserIdOrderByCreatedAtDesc(userId));
    }

    // 2. 영상 업로드
    @PostMapping("/upload")
    @Operation(summary = "영상 파일 업로드 (MP4)")
    public ResponseEntity<?> uploadVideo(
            @RequestParam("file") MultipartFile file,
            @RequestParam("userId") Long userId,
            @RequestParam(value = "behavior", defaultValue = "unknown") String behavior
    ) {
        if (file.isEmpty()) {
            return ResponseEntity.badRequest().body("파일이 비어있습니다.");
        }

        try {
            File directory = new File(uploadDir);
            if (!directory.exists()) {
                directory.mkdirs();
            }

            // 파일명 생성 (UUID + 원본명)
            String originalFilename = file.getOriginalFilename();
            String savedFilename = UUID.randomUUID() + "_" + originalFilename;
            String filePath = uploadDir + File.separator + savedFilename;

            // 디스크 저장
            file.transferTo(new File(filePath));
            log.info("🎥 영상 저장 완료: {}", filePath);

            // DB 접근 URL (Nginx 경로와 일치해야 함)
            String accessUrl = "/uploads/video/" + savedFilename;

            // DB 엔티티 생성
            Video video = new Video();
            video.setUserId(userId);
            video.setUrl(accessUrl);
            video.setBehavior(behavior);
            
            // ⚡ [수정 1] 실제 저장된 파일명(UUID 포함)을 저장해야 나중에 삭제 가능
            video.setFileName(savedFilename); 
            
            video.setCreatedAt(LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));

            Video savedVideo = videoRepository.save(video);
            
            return ResponseEntity.ok(savedVideo);

        } catch (IOException e) {
            log.error("파일 업로드 실패", e);
            return ResponseEntity.internalServerError().body("오류 발생: " + e.getMessage());
        }
    }

    // 3. 영상 삭제 (파일 삭제 기능 추가)
    @DeleteMapping("/{id}")
    @Operation(summary = "영상 삭제 (DB + 실제 파일)")
    public ResponseEntity<?> deleteVideo(@PathVariable Long id) {
        // 1. DB에서 영상 정보 찾기
        Video video = videoRepository.findById(id).orElse(null);
        if (video == null) {
            return ResponseEntity.status(404).body("해당 영상을 찾을 수 없습니다.");
        }

        // ⚡ [수정 2] 실제 파일 삭제 로직 추가
        try {
            // DB에 저장된 파일명으로 실제 파일 경로 구성
            String fullPath = uploadDir + File.separator + video.getFileName();
            File file = new File(fullPath);

            if (file.exists()) {
                if (file.delete()) {
                    log.info("🗑️ 실제 파일 삭제 성공: {}", fullPath);
                } else {
                    log.warn("⚠️ 실제 파일 삭제 실패: {}", fullPath);
                }
            } else {
                log.warn("⚠️ 파일이 존재하지 않습니다 (이미 삭제됨?): {}", fullPath);
            }
        } catch (Exception e) {
            log.error("파일 삭제 중 에러 발생", e);
            // 파일 삭제 에러가 나도 DB 데이터는 지울지 결정해야 함 (여기선 진행)
        }

        // 2. DB 데이터 삭제
        videoRepository.deleteById(id);
        return ResponseEntity.ok("영상과 데이터가 삭제되었습니다.");
    }
}