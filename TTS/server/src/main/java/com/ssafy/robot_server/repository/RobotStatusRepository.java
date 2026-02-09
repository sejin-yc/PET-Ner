package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.RobotStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface RobotStatusRepository extends JpaRepository<RobotStatus, Long> {
    Optional<RobotStatus> findTopByUserIdOrderByIdDesc(Long userId);
}