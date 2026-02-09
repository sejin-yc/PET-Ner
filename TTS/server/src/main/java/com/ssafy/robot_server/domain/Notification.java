package com.ssafy.robot_server.domain;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Data
@Table(name = "notifications")
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Notification {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String type;     // robot_status, robot_error, cat_alert, system
    private String title;
    private String message;
    private String priority; // high, medium, low

    @JsonProperty("isRead")
    private boolean isRead;

    private LocalDateTime timestamp;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    @JsonIgnore // User 정보를 JSON으로 보낼 때 무한루프 방지
    private User user;

    @PrePersist
    public void onCreate() {
        if (this.timestamp == null) this.timestamp = LocalDateTime.now();
    }
}