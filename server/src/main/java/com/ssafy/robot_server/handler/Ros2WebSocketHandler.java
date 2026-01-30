package com.ssafy.robot_server.handler;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

@Component
@RequiredArgsConstructor
public class Ros2WebSocketHandler extends TextWebSocketHandler {

    // ✅ 웹(React)으로 메시지를 보내기 (STOMP)
    private final SimpMessagingTemplate messagingTemplate;
    private final ObjectMapper objectMapper;

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        System.out.println("🤖 [ROS2] 로봇 연결됨: " + session.getId());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        String payload = message.getPayload();

        try {
            JsonNode jsonNode = objectMapper.readTree(payload);

            if (jsonNode.has("userId")) {
                long userId = jsonNode.get("userId").asLong();

                String destination = "/sub/robot/" + userId + "/status";

                messagingTemplate.convertAndSend(destination, payload);
            } else {
                System.err.println("⚠️ 주인 없는 데이터: " + payload);
            }
        } catch (Exception e) {
            System.err.println("메시지 전달 실패: " + e.getMessage());
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        System.out.println("🔌 [ROS2] 로봇 연결 해제됨");
    }
}