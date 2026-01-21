package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp; // ✅ 이거 추가
import java.time.LocalDateTime;

@Entity
@Getter @Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table(name = "robot_status") // ✅ 테이블 이름 명시 권장
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
    
    // ✅ [수정] 누가, 어떻게 저장하든 자동으로 현재 시간이 찍히도록 설정
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
        // this.timestamp = LocalDateTime.now(); // @CreationTimestamp가 있으므로 제거해도 됨
    }
}