package com.ssafy.robot_server.config;

import com.ssafy.robot_server.security.JwtAuthenticationFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager; // ✅ 추가
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration; // ✅ 추가
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder; // ✅ 추가
import org.springframework.security.crypto.password.PasswordEncoder; // ✅ 추가
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthenticationFilter) {
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration authenticationConfiguration) throws Exception {
        return authenticationConfiguration.getAuthenticationManager();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .cors(cors -> cors.configurationSource(corsConfigurationSource())) // CORS 설정 적용
            .csrf(csrf -> csrf.disable()) // CSRF 비활성화 (JWT 사용 시 필수)
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS)) // 세션 안 씀
            .authorizeHttpRequests(auth -> auth
                // ✅ 1. 회원가입과 로그인은 무조건 허용 (토큰 검사 X)
                .requestMatchers(HttpMethod.POST, "/api/users/**", "/users/**").permitAll()
                
                .requestMatchers("/api/users/login").permitAll()

                // ✅ 2. 스웨거(Swagger) 문서도 허용
                .requestMatchers("/swagger-ui/**", "/v3/api-docs/**").permitAll()

                // WebSocket
                .requestMatchers("/ws/**").permitAll()
                
                // 3. 나머지는 다 인증 필요
                .anyRequest().authenticated()
            )
            // JWT 필터를 먼저 실행
            .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    // CORS 설정 (프론트엔드 5173 포트 허용)
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(List.of("http://localhost:5173", "https://i14c203.p.ssafy.io")); // 프론트엔드 주소
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("*"));
        config.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}