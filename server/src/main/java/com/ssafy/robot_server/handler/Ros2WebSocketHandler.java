package com.ssafy.robot_server.handler;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

@Component
public class Ros2WebSocketHandler extends TextWebSocketHandler {

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        System.out.println("🤖 [ROS2] 로봇이 서버에 연결되었습니다! ID: " + session.getId());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        // 로봇이 보낸 데이터(JSON) 확인
        String payload = message.getPayload();
        System.out.println("📩 [ROS2 데이터 수신]: " + payload);
        
        // TODO: 여기서 받은 데이터를 파싱해서 DB에 저장하거나, 웹(React)으로 쏘는 로직이 필요함.
        // (일단 오늘은 로봇->서버 연결부터 확인합시다)
    }
}