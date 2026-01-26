package com.ssafy.robot_server.handler;

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

    // ✅ 웹(React)으로 메시지를 보내기 위한 배달부 (STOMP)
    private final SimpMessagingTemplate messagingTemplate;

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        System.out.println("🤖 [ROS2] 로봇 연결됨: " + session.getId());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        String payload = message.getPayload();
        // System.out.println("📩 [ROS2 데이터]: " + payload); // 로그 너무 많으면 주석 처리

        // ✅ [핵심] 받은 데이터를 웹 프론트엔드로 바로 토스!
        // React는 "/sub/robot/status"를 구독하고 있으면 데이터를 받게 됨.
        try {
            messagingTemplate.convertAndSend("/sub/robot/status", payload);
        } catch (Exception e) {
            System.err.println("메시지 전달 실패: " + e.getMessage());
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        System.out.println("🔌 [ROS2] 로봇 연결 해제됨");
    }
}