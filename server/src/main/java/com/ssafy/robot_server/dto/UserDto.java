package com.ssafy.robot_server.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.ssafy.robot_server.domain.User;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class UserDto {
    
    private Long id;        // 유저 고유 번호 (응답용)
    private String email;   // 이메일
    private String password;// 비밀번호 (요청받을 때만 사용)
    private String name;    // 이름
    private List<String> roles;
    private boolean isVoiceTrained;
    private Integer age;
    private String gender;

    public static UserDto from(User user) {
        if (user == null) return null;

        return new UserDto(
            user.getId(),
            user.getEmail(),
            null, // 🚨 보안 중요: 회원가입 완료 후 응답에는 비밀번호를 비워서 보냄!
            user.getName(),
            user.getRoles(),
            user.isVoiceTrained(),
            user.getAge(),
            user.getGender()
        );
    }
}