package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Data
@Table(name = "logs")
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Log {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private Long userId;

    private Long rentId;
    private Long vehicleId;

    private String mode;        // auto, manual
    private String status;      // completed, in-progress
    private String duration;    // "10분 30초" (화면 표시용)

    private int durationNum;    // 630 (초 단위, 그래프 계산용)

    private double distance;
    private int detectionCount;

    @Column(columnDefinition = "TEXT")
    private String details;

    private String createdAt;
}