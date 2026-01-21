package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional; // ✅ 이 줄이 꼭 필요합니다!

public interface UserRepository extends JpaRepository<User, Long> {
    
    // [수정 전] 아마 이렇게 되어 있을 겁니다
    // User findByEmail(String email);

    // [수정 후] Optional로 감싸주세요
    Optional<User> findByEmail(String email);
    boolean existsByEmail(String email);
}