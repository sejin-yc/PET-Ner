package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.repository.UserRepository;
import com.ssafy.robot_server.security.JwtTokenProvider;
import com.ssafy.robot_server.service.VoiceJetsonSyncService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder; // ✅ 필수 추가
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
// @RequestMapping("/api/users")
@RequestMapping("user")
@RequiredArgsConstructor
@Tag(name = "1. 유저 관리", description = "회원가입/로그인 API")
public class UserController {

    private final UserRepository userRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final PasswordEncoder passwordEncoder; // ✅ 암호화 도구 주입
    private final VoiceJetsonSyncService voiceJetsonSyncService;

    // ✅ 오타 수정 (passward -> password)
    @Data
    public static class LoginRequest{
        private String email;
        private String password;
    }

    @Data
    public static class UpdateProfileRequest{
        private String name;
        private Integer age;
        private String gender; // "M", "F", null
    }

    @Data
    public static class PasswordRequest {
        private Long userId;
        private String password;    // 현재 비번
        private String newPassword; // 새 비번
    }

    // 1. 회원가입
    @PostMapping
    @Operation(summary = "회원가입")
    public ResponseEntity<?> registerUser(@RequestBody User user) {
        if (userRepository.findByEmail(user.getEmail()).isPresent()) {
            return ResponseEntity.badRequest().body("이미 존재하는 이메일입니다.");
        }
        
        // ✅ 비밀번호 암호화 후 저장 (필수!)
        user.setPassword(passwordEncoder.encode(user.getPassword()));
        
        User savedUser = userRepository.save(user);
        return ResponseEntity.ok(savedUser);
    }

    // 2. 로그인
    @PostMapping("/login")
    @Operation(summary = "로그인")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail()).orElse(null);

        // ✅ 암호화된 비밀번호 비교 (matches 함수 사용 필수)
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            return ResponseEntity.status(401).body("이메일 또는 비밀번호가 잘못되었습니다.");
        }

        String token = jwtTokenProvider.createToken(user.getEmail());

        // 로그인한 유저에게 음성 토큰이 있으면 Jetson으로 미리 전송 (JETSON_VOICE_URL 설정 시만)
        voiceJetsonSyncService.syncTokenToJetson(user.getId());

        Map<String, Object> response = new HashMap<>();
        response.put("token", token);
        response.put("user", user);

        return ResponseEntity.ok(response);
    }

    // 3. 프로필 수정 (이름, 나이, 성별)
    @PutMapping("/{id}/profile")
    @Operation(summary = "프로필 수정")
    public ResponseEntity<?> updateProfile(@PathVariable Long id, @RequestBody UpdateProfileRequest request) {
        User user = userRepository.findById(id).orElse(null);
        if (user == null) return ResponseEntity.badRequest().body("유저를 찾을 수 없습니다.");

        if (request.getName() != null) {
            user.setName(request.getName());
        }
        if (request.getAge() != null) {
            user.setAge(request.getAge());
        }
        if (request.getGender() != null) {
            user.setGender(request.getGender());
        }
        userRepository.save(user);
        return ResponseEntity.ok(user);
    }

    // 4. 비밀번호 확인 (설정 페이지 진입용)
    @PostMapping("/verify-password")
    @Operation(summary = "비밀번호 확인")
    public ResponseEntity<?> verifyPassword(@RequestBody PasswordRequest request) {
        User user = userRepository.findById(request.getUserId()).orElse(null);
        
        // ✅ 여기도 matches 사용
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

    // ✅ [추가됨] 6. 회원 탈퇴 (프론트엔드 SettingsPage에서 호출함)
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