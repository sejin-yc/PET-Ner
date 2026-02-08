package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.Log;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface LogRepository extends JpaRepository<Log, Long> {
    // 특정 유저의 로그만 최신순으로 가져오기
    List<Log> findByUserIdOrderByCreatedAtDesc(Long userId);
}