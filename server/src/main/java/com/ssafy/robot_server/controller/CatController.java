package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.Cat;
import com.ssafy.robot_server.repository.CatRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/user/cats")
@RequiredArgsConstructor
@Tag(name = "3. 고양이 관리", description = "반려묘 등록/조회/삭제 API")
public class CatController {

    private final CatRepository catRepository;

    // 1. 내 고양이 목록 조회
    @GetMapping
    @Operation(summary = "고양이 목록 조회")
    public ResponseEntity<List<Cat>> getCats(@RequestParam Long userId) {
        return ResponseEntity.ok(catRepository.findByUserId(userId));
    }

    // 2. 고양이 등록
    @PostMapping
    @Operation(summary = "고양이 등록")
    public ResponseEntity<?> addCat(@RequestBody Cat cat) {
        // 유효성 검사: 주인이 누구인지 모르면 등록 거부
        if (cat.getUserId() == null) {
            return ResponseEntity.badRequest().body("userId(사용자 ID)는 필수입니다.");
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