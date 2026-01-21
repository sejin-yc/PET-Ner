package com.ssafy.robot_server.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.dto.RobotCommand;
import com.ssafy.robot_server.service.MqttService;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.stereotype.Controller;

import java.util.Map;

@Controller
@RequiredArgsConstructor
public class RobotController {

    private final MqttService mqttService;
    private final ObjectMapper objectMapper; // ✅ JSON 변환기 (Spring 기본 내장)

    // 1. 프론트엔드 명령 수신 (웹 -> 로봇)
    @MessageMapping("/robot/control")
    public void handleControl(RobotCommand command) {
        System.out.println("🕹️ 명령 수신: " + command.getType());
        
        try {
            // ✅ 객체를 안전하게 JSON 문자열로 변환
            String jsonCommand = objectMapper.writeValueAsString(command);
            
            // 로봇에게 MQTT 전송
            mqttService.sendCommand("/pub/robot/control", jsonCommand);
            
        } catch (JsonProcessingException e) {
            e.printStackTrace();
        }
    }

    // 2. WebRTC Answer 전달 (웹 -> 로봇)
    @MessageMapping("/peer/answer")
    public void handleAnswer(String answerJson) {
        System.out.println("📡 WebRTC Answer 수신 (웹 -> 로봇)");
        // 로봇에게 그대로 토스
        mqttService.sendCommand("/pub/peer/answer", answerJson);
    }

    // ✅ [신규 추가] 3. WebRTC ICE Candidate 전달 (웹 -> 로봇)
    // 이게 없으면 서로 네트워크 경로를 못 찾아서 영상이 안 나옵니다!
    @MessageMapping("/peer/ice")
    public void handleIceCandidate(Map<String, Object> candidate) {
        System.out.println("❄️ ICE Candidate 수신 (웹 -> 로봇)");
        try {
            // 맵 데이터를 JSON으로 바꿔서 로봇에게 전달
            String jsonCandidate = objectMapper.writeValueAsString(candidate);
            mqttService.sendCommand("/pub/peer/ice", jsonCandidate);
            
        } catch (JsonProcessingException e) {
            e.printStackTrace();
        }
    }
}