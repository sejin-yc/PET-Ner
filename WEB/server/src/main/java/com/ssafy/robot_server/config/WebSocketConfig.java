package com.ssafy.robot_server.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketTransportRegistration;

@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws")
                .setAllowedOriginPatterns("*");
        
        registry.addEndpoint("/ws-sockjs")
                .setAllowedOriginPatterns("*")
                .withSockJS();
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // 메시지 구독 요청 url (받을 때)
        registry.enableSimpleBroker("/sub", "/topic", "/queue")
                .setTaskScheduler(heartBeatScheduler())
                .setHeartbeatValue(new long[]{10000, 10000});
        // 메시지 발행 요청 url (보낼 때)
        registry.setApplicationDestinationPrefixes("/pub", "/app");
    }

    @Override
    public void configureWebSocketTransport(WebSocketTransportRegistration registration) {
        // 메시지 최대 크기를 512KB로 설정 (기본값보다 크게)
        registration.setMessageSizeLimit(512 * 1024); 
        // 전송 시간 제한 늘리기
        registration.setSendTimeLimit(20 * 10000);
        // 버퍼 크기 늘리기
        registration.setSendBufferSizeLimit(512 * 1024);
    }

    @Bean
    public TaskScheduler heartBeatScheduler() {
        return new ThreadPoolTaskScheduler();
    }
}