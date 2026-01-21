package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor; // ✅ 추가
import lombok.Builder;            // ✅ 추가
import lombok.Data;
import lombok.NoArgsConstructor;  // ✅ 필수 (JPA 에러 방지)
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

@Entity
@Data
@Table(name = "logs")
@NoArgsConstructor  // ✅ JPA 필수: 기본 생성자
@AllArgsConstructor // ✅ 전체 생성자
@Builder            // ✅ 빌더 패턴 사용 가능
public class Log {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // ✅ User 객체 대신 userId(Long) 사용: 아주 좋은 선택입니다!
    // 로그는 데이터가 많아서 User 객체랑 일일이 연관관계(Join)를 맺으면 성능이 느려질 수 있는데,
    // 이렇게 ID만 저장하면 아주 가볍고 빠릅니다.
    private Long userId;

    private String mode;        // auto, manual
    private String status;      // completed, in-progress
    private String duration;    // "10분 30초" (화면 표시용)
    private int durationNum;    // 630 (초 단위, 그래프 계산용) - ✅ 아주 센스 있습니다!
    private double distance;
    private int detectionCount;
    private String details;

    @CreationTimestamp
    @Column(updatable = false)
    private LocalDateTime createdAt;
}