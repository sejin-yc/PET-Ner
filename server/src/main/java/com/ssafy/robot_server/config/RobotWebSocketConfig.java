package com.ssafy.robot_server.config;

import com.ssafy.robot_server.handler.Ros2WebSocketHandler;
import com.ssafy.robot_server.handler.WebRtcSignalingHandler;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
@RequiredArgsConstructor
public class RobotWebSocketConfig implements WebSocketConfigurer {

    private final Ros2WebSocketHandler ros2WebSocketHandler;
    private final WebRtcSignalingHandler webRtcSignalingHandler;

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        // 1. 규격서 기반 로봇 데이터 수신 (WebSocket)
        registry.addHandler(ros2WebSocketHandler, "/ros2/vehicle/status")
                .setAllowedOrigins("*"); // 모든 주소 접속 허용

        // 2. WebRTC 시그널링 (WebSocket)
        registry.addHandler(webRtcSignalingHandler, "/signal")
                .setAllowedOrigins("*");
    }
}