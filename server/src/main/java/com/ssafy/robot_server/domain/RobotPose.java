package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
@Table(name = "robot_pose")
public class RobotPose {

    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long userId;

    private double x; // 가로 위치
    
    private double y; // 세로 위치

    private double theta; 

    @CreationTimestamp
    private LocalDateTime timestamp; // ✅ 최신 Java 표준 타입으로 변경
}