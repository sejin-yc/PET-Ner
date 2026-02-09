package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Data
@Table(name = "cats")
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Cat {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // ✅ 객체(User) 대신 숫자(userId)로 저장 (Log와 통일)
    private Long userId;

    @Column(nullable = false)
    private String name;

    private String breed;
    private int age;
    private double weight;
    private String notes;

    @Builder.Default
    private String healthStatus = "normal";

    @Builder.Default
    private String behaviorStatus = "대기 중"; 
    
    private LocalDateTime lastDetected;
}