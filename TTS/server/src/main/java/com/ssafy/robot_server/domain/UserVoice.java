package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Data
@Table(name = "user_voices")
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserVoice {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long userId;

    @Column(length = 500)
    private String promptText; // 녹음한 문구

    @Column(length = 1000)
    private String audioUrl; // 오디오 파일 경로

    // 음성 토큰 데이터 (JSON 형태로 저장)
    @Column(columnDefinition = "TEXT")
    private String speechTokens; // JSON 형태의 토큰 데이터

    @Column(columnDefinition = "TEXT")
    private String embeddings; // JSON 형태의 임베딩 데이터

    @Builder.Default
    private LocalDateTime createdAt = LocalDateTime.now();

    @Builder.Default
    private Boolean isActive = true; // 활성화 여부
}
