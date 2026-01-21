package com.ssafy.robot_server.service;

import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.dto.UserDto;
import com.ssafy.robot_server.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;

@Service
@RequiredArgsConstructor
@Transactional
public class UserService implements UserDetailsService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder; // ✅ 암호화 기계 주입

    /**
     * 회원가입 기능 (비밀번호 암호화 필수!)
     */
    public UserDto register(UserDto userDto) {
        // 1. 이메일 중복 검사
        if (userRepository.existsByEmail(userDto.getEmail())) {
            throw new RuntimeException("이미 존재하는 이메일입니다.");
        }

        // 2. User 엔티티 생성
        User user = new User();
        user.setName(userDto.getName());
        user.setEmail(userDto.getEmail());

        // ✅ [핵심] 비밀번호를 그냥 넣지 않고, '암호화'해서 넣는다!
        // 입력: "1234" -> 저장: "$2a$10$rD..." (알 수 없는 문자열)
        String encodedPassword = passwordEncoder.encode(userDto.getPassword());
        user.setPassword(encodedPassword);

        // 3. DB 저장
        User savedUser = userRepository.save(user);

        // 4. 결과 반환
        return UserDto.from(savedUser);
    }

    /**
     * 로그인 기능 (Spring Security가 자동으로 호출함)
     * 이 메서드가 있어야 DB에서 유저를 찾아 로그인 검사를 할 수 있음.
     */
    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException("사용자를 찾을 수 없습니다: " + email));

        // Spring Security가 이해할 수 있는 User 객체로 변환해서 반환
        return new org.springframework.security.core.userdetails.User(
                user.getEmail(),
                user.getPassword(), // 암호화된 비밀번호
                new ArrayList<>()   // 권한 목록 (일단 비움)
        );
    }
}