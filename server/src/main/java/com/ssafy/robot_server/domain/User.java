package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor; // ✅ 추가
import lombok.Builder;            // ✅ 추가
import lombok.Data;
import lombok.NoArgsConstructor;  // ✅ 필수 (JPA용 기본 생성자)

@Entity
@Data
@Table(name = "users")
@NoArgsConstructor  // ✅ JPA 필수
@AllArgsConstructor // ✅ Builder용
@Builder            // ✅ 객체 생성 편의성
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    @NotBlank(message = "이름은 필수 입력 값입니다.")
    private String name;

    @Column(nullable = false, unique = true)
    @NotBlank(message = "이메일은 필수 입력 값입니다.")
    @Email(message = "이메일 형식이 올바르지 않습니다.")
    private String email;

    @Column(nullable = false, length = 100)
    @NotBlank(message = "비밀번호는 필수 입력 값입니다.")
    // 🚨 주의: DB에는 암호화된(긴) 비밀번호가 저장되므로, 
    // @Size 검사는 보통 회원가입 요청 DTO에서 하는 게 더 정확하지만, 
    // 엔티티에 두어도 @PrePersist 등으로 막지 않는 한 큰 문제는 없습니다.
    private String password;

    // ✅ (선택 사항) 권한 구분용 필드
    // 나중에 관리자 페이지를 만들거나 할 때 유용합니다.
    @Builder.Default // 빌더 패턴 사용 시 기본값 적용
    private String role = "ROLE_USER"; 
}