package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.Cat;
import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.repository.CatRepository;
import com.ssafy.robot_server.repository.UserRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping({"/cat", "/cats"})
@RequiredArgsConstructor
@Tag(name = "3. 고양이 관리", description = "반려묘 등록/조회/삭제 API")
public class CatController {

    private final CatRepository catRepository;
    private final UserRepository userRepository;

    // 1. 내 고양이 목록 조회
    @GetMapping
    @Operation(summary = "고양이 목록 조회")
    public ResponseEntity<List<Cat>> getCats(@RequestParam Long userId) {
        System.out.println(">>> [DEBUG] 고양이 목록 조회 요청 들어옴! UserID: " + userId);
        return ResponseEntity.ok(catRepository.findByUserId(userId));
    }

    // 2. 고양이 등록
    @PostMapping
    @Operation(summary = "고양이 등록")
    public ResponseEntity<?> addCat(@RequestBody Cat cat) {
        // 유효성 검사: 주인이 누구인지 모르면 등록 거부
        if (cat.getUserId() == null) {
            Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
            if (authentication != null && authentication.isAuthenticated()) {
                String email = authentication.getName();
                Optional<User> user = userRepository.findByEmail(email);

                if (user.isPresent()) {
                    cat.setUserId(user.get().getId());
                } else {
                    return ResponseEntity.badRequest().body("로그인 정보를 찾을 수 없습니다.");
                }
            } else {
                return ResponseEntity.status(401).body("로그인이 필요합니다.");
            }
        }

        cat.setId(null);

        // 기본값 방어 로직
        if (cat.getHealthStatus() == null) cat.setHealthStatus("normal");
        if (cat.getBehaviorStatus() == null) cat.setBehaviorStatus("대기 중");
        
        // 이름이 없으면 '야옹이'로 설정 (선택 사항)
        if (cat.getName() == null || cat.getName().isEmpty()) cat.setName("이름 없는 고양이");
        
        cat.setLastDetected(LocalDateTime.now());

        Cat savedCat = catRepository.save(cat);
        return ResponseEntity.ok(savedCat);
    }

    // 3. 고양이 삭제
    @DeleteMapping("/{id}")
    @Operation(summary = "고양이 삭제")
    public ResponseEntity<?> deleteCat(@PathVariable Long id) {
        // 있는지 확인 후 삭제 (안전하게)
        if (catRepository.existsById(id)) {
            catRepository.deleteById(id);
            return ResponseEntity.ok("성공적으로 삭제되었습니다.");
        } else {
            return ResponseEntity.badRequest().body("해당 ID의 고양이가 존재하지 않습니다.");
        }
    }
}