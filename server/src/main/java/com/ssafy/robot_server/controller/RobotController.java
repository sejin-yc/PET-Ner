package com.ssafy.robot_server.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.dto.RobotCommand;
import com.ssafy.robot_server.service.MqttService;
import com.ssafy.robot_server.domain.User;
import com.ssafy.robot_server.repository.UserRepository;
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
    private final UserRepository userRepository;

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

    @PostMapping("/tts")
    public ResponseEntity<?> sendTts(@RequestBody Map<String, String> payload) {
        String userId = payload.get("userId");
        String text = payload.get("text");
        System.out.println("🗣️ TTS 요청: " + text + " (User: " + userId + ")");

        if (userId != null && text != null) {
            mqttService.sendCommand("robot/" + userId + "/control", "{\"type\": \"TTS\", \"text\": \"" + text + "\"}");
        }
        try {
            Map<String, String> commandMap = Map.of("type", "TTS", "text", text);
            String jsonCommand = objectMapper.writeValueAsString(commandMap);

            mqttService.sendCommand("robot/" + userId + "/control", jsonCommand);
            return ResponseEntity.ok("TTS 명령 전송 완료");
        } catch (JsonProcessingException e) {
            e.printStackTrace();
            return ResponseEntity.badRequest().body("userId 또는 text가 누락되었습니다.");
        }
    }
    
    @PostMapping("/training/complete")
    public ResponseEntity<?> completeTraining(@RequestBody Map<String, Object> data) {
        System.out.println("💾 목소리 학습 데이터 저장 요청: " + data);

        Long userId = null;
        try {
            userId = Long.valueOf(String.valueOf(data.get("userId")));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body("userId 형식이 잘못되었습니다.");
        }

        User user = userRepository.findById(userId).orElse(null);
        if (user == null) {
            return ResponseEntity.badRequest().body("존재하지 않는 유저입니다.");
        }

        user.setVoiceTrained(true);
        userRepository.save(user);
        
        return ResponseEntity.ok("학습 데이터 저장 완료");
    }
    

    // 1. 프론트엔드 명령 수신 (웹 -> 로봇)
    @MessageMapping("/robot/control")
    public void handleControl(RobotCommand command) {
        if (command.getUserId() == null) {
            System.err.println("❌ 명령 거부: UserID가 없습니다.");
            return;
        }
        
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
        sendSignalToRobot(answerData, "WebRTC Answer");
    }

    // ✅ [신규 추가] 3. WebRTC ICE Candidate 전달 (웹 -> 로봇)
    @MessageMapping("/peer/ice")
    public void handleIceCandidate(Map<String, Object> candidate) {
        sendSignalToRobot(candidate, "WebRTC ICE Candidate");
    }

    private void sendSignalToRobot(Map<String, Object> data, String logType) {
        Long userId = extractUserId(data);
        if (userId == null) return;

        try {
            String json = objectMapper.writeValueAsString(data);
            String targetTopic = "robot/" + userId + "/signal";
            mqttService.sendCommand(targetTopic, json);
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