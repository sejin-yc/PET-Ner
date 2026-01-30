package com.ssafy.robot_server.handler;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.net.URI;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class WebRtcSignalingHandler extends TextWebSocketHandler {

    // 현재 접속한 세션들 (로봇, 웹) 관리
    private static final Map<Long, WebSocketSession> robotSessions = new ConcurrentHashMap<>();
    private static final Map<Long, WebSocketSession> userSessions = new ConcurrentHashMap<>();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        Long userId = getUserId(session);
        String role = getRole(session);

        if (userId == null || role == null) {
            System.err.println("❌ [WebRTC] 인증 정보 부족으로 연결 거부: " + session.getId());
            session.close(CloseStatus.BAD_DATA);
            return;
        }

        if ("robot".equalsIgnoreCase(role)) {
            robotSessions.put(userId, session);
            System.out.println("🤖 [WebRTC] 로봇 연결됨 (User " + userId + ")");
        } else {
            userSessions.put(userId, session);
            System.out.println("👤 [WebRTC] 유저 연결됨 (User " + userId + ")");
        }
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        Long userId = getUserId(session);
        String role = getRole(session);

        if (userId == null || role == null) return;

        WebSocketSession targetSession = null;
        
        if ("robot".equalsIgnoreCase(role)) {
            targetSession = userSessions.get(userId);
        } else {
            targetSession = robotSessions.get(userId);
        }

        if (targetSession != null && targetSession.isOpen()) {
            try {
                targetSession.sendMessage(message);
            } catch (IOException e) {
                System.err.println("전송 실패: " + e.getMessage());
            }
        } else {
            System.out.println("⚠️ 대상이 접속해 있지 않음 (User " + userId + ")");
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        Long userId = getUserId(session);
        String role = getRole(session);

        if (userId != null && role != null) {
            if ("robot".equalsIgnoreCase(role)) {
                robotSessions.remove(userId);
            } else {
                userSessions.remove(userId);
            }
            System.out.println("🔌 [WebRTC] 연결 종료: " + role + " (User " + userId + ")");
        }
    }

    private Long getUserId(WebSocketSession session) {
        try {
            URI uri = session.getUri();
            String query = uri.getQuery();
            if (query == null) return null;

            for (String param : query.split("&")) {
                String[] pair = param.split("=");
                if (pair.length == 2 && "userId".equals(pair[0])) {
                    return Long.parseLong(pair[1]);
                }
            }
        } catch (Exception e) {
            return null;
        }
        return null;
    }

    private String getRole(WebSocketSession session) {
        try {
            URI uri = session.getUri();
            String query = uri.getQuery();
            if (query == null) return null;

            for (String param : query.split("&")) {
                String[] pair = param.split("=");
                if (pair.length == 2 && "role".equals(pair[0])){
                    return pair[1];
                }
            }
        } catch (Exception e) {
            return null;
        }
        return null;
    }
}