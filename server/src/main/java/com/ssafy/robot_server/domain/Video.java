package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.Data;
import org.hibernate.annotations.CreationTimestamp;
import java.time.LocalDateTime;

@Entity
@Data
@Table(name = "videos")
public class Video {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long userId;        // 유저 ID (숫자)
    private String catName;     // 고양이 이름
    private String behavior;    // 행동 (예: 밥 먹음)
    private String duration;    // 영상 길이

    @Column(length = 1000)
    private String url;
    
    @Column(length = 1000)
    private String thumbnailUrl; // 썸네일 주소

    @CreationTimestamp
    @Column(updatable = false)
    private LocalDateTime createdAt;
}