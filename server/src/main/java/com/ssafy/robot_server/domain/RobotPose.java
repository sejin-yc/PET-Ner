package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import java.time.LocalDateTime; // ✅ java.sql.Timestamp 대신 사용

@Entity
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@Table(name = "robot_pose")
public class RobotPose {

    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // ✅ 다른 엔티티(Log, Cat)와 통일성을 위해 추가
    // (어떤 유저의 로봇인지 구별용)
    private Long userId;

    private double x; // 가로 위치
    
    private double y; // 세로 위치

    // ✅ 로봇이 바라보는 방향 (라디안 또는 도)
    // 이게 없으면 지도에서 로봇을 그냥 '점'으로만 표현해야 합니다.
    // 화살표로 표현하려면 이 필드가 필수입니다.
    private double theta; 

    @CreationTimestamp
    private LocalDateTime timestamp; // ✅ 최신 Java 표준 타입으로 변경
}