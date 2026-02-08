package com.ssafy.robot_server.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.domain.RobotPose;
import com.ssafy.robot_server.domain.RobotStatus;
import com.ssafy.robot_server.mqtt.MqttGateway;
import com.ssafy.robot_server.repository.RobotStatusRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.integration.mqtt.support.MqttHeaders;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class MqttService {

    private final MqttGateway mqttGateway;
    private final RobotStatusRepository statusRepository;
    private final SimpMessagingTemplate messagingTemplate;
    
    private final ObjectMapper objectMapper = new ObjectMapper(); 

    @ServiceActivator(inputChannel = "mqttInputChannel")
    public void handleMessage(String payload, @Header(MqttHeaders.RECEIVED_TOPIC) String topic) {
        try {
            JsonNode json = objectMapper.readTree(payload);
            if (!json.has("userId")) return;
            Long userId = json.get("userId").asLong();

            // 1. 로봇 상태 수신
            if (topic.endsWith("/status")) {
                RobotStatus s = RobotStatus.builder()
                        .userId(userId)
                        .batteryLevel(json.path("batteryLevel").asInt(0))
                        .temperature(json.path("temperature").asDouble(0.0))
                        .isCharging(json.path("charging").asBoolean(false))
                        .x(json.path("x").asDouble(0.0))
                        .y(json.path("y").asDouble(0.0))
                        .mode(json.path("mode").asText("unknown"))
                        .build();
                
                statusRepository.save(s);

                String webSocketDest = "/topic/robot/" + userId + "/status";
                messagingTemplate.convertAndSend(webSocketDest, s);

            // 2. 로봇 위치(좌표) 수신
            } else if (topic.endsWith("/pose")) {
                RobotPose p = RobotPose.builder()
                        .userId(userId)
                        .x(json.path("x").asDouble(0.0))
                        .y(json.path("y").asDouble(0.0))
                        .theta(json.path("theta").asDouble(0.0))
                        .build();

                String webSocketDest = "/topic/robot/" + userId + "/pose";
                messagingTemplate.convertAndSend(webSocketDest, p);

            } else if (topic.endsWith("/cat_state")) {
                String webSocketDest = "/topic/robot/" + userId + "/cat_state";
                messagingTemplate.convertAndSend(webSocketDest, json);
            } else if (topic.endsWith("/offer")){
                messagingTemplate.convertAndSend("/topic/peer/" + userId + "/offer", payload);
            } else if (topic.endsWith("/ice")) {
                messagingTemplate.convertAndSend("/topic/peer/" + userId + "/ice", payload);
            } else if (topic.endsWith("/answer")) {
                messagingTemplate.convertAndSend("/topic/peer/" + userId + "/answer", payload);
            }

        } catch (Exception e) {
            log.error("❌ MQTT 처리 에러: {}", e.getMessage());
        }
    }

    public void sendCommand(String topic, String message) {
        mqttGateway.sendToMqtt(message, topic);
    }
}