package com.ssafy.robot_server.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class RobotCommand {
    private Long userId;
    
    private String type;   // "MOVE", "STOP", "MODE"
    private double linear; // 전진 속도
    private double angular;// 회전 속도
    private String value;  // 모드 값 ("auto", "manual")
}