package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Data  // @Getter, @Setter, @ToString 등을 자동으로 생성해줌
@Table(name = "videos")
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Video {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long userId;

    private Long rentId;
    private Long vehicleId;

    private String catName;
    private String behavior;
    private String duration;

    @Column(length = 1000)
    private String url;       // 웹에서 접근하는 주소 (예: /uploads/video/uuid_file.mp4)
    
    @Column(length = 1000)
    private String thumbnailUrl;

    // ⚡ [수정 1] 실제 파일명을 저장할 필드 추가
    // 이 필드가 있어야 컨트롤러에서 video.setFileName()을 쓸 수 있습니다.
    @Column(name = "file_name")
    private String fileName;  // 디스크에 저장된 실제 파일명 (예: uuid_file.mp4)

    @Column(updatable = false)
    private String createdAt;

    // ⚡ [수정 2] 아래 메서드는 삭제하세요!
    // public void setFileName(String originalFilename) { ... }
    // -> 이 메서드가 있으면 Lombok이 setFileName을 안 만들고, 이걸 실행해서 에러가 납니다.
    // -> 필드(private String fileName)만 추가하면 @Data가 알아서 만들어줍니다.
}