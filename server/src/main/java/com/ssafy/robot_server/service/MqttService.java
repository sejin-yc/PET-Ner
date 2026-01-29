package com.ssafy.robot_server.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.domain.RobotPose;
import com.ssafy.robot_server.domain.RobotStatus;
import com.ssafy.robot_server.mqtt.MqttGateway;
import com.ssafy.robot_server.repository.RobotPoseRepository;
import com.ssafy.robot_server.repository.RobotStatusRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.integration.mqtt.support.MqttHeaders;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class MqttService {

    private final MqttGateway mqttGateway;
    private final RobotStatusRepository statusRepository;
    private final RobotPoseRepository poseRepository;
    private final SimpMessagingTemplate messagingTemplate;
    
    private final ObjectMapper objectMapper = new ObjectMapper(); 

    @ServiceActivator(inputChannel = "mqttInputChannel")
    public void handleMessage(String payload, @Header(MqttHeaders.RECEIVED_TOPIC) String topic) {
        try {
            JsonNode json = objectMapper.readTree(payload);

            // 1. 로봇 상태 수신
            if ("/sub/robot/status".equals(topic)) {
                RobotStatus s = RobotStatus.builder()
                        .batteryLevel(json.path("batteryLevel").asInt(0))
                        .temperature(json.path("temperature").asDouble(0.0))
                        .isCharging(json.path("charging").asBoolean(false))
                        .x(json.path("x").asDouble(0.0))
                        .y(json.path("y").asDouble(0.0))
                        .mode(json.path("mode").asText("unknown"))
                        .timestamp(LocalDateTime.now())
                        .build();
                
                statusRepository.save(s);
                messagingTemplate.convertAndSend("/sub/robot/status", s);

            // 2. 로봇 위치(좌표) 수신
            } else if ("/sub/robot/pose".equals(topic)) {
                RobotPose p = RobotPose.builder()
                        .x(json.path("x").asDouble(0.0))
                        .y(json.path("y").asDouble(0.0))
                        .theta(json.path("theta").asDouble(0.0)) // ✅ 각도 추가
                        .build();
                poseRepository.save(p);
                // (선택사항) 지도 실시간 갱신을 원하면 웹소켓 추가 가능
                messagingTemplate.convertAndSend("/sub/robot/pose", p);

            // 3. WebRTC 관련 (로봇 -> 웹)
            } else if ("/sub/peer/offer".equals(topic)){
                log.info("📹 WebRTC Offer 수신 (로봇 -> 웹)");
                messagingTemplate.convertAndSend("/sub/peer/offer", payload); // 원본 JSON 전달

            } else if ("/sub/peer/ice".equals(topic)) { // ✅ [중요] ICE Candidate 추가
                log.info("❄️ WebRTC ICE Candidate 수신 (로봇 -> 웹)");
                messagingTemplate.convertAndSend("/sub/peer/ice", payload);
            }

        } catch (Exception e) {
            log.error("❌ MQTT 처리 에러: {}", e.getMessage());
        }
    }

    public void sendCommand(String topic, String message) {
        mqttGateway.sendToMqtt(message, topic);
    }
}