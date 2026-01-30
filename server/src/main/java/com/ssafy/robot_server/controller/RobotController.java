package com.ssafy.robot_server.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.dto.RobotCommand;
import com.ssafy.robot_server.service.MqttService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping({"/robot", "/api/robot"})
@RequiredArgsConstructor
public class RobotController {

    private final MqttService mqttService;
    private final ObjectMapper objectMapper;

    @GetMapping("/state")
    public ResponseEntity<?> getRobotState(@RequestParam(value = "userId", required = false) String userId) {
        System.out.println("📥 HTTP 요청 수신: 로봇 상태 조회 (User: " + userId + ")");
        Map<String, Object> mockState = Map.of(
            "status", "standby",      // 로봇 상태 (standby, moving, charging)
            "battery", 85,            // 배터리 잔량
            "location", "거실",       // 현재 위치
            "isCameraOn", false       // 카메라 작동 여부
        );

        return ResponseEntity.ok(mockState);
    }

    // 1. 프론트엔드 명령 수신 (웹 -> 로봇)
    @MessageMapping("/robot/control")
    public void handleControl(RobotCommand command) {
        if (command.getUserId() == null) {
            System.err.println("❌ 명령 거부: UserID가 없습니다.");
            return;
        }

        System.out.println("🕹️ 명령 수신: " + command.getUserId() + "): " + command.getType());
        
        try {
            // ✅ 객체를 안전하게 JSON 문자열로 변환
            String jsonCommand = objectMapper.writeValueAsString(command);
            String targetTopic = "robot/" + command.getUserId() + "/control";
            
            // 로봇에게 MQTT 전송
            mqttService.sendCommand(targetTopic, jsonCommand);
        } catch (JsonProcessingException e) {
            e.printStackTrace();
        }
    }

    // 2. WebRTC Answer 전달 (웹 -> 로봇)
    @MessageMapping("/peer/answer")
    public void handleAnswer(Map<String, Object> answerData) {
        Long userId = extractUserId(answerData);
        if (userId == null) return;

        System.out.println("📡 WebRTC Answer 수신 -> User " + userId);
        try {
            String jsonAnswer = objectMapper.writeValueAsString(answerData);
            String targetTopic = "robot/" + userId + "/signal";

            mqttService.sendCommand(targetTopic, jsonAnswer);
        } catch (JsonProcessingException e) {
            e.printStackTrace();
        }
    }

    // ✅ [신규 추가] 3. WebRTC ICE Candidate 전달 (웹 -> 로봇)
    @MessageMapping("/peer/ice")
    public void handleIceCandidate(Map<String, Object> candidate) {
        Long userId = extractUserId(candidate);
        if (userId == null) return;

        try {
            // 맵 데이터를 JSON으로 바꿔서 로봇에게 전달
            String jsonCandidate = objectMapper.writeValueAsString(candidate);
            String targetTopic = "robot/" + userId + "/signal";

            mqttService.sendCommand(targetTopic, jsonCandidate);
        } catch (JsonProcessingException e) {
            e.printStackTrace();
        }
    }

    private Long extractUserId(Map<String, Object> map) {
        if (!map.containsKey("userId")) {
            System.err.println("❌ WebRTC 에러: userId 누락됨");
            return null;
        }

        try {
            return Long.valueOf(String.valueOf(map.get("userId")));
        } catch (NumberFormatException e) {
            System.err.println("❌ ID 변환 에러: " + map.get("userId"));
            return null;
        }
    }
}