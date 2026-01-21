package com.ssafy.robot_server.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI openAPI() {
        // 1. JWT 토큰 설정 정의
        String jwt = "JWT";
        SecurityRequirement securityRequirement = new SecurityRequirement().addList(jwt);

        // 2. Components에 보안 스키마 등록 (Bearer Token)
        Components components = new Components().addSecuritySchemes(jwt, new SecurityScheme()
                .name(jwt)
                .type(SecurityScheme.Type.HTTP)
                .scheme("bearer")
                .bearerFormat("JWT")
        );

        // 3. OpenAPI 객체 생성
        return new OpenAPI()
                .info(new Info()
                        .title("🤖 지능형 로봇 관제 시스템 API")
                        .description("로봇 제어, 영상 스트리밍, 로그 관리를 위한 백엔드 API 명세서입니다.")
                        .version("v1.0.0"))
                .addSecurityItem(securityRequirement) // 이 부분이 있어야 모든 API에 자물쇠가 달립니다.
                .components(components);
    }
}