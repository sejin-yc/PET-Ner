package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.RobotPose;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface RobotPoseRepository extends JpaRepository<RobotPose, Long> {
    
    // 1. 특정 유저의 모든 이동 경로 가져오기 (데이터가 많으면 느려질 수 있음)
    List<RobotPose> findByUserId(Long userId);

    // 2. (추천) 특정 유저의 "최신 100개" 좌표만 가져오기 (지도 궤적 그리기용)
    List<RobotPose> findTop100ByUserIdOrderByTimestampDesc(Long userId);
}