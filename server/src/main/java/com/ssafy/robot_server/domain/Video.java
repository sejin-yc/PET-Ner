package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Data
@Table(name = "videos")
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Video {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long userId;        // 유저 ID (숫자)

    private Long rentId;
    private Long vehicleId;

    private String catName;     // 고양이 이름
    private String behavior;    // 행동 (예: 밥 먹음)
    private String duration;    // 영상 길이 (예: "00:15")

    @Column(length = 1000)
    private String url;
    
    @Column(length = 1000)
    private String thumbnailUrl; // 썸네일 주소

    @Column(updatable = false)
    private String createdAt;
}