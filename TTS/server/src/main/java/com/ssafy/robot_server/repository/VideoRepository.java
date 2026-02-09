package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.Video;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface VideoRepository extends JpaRepository<Video, Long> {
    List<Video> findByUserIdOrderByCreatedAtDesc(Long userId);
}