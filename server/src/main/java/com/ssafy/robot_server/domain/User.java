package com.ssafy.robot_server.domain;

import java.util.ArrayList;
import java.util.List;

import jakarta.persistence.*;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Data
@Table(name = "users")
@NoArgsConstructor
@AllArgsConstructor
@Builder
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
    private String password;

    @ElementCollection(fetch = FetchType.EAGER)
    @Builder.Default // 빌더 패턴 사용 시 기본값 적용
    private List<String> roles = new ArrayList<>();
}