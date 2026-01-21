package com.ssafy.robot_server.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data // Getter, Setter, toString, equals, hashCode 자동 생성
@NoArgsConstructor // 기본 생성자 (Jackson 라이브러리가 JSON 변환할 때 필수)
@AllArgsConstructor // 전체 생성자 (테스트할 때 편함)
public class RobotCommand {
    private String type;   // "MOVE", "STOP", "MODE"
    private double linear; // 전진 속도
    private double angular;// 회전 속도
    private String value;  // 모드 값 ("auto", "manual")
}