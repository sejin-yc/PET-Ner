package com.ssafy.robot_server.domain;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.persistence.*;
import lombok.AllArgsConstructor; // ✅ 추가
import lombok.Builder;            // ✅ 추가
import lombok.Data;
import lombok.NoArgsConstructor;  // ✅ 필수 (JPA 에러 방지)
import org.hibernate.annotations.CreationTimestamp;
import java.time.LocalDateTime;

@Entity
@Data
@Table(name = "videos")
@NoArgsConstructor  // ✅ JPA 필수: 기본 생성자
@AllArgsConstructor // ✅ Builder 사용 시 필수
@Builder            // ✅ 객체 생성 편의성
public class Video {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long userId;        // 유저 ID (숫자)
    private String catName;     // 고양이 이름
    private String behavior;    // 행동 (예: 밥 먹음)
    private String duration;    // 영상 길이 (예: "00:15")

    @Column(length = 1000)      // ✅ URL이 길어질 수 있으므로 아주 좋은 설정입니다!
    private String url;
    
    @Column(length = 1000)
    private String thumbnailUrl; // 썸네일 주소

    @CreationTimestamp
    @Column(updatable = false)
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd HH:mm:ss", timezone = "Asia/Seoul")
    private String createdAt;
}