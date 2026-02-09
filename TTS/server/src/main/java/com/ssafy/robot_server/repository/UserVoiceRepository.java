package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.UserVoice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface UserVoiceRepository extends JpaRepository<UserVoice, Long> {
    List<UserVoice> findByUserIdAndIsActiveTrue(Long userId);
    Optional<UserVoice> findByUserIdAndIsActiveTrueOrderByCreatedAtDesc(Long userId);
    /** 해당 user_id 의 최신 행 1개 (is_active 무관, DB에 행이 있으면 쓰기 위함) */
    Optional<UserVoice> findFirstByUserIdOrderByCreatedAtDesc(Long userId);

    /** 해당 사용자의 기존 활성 음성을 모두 비활성화 (사용자당 하나의 활성 음성만 유지) */
    @Modifying
    @Query("UPDATE UserVoice v SET v.isActive = false WHERE v.userId = :userId AND v.isActive = true")
    int deactivateAllByUserId(@Param("userId") Long userId);
}
