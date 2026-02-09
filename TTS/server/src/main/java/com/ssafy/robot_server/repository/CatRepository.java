package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.Cat;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface CatRepository extends JpaRepository<Cat, Long> {
    // userId 숫자만으로 조회
    List<Cat> findByUserId(Long userId);
}