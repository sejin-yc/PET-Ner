package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.repository.UserRepository;
import com.ssafy.robot_server.security.JwtTokenProvider; // ✅ 여기가 중요! (util 아님)
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.Data;
import lombok.RequiredArgsConstructor;
// import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
@Tag(name = "1. 유저 관리", description = "회원가입/로그인 API")
public class UserController {

    private final UserRepository userRepository;
    private final JwtTokenProvider jwtTokenProvider;

    @Data
    public static class LoginRequest{
        private String email;
        private String passward;
    }

    @Data
    public static class UpdateProfileRequest{
        private String name;
    }

    @Data
    public static class PasswardRequest {
        private Long userId;
        private String passward;
        private String newPassward;
    }

    // 1. 회원가입
    @PostMapping
    @Operation(summary = "회원가입")
    public ResponseEntity<?> registerUser(@RequestBody User user) {
        // 이메일 중복 체크
        if (userRepository.findByEmail(user.getEmail()).isPresent()) {
            return ResponseEntity.badRequest().body("이미 존재하는 이메일입니다.");
        }
        
        // 유저 저장 (비밀번호 암호화는 나중에 추가 가능)
        User savedUser = userRepository.save(user);
        return ResponseEntity.ok(savedUser);
    }

    // 2. 로그인
    @PostMapping("/login")
    @Operation(summary = "로그인")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        String email = request.getEmail();
        String password = request.getPassward();

        // ✅ Optional 처리: .orElse(null)을 사용하여 안전하게 꺼냄
        User user = userRepository.findByEmail(email).orElse(null);

        // 유저가 없거나 비밀번호가 틀리면 401 에러
        if (user == null || !user.getPassword().equals(password)) {
            return ResponseEntity.status(401).body("이메일 또는 비밀번호가 잘못되었습니다.");
        }

        // 토큰 생성
        String token = jwtTokenProvider.createToken(user.getEmail());

        // 결과 반환 (토큰 + 유저정보)
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

    // 4. 비밀번호 확인 (변경 전 본인확인용)
    @PostMapping("/verify-password")
    @Operation(summary = "비밀번호 확인")
    public ResponseEntity<?> verifyPassword(@RequestBody PasswardRequest request) {
        Long userId = request.getUserId();
        String password = request.getPassward();

        User user = userRepository.findById(userId).orElse(null);
        if (user == null || !user.getPassword().equals(password)) {
            return ResponseEntity.status(401).body("비밀번호가 일치하지 않습니다.");
        }
        return ResponseEntity.ok("비밀번호 확인 완료");
    }

    // 5. 비밀번호 변경
    @PutMapping("/{id}/password")
    @Operation(summary = "비밀번호 변경")
    public ResponseEntity<?> updatePassword(@PathVariable Long id, @RequestBody PasswardRequest request) {
        User user = userRepository.findById(id).orElse(null);
        if (user == null) return ResponseEntity.badRequest().body("유저를 찾을 수 없습니다.");

        if (request.getNewPassward() == null || request.getNewPassward().isEmpty()){
            return ResponseEntity.badRequest().body("새 비밀번호를 입력해주세요.");
        }

        user.setPassword(request.getNewPassward());
        userRepository.save(user);
        return ResponseEntity.ok("비밀번호가 변경되었습니다.");
    }
}