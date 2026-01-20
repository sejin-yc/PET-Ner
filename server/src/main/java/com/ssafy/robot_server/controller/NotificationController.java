package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.Notification;
import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.repository.NotificationRepository;
import com.ssafy.robot_server.repository.UserRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional; // ✅ 트랜잭션 필수
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/api/notifications")
@RequiredArgsConstructor // ✅ 생성자 주입
@Tag(name = "4. 알림 관리", description = "알림 조회/생성/읽음처리 API")
public class NotificationController {

    private final NotificationRepository notificationRepository;
    private final UserRepository userRepository;

    // 1. 목록 조회
    @GetMapping
    @Operation(summary = "알림 목록 조회")
    public ResponseEntity<?> getNotifications(@RequestParam Long userId) {
        User user = userRepository.findById(userId).orElse(null);
        if (user == null) return ResponseEntity.badRequest().body("존재하지 않는 유저입니다.");
        
        return ResponseEntity.ok(notificationRepository.findByUserOrderByTimestampDesc(user));
    }

    // ✅ [중요] Map 대신 DTO 클래스 사용 (안전성 확보)
    @Data
    public static class NotificationRequest {
        private Long userId;
        private String type;
        private String title;
        private String message;
        private String priority;
    }

    // 2. 알림 생성
    @PostMapping
    @Operation(summary = "알림 생성 (로봇 -> 서버)")
    public ResponseEntity<?> createNotification(@RequestBody NotificationRequest request) {
        // 유효성 검사
        if (request.getUserId() == null) return ResponseEntity.badRequest().body("userId는 필수입니다.");

        User user = userRepository.findById(request.getUserId()).orElse(null);
        if (user == null) return ResponseEntity.badRequest().body("존재하지 않는 유저입니다.");

        Notification noti = new Notification();
        noti.setType(request.getType());
        noti.setTitle(request.getTitle());
        noti.setMessage(request.getMessage());
        noti.setPriority(request.getPriority() != null ? request.getPriority() : "INFO"); // 기본값 설정
        noti.setRead(false);
        noti.setUser(user);
        
        // 시간 설정 (Entity에 @CreationTimestamp가 없으면 여기서 필수)
        noti.setTimestamp(LocalDateTime.now());

        notificationRepository.save(noti);
        return ResponseEntity.ok("알림이 저장되었습니다.");
    }

    // 3. 읽음 처리
    @PutMapping("/{id}/read")
    @Operation(summary = "단일 알림 읽음 처리")
    public ResponseEntity<?> markAsRead(@PathVariable Long id) {
        Notification noti = notificationRepository.findById(id).orElse(null);
        if (noti != null) {
            noti.setRead(true);
            notificationRepository.save(noti);
            return ResponseEntity.ok("읽음 처리 완료");
        }
        return ResponseEntity.badRequest().body("알림을 찾을 수 없습니다.");
    }

    // 4. 모두 읽음 처리
    @PutMapping("/read-all")
    @Operation(summary = "모든 알림 읽음 처리")
    @Transactional // ✅ 여러 개를 수정하므로 트랜잭션 추천
    public ResponseEntity<?> markAllAsRead(@RequestParam Long userId) {
        User user = userRepository.findById(userId).orElse(null);
        if (user == null) return ResponseEntity.badRequest().body("유저 없음");
        
        // 벌크 업데이트 쿼리를 만드는 게 성능상 더 좋지만, 지금은 루프도 괜찮습니다.
        List<Notification> list = notificationRepository.findByUserOrderByTimestampDesc(user);
        for (Notification n : list) {
            n.setRead(true);
        }
        notificationRepository.saveAll(list);
        return ResponseEntity.ok("모두 읽음 처리 완료");
    }

    // 5. 삭제 (단건)
    @DeleteMapping("/{id}")
    @Operation(summary = "알림 삭제")
    public ResponseEntity<?> deleteNotification(@PathVariable Long id) {
        if (notificationRepository.existsById(id)) {
            notificationRepository.deleteById(id);
            return ResponseEntity.ok("삭제 완료");
        }
        return ResponseEntity.badRequest().body("삭제할 알림이 없습니다.");
    }

    // 6. 전체 삭제
    @DeleteMapping("/all")
    @Operation(summary = "알림 전체 삭제")
    @Transactional // 🚨 [매우 중요] deleteByUser 같은 커스텀 삭제는 트랜잭션 필수!
    public ResponseEntity<?> deleteAllNotifications(@RequestParam Long userId) {
        User user = userRepository.findById(userId).orElse(null);
        if (user == null) return ResponseEntity.badRequest().body("유저 없음");
        
        notificationRepository.deleteByUser(user);
        return ResponseEntity.ok("전체 삭제 완료");
    }
}