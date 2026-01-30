package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import java.time.LocalDateTime;

@Entity
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table(name = "robot_status")
public class RobotStatus {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private Long userId;

    // ✅ MqttService 필드 (배터리, 온도, 충전여부)
    private Integer batteryLevel;
    private Double temperature;
    private Boolean isCharging;

    // ✅ RobotController 시뮬레이터 필드 (좌표, 모드)
    private Double x;
    private Double y;
    private String mode;
    
    @CreationTimestamp
    @Column(updatable = false)
    private LocalDateTime timestamp;

    // ✅ 호환성 생성자 (유지)
    public RobotStatus(Double battery, Double x, Double y, String mode) {
        this.batteryLevel = (battery != null) ? battery.intValue() : 0;
        this.x = x;
        this.y = y;
        this.mode = mode;
        this.temperature = 0.0;
        this.isCharging = false;
    }
}