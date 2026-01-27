package com.ssafy.robot_server.config;

import com.ssafy.robot_server.security.JwtAuthenticationFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
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

    // 🔐 비밀번호 암호화 (BCrypt) - 이 친구 때문에 DB에 평문 비번(1234)이 있으면 로그인 안 됨!
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                // ✅ [수정 1] POST 제한 제거! (OPTIONS 요청 등 모든 메서드 허용)
                // 프론트에서 "/api"를 붙여서 보내므로 "/api/users/**"를 확실하게 열어줍니다.
                .requestMatchers("/api/users/**", "/users/**").permitAll()

                // 로봇 데이터(/ros2)와 WebRTC 시그널링(/signal)은 로그인 없이 접속 허용
                .requestMatchers("/ros2/**", "/signal").permitAll()
                
                // ✅ [수정 2] Swagger 및 정적 리소스, 웹소켓 허용
                .requestMatchers("/swagger-ui/**", "/v3/api-docs/**", "/ws/**", "/error").permitAll()
                
                .requestMatchers("/api/videos/**", "/uploads/**", "/api/logs/**").permitAll()

                // 3. 나머지는 인증 필요
                .anyRequest().authenticated()
            )
            .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        // ✅ 프론트엔드 주소 허용 (로컬 + 배포 주소)
        config.setAllowedOrigins(List.of("http://localhost:5173", "https://i14c203.p.ssafy.io"));
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS")); // OPTIONS 필수
        config.setAllowedHeaders(List.of("*"));
        config.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}