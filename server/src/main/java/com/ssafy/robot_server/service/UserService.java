package com.ssafy.robot_server.service;

import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.dto.UserDto;
import com.ssafy.robot_server.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.authority.SimpleGrantedAuthority; // ✅ 권한 부여용 추가
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collections; // ✅ 추가

@Service
@RequiredArgsConstructor
public class UserService implements UserDetailsService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    /**
     * 회원가입 기능
     */
    @Transactional // 수정이 일어나므로 트랜잭션 보장
    public UserDto register(UserDto userDto) {
        if (userRepository.existsByEmail(userDto.getEmail())) {
            throw new RuntimeException("이미 존재하는 이메일입니다.");
        }

        // ✅ [수정] 빌더 패턴을 사용하여 엔티티 생성 (더 깔끔합니다)
        User user = User.builder()
                .name(userDto.getName())
                .email(userDto.getEmail())
                .password(passwordEncoder.encode(userDto.getPassword())) // 암호화 굿!
                .role("ROLE_USER") // 기본 권한 설정
                .build();

        User savedUser = userRepository.save(user);
        return UserDto.from(savedUser);
    }

    /**
     * 시큐리티 로그인 처리
     */
    @Override
    @Transactional(readOnly = true) // 읽기 전용으로 성능 최적화
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException("사용자를 찾을 수 없습니다: " + email));

        // ✅ [수정] 빈 리스트 대신 기본 권한인 ROLE_USER를 넣어줍니다.
        return new org.springframework.security.core.userdetails.User(
                user.getEmail(),
                user.getPassword(),
                Collections.singletonList(new SimpleGrantedAuthority(user.getRole()))
        );
    }
}