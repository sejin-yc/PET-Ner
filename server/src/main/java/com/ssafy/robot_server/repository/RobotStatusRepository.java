package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.RobotStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional; // ✅ Null 처리를 위해 Optional 추천

@Repository
public interface RobotStatusRepository extends JpaRepository<RobotStatus, Long> {
    
    // ❌ (기존) 전체 데이터 중 1등 가져오기 -> 남의 것도 가져옴
    // RobotStatus findTopByOrderByIdDesc();

    // ✅ (수정) "내 ID(UserId)"를 가진 데이터 중에서, 가장 최신(OrderByIdDesc) 1개 가져오기
    // (Optional을 쓰면 데이터가 없을 때 null 에러를 방지하기 좋습니다)
    Optional<RobotStatus> findTopByUserIdOrderByIdDesc(Long userId);
}