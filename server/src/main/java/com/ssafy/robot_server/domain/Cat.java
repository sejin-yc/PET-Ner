package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor; // ✅ 추가
import lombok.Builder;            // ✅ 추가 (객체 생성 시 아주 편함)
import lombok.Data;
import lombok.NoArgsConstructor;  // ✅ 필수 (JPA는 빈 생성자가 없으면 에러남!)

import java.time.LocalDateTime;

@Entity
@Data
@Table(name = "cats")
@NoArgsConstructor  // ✅ JPA 필수 설탕
@AllArgsConstructor // ✅ 전체 생성자
@Builder            // ✅ 빌더 패턴 (Cat.builder().name("냥이").build() 가능)
public class Cat {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // ✅ 객체(User) 대신 숫자(userId)로 저장 (Log와 통일) -> 아주 좋은 선택입니다!
    private Long userId;

    @Column(nullable = false)
    private String name;

    private String breed;
    private int age;
    private double weight;
    private String notes;

    // 기본값 설정 (Builder를 쓸 때도 기본값이 적용되려면 @Builder.Default가 필요하지만, 
    // 지금처럼 필드 초기화를 해두면 new Cat() 할 때는 적용됩니다.)
    private String healthStatus = "normal"; 
    private String behaviorStatus = "대기 중"; 
    
    private LocalDateTime lastDetected;
}