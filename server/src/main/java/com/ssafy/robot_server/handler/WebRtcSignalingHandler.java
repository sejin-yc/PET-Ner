package com.ssafy.robot_server.handler;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

@Component
public class WebRtcSignalingHandler extends TextWebSocketHandler {

    // 현재 접속한 세션들 (로봇, 웹) 관리
    private static final Set<WebSocketSession> sessions = Collections.synchronizedSet(new HashSet<>());

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        sessions.add(session);
        System.out.println("📹 [WebRTC] 새로운 연결됨: " + session.getId());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        // 받은 메시지(Offer, Answer, ICE Candidate)를 나를 제외한 다른 사람에게 그대로 전달
        String payload = message.getPayload();
        
        synchronized (sessions) {
            for (WebSocketSession s : sessions) {
                if (s.isOpen() && !s.getId().equals(session.getId())) {
                    try {
                        s.sendMessage(new TextMessage(payload));
                    } catch (IOException e) {
                        e.printStackTrace();
                    }
                }
            }
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        sessions.remove(session);
        System.out.println("🔌 [WebRTC] 연결 종료됨: " + session.getId());
    }
}