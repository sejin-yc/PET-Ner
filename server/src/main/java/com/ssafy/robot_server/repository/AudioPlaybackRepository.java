package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.AudioPlayback;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface AudioPlaybackRepository extends JpaRepository<AudioPlayback, Long> {

    /** 최신순 목록 (DB 저장 확인용) */
    List<AudioPlayback> findAllByOrderByCreatedAtDesc(Pageable pageable);

    /** 큐: 이미 재생 중인 항목이 있는지 */
    boolean existsByStatus(String status);

    /** 큐: 대기 중(CREATED)인 것 중 가장 오래된 것 (선입선출) */
    Optional<AudioPlayback> findFirstByStatusOrderByCreatedAtAsc(String status);
}
