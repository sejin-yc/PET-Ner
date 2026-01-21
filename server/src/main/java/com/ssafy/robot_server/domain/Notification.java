package com.ssafy.robot_server.domain;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import lombok.AllArgsConstructor; // ✅ 추가
import lombok.Builder;            // ✅ 추가
import lombok.Data;
import lombok.NoArgsConstructor;  // ✅ 필수 (JPA용 기본 생성자)
import java.time.LocalDateTime;

@Entity
@Data
@Table(name = "notifications")
@NoArgsConstructor  // ✅ 필수
@AllArgsConstructor // ✅ 추가
@Builder            // ✅ 빌더 패턴 사용
public class Notification {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String type;     // robot_status, robot_error, cat_alert, system
    private String title;
    private String message;
    private String priority; // high, medium, low
    
    // ✅ 팁: Lombok에서 boolean 필드는 'isRead'라고 쓰면 
    // JSON 변환 시 getter 이름 문제로 'read'로 바뀔 수 있습니다.
    // 프론트에서 noti.read 로 안 나오면 noti.isRead로 확인해보세요.
    private boolean isRead;

    private LocalDateTime timestamp;

    // ✅ Log/Cat과 달리 여기선 User 객체를 직접 연결했습니다. (Foreign Key 제약조건 생성됨)
    // 데이터 무결성 측면에서는 이게 더 정석적인 방법입니다. 아주 좋습니다!
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    @JsonIgnore // User 정보를 JSON으로 보낼 때 무한루프 방지
    private User user;

    @PrePersist
    public void onCreate() {
        if (this.timestamp == null) this.timestamp = LocalDateTime.now();
    }
}