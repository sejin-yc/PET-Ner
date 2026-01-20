package com.ssafy.robot_server.controller;

import com.ssafy.robot_server.domain.RobotStatus;
import com.ssafy.robot_server.dto.RobotCommand;
import com.ssafy.robot_server.repository.RobotStatusRepository;
import com.ssafy.robot_server.service.MqttService;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;

@Controller
@RequiredArgsConstructor // 생성자 주입 자동화
public class RobotController {

    private final SimpMessagingTemplate messagingTemplate;
    // private final RobotStatusRepository robotStatusRepository; // ✅ DB 저장소 추가
    private final MqttService mqttService;

    // 1. 프론트엔드 명령 수신 (웹 -> 로봇)
    // 웹에서 보낸 명령을 그대로 로봇(Python)에게 토스합니다.
    @MessageMapping("/robot/control")
    public void handleControl(RobotCommand command) {
        System.out.println("🕹️ 명령 수신: " + command.getType());
        
        // 파이썬 로봇이 구독 중인 주소로 명령 전달
        messagingTemplate.convertAndSend("/sub/robot/control", command);

        String jsonCommand = String.format(
            "{\"type\":\"%s\", \"linear\":%f, \"angular\":%f}",
            command.getType(), command.getLinear(), command.getAngular()
        );
        mqttService.sendCommand("/pub/robot/control", jsonCommand);
    }

    // // 2. 로봇 상태 수신 (로봇 -> 서버 -> DB & 웹)
    // // 파이썬 로봇이 1초마다 이 주소로 자기 상태를 보냅니다.
    // @MessageMapping("/robot/status")
    // @Transactional
    // public void handleStatus(Map<String, Object> statusData) {
    //     // (1) 데이터 파싱
    //     Double battery = Double.valueOf(statusData.get("battery").toString());
    //     Map<String, Double> position = (Map<String, Double>) statusData.get("position");
    //     Double x = Double.valueOf(position.get("x").toString());
    //     Double y = Double.valueOf(position.get("y").toString());
    //     String mode = (String) statusData.get("mode");

    //     // (2) ✅ DB에 저장 (영구 기록)
    //     RobotStatus statusEntity = new RobotStatus(battery, x, y, mode);
    //     robotStatusRepository.save(statusEntity);

    //     // (3) 웹 대시보드로 실시간 전달 (화면 갱신용)
    //     messagingTemplate.convertAndSend("/sub/robot/status", statusData);
        
    //     // 로그 확인용
    //     // System.out.println("💾 DB 저장 완료: 배터리=" + battery + "%");
    // }

    // 👇👇 [여기 추가!] 웹의 답장(Answer)을 로봇(MQTT)에게 전달 👇👇
    @MessageMapping("/peer/answer")
    public void handleAnswer(String answerJson) {
        System.out.println("📡 WebRTC Answer 수신 (웹 -> 로봇)");
        // 로봇이 듣고 있는 MQTT 주제로 쏩니다.
        mqttService.sendCommand("/pub/peer/answer", answerJson);
    }
}