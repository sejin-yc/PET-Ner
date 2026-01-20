// WebMvcConfig.java 예시
package com.ssafy.robot_server.config; // 패키지명 확인!

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                // 🚨 여기에 배포된 도메인을 반드시 추가해야 합니다!
                .allowedOrigins("https://i14c203.p.ssafy.io", "http://localhost:5173")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowCredentials(true);
    }
}