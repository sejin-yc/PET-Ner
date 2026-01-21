package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.Log;
import com.ssafy.robot_server.repository.LogRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor; // ✅ Lombok 추가
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/api/logs")
@RequiredArgsConstructor // ✅ 생성자 주입 (Autowired 대체)
@Tag(name = "2. 로그 관리", description = "로봇 순찰 로그 API")
public class LogController {

    private final LogRepository logRepository; // ✅ final 선언 (불변성 보장)

    // 1. 목록 조회
    @GetMapping
    @Operation(summary = "로그 목록 조회", description = "특정 유저의 로그를 최신순으로 조회합니다.")
    public ResponseEntity<List<Log>> getLogs(@RequestParam Long userId) {
        // Repository에 findByUserIdOrderByCreatedAtDesc 메소드가 있어야 합니다.
        // 만약 없다면 Repository 인터페이스에 추가해 주세요!
        return ResponseEntity.ok(logRepository.findByUserIdOrderByCreatedAtDesc(userId));
    }

    // 2. 생성 (로봇이 자동으로 남길 수도 있고, 수동으로 남길 수도 있음)
    @PostMapping
    @Operation(summary = "로그 생성")
    public ResponseEntity<?> createLog(@RequestBody Log log) {
        // 유효성 검사
        if (log.getUserId() == null) {
            return ResponseEntity.badRequest().body("userId는 필수입니다.");
        }

        log.setId(null);

        // 시간 자동 설정 (Entity에 @CreationTimestamp가 없다면 여기서 설정)
        if (log.getCreatedAt() == null) {
            log.setCreatedAt(LocalDateTime.now());
        }

        return ResponseEntity.ok(logRepository.save(log));
    }

    // 3. 삭제
    @DeleteMapping("/{id}")
    @Operation(summary = "로그 삭제")
    public ResponseEntity<?> deleteLog(@PathVariable Long id) {
        if (logRepository.existsById(id)) {
            logRepository.deleteById(id);
            return ResponseEntity.ok("로그가 삭제되었습니다.");
        } else {
            return ResponseEntity.status(404).body("해당 ID의 로그를 찾을 수 없습니다.");
        }
    }
}