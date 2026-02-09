package com.ssafy.robot_server.repository;

import com.ssafy.robot_server.domain.Notification;
import com.ssafy.robot_server.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;

public interface NotificationRepository extends JpaRepository<Notification, Long> {
    List<Notification> findByUserOrderByTimestampDesc(User user);
    
    @Transactional
    void deleteByUser(User user); // 전체 삭제용
}