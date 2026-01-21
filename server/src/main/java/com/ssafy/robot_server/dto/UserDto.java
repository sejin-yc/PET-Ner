package com.ssafy.robot_server.dto;

import com.ssafy.robot_server.domain.User;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class UserDto {
    
    private Long id;        // 유저 고유 번호 (응답용)
    private String email;   // 이메일
    private String password;// 비밀번호 (요청받을 때만 사용)
    private String name;    // 이름

    /**
     * User 엔티티(DB 데이터)를 UserDto(응답 데이터)로 변환하는 메서드
     * UserService.java에서 사용합니다.
     */
    public static UserDto from(User user) {
        if (user == null) return null;

        return new UserDto(
            user.getId(),
            user.getEmail(),
            null, // 🚨 보안 중요: 회원가입 완료 후 응답에는 비밀번호를 비워서 보냄!
            user.getName()
        );
    }
}