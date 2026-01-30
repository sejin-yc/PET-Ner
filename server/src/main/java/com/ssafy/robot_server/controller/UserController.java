package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.repository.UserRepository;
import com.ssafy.robot_server.security.JwtTokenProvider;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("users")
@RequiredArgsConstructor
@Tag(name = "1. 유저 관리", description = "회원가입/로그인 API")
public class UserController {

    private final UserRepository userRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final PasswordEncoder passwordEncoder;

    @Data
    public static class LoginRequest{
        private String email;
        private String password;
    }

    @Data
    public static class UpdateProfileRequest{
        private String name;
    }

    @Data
    public static class PasswordRequest {
        private Long userId;
        private String password;    // 현재 비번
        private String newPassword; // 새 비번
    }

    // 1. 회원가입
    @PostMapping("/register")
    @Operation(summary = "회원가입")
    public ResponseEntity<?> registerUser(@RequestBody User user) {
        if (userRepository.findByEmail(user.getEmail()).isPresent()) {
            return ResponseEntity.badRequest().body("이미 존재하는 이메일입니다.");
        }
        
        // 비밀번호 암호화 후 저장
        user.setPassword(passwordEncoder.encode(user.getPassword()));

        if (user.getRoles() == null || user.getRoles().isEmpty()) {
            user.setRoles(Collections.singletonList("ROLE_USER"));
        }
        
        User savedUser = userRepository.save(user);
        return ResponseEntity.ok(savedUser);
    }

    // 2. 로그인
    @PostMapping("/login")
    @Operation(summary = "로그인")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail()).orElse(null);

        // ✅ 암호화된 비밀번호 비교
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            return ResponseEntity.status(401).body("이메일 또는 비밀번호가 잘못되었습니다.");
        }

        String token = jwtTokenProvider.createToken(user.getEmail());

        Map<String, Object> response = new HashMap<>();
        response.put("token", token);
        response.put("user", user);

        return ResponseEntity.ok(response);
    }

    // 3. 프로필 이름 수정
    @PutMapping("/{id}/profile")
    @Operation(summary = "프로필 수정")
    public ResponseEntity<?> updateProfile(@PathVariable Long id, @RequestBody UpdateProfileRequest request) {
        User user = userRepository.findById(id).orElse(null);
        if (user == null) return ResponseEntity.badRequest().body("유저를 찾을 수 없습니다.");

        user.setName(request.getName());
        userRepository.save(user);
        return ResponseEntity.ok(user);
    }

    // 4. 비밀번호 확인 (설정 페이지 진입용)
    @PostMapping("/verify-password")
    @Operation(summary = "비밀번호 확인")
    public ResponseEntity<?> verifyPassword(@RequestBody PasswordRequest request) {
        User user = userRepository.findById(request.getUserId()).orElse(null);
        
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            return ResponseEntity.status(401).body("비밀번호가 일치하지 않습니다.");
        }
        return ResponseEntity.ok("비밀번호 확인 완료");
    }

    // 5. 비밀번호 변경
    @PutMapping("/{id}/password")
    @Operation(summary = "비밀번호 변경")
    public ResponseEntity<?> updatePassword(@PathVariable Long id, @RequestBody PasswordRequest request) {
        User user = userRepository.findById(id).orElse(null);
        if (user == null) return ResponseEntity.badRequest().body("유저를 찾을 수 없습니다.");

        if (request.getNewPassword() == null || request.getNewPassword().isEmpty()){
            return ResponseEntity.badRequest().body("새 비밀번호를 입력해주세요.");
        }

        // ✅ 새 비밀번호도 암호화해서 저장
        user.setPassword(passwordEncoder.encode(request.getNewPassword()));
        userRepository.save(user);
        return ResponseEntity.ok("비밀번호가 변경되었습니다.");
    }

    // 6. 회원 탈퇴
    @DeleteMapping("/{id}")
    @Operation(summary = "회원 탈퇴")
    public ResponseEntity<?> deleteUser(@PathVariable Long id) {
        if (userRepository.existsById(id)) {
            userRepository.deleteById(id);
            return ResponseEntity.ok("회원 탈퇴가 완료되었습니다.");
        }
        return ResponseEntity.badRequest().body("존재하지 않는 유저입니다.");
    }
}