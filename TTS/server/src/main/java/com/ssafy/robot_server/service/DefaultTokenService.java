package com.ssafy.robot_server.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.robot_server.domain.User;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.Map;

/**
 * 기본 음성 토큰 로드 서비스
 * User의 age, gender에 따라 적절한 기본 토큰을 선택
 */
@Service
@RequiredArgsConstructor
public class DefaultTokenService {

    private final ResourceLoader resourceLoader;
    private final ObjectMapper objectMapper;

    /**
     * User의 age, gender에 따라 profile_id 결정
     * @param age 나이 (nullable)
     * @param gender 성별 ("M", "F", null)
     * @return profile_id (예: "male_20s", "female_40s", "neutral")
     */
    public String getProfileId(Integer age, String gender) {
        if (gender == null || age == null) {
            return "neutral";
        }
        
        String genderPrefix = gender.equalsIgnoreCase("M") ? "male" : 
                             gender.equalsIgnoreCase("F") ? "female" : "neutral";
        
        if (genderPrefix.equals("neutral")) {
            return "neutral";
        }
        
        // 연령대 구분: 10s, 20s, 30s, 40s, 50s (추출된 토큰 전체 사용)
        String ageGroup;
        if (age < 20) {
            ageGroup = "10s";
        } else if (age < 30) {
            ageGroup = "20s";
        } else if (age < 40) {
            ageGroup = "30s";
        } else if (age < 50) {
            ageGroup = "40s";
        } else {
            ageGroup = "50s";
        }

        return genderPrefix + "_" + ageGroup;
    }

    /**
     * profile_id에 해당하는 기본 토큰 JSON 로드
     * @param profileId 예: "male_20s", "female_40s", "neutral"
     * @return 토큰 Map (CosyVoice /extract_tokens 응답 형식)
     * @throws IOException 파일 없거나 읽기 실패 시
     */
    public Map<String, Object> loadDefaultTokens(String profileId) throws IOException {
        String path = "classpath:default_tokens/" + profileId + ".json";
        Resource resource = resourceLoader.getResource(path);
        
        if (!resource.exists()) {
            throw new IOException("기본 토큰 파일이 없습니다: " + profileId + ".json");
        }
        
        byte[] bytes = resource.getInputStream().readAllBytes();
        String json = new String(bytes);
        
        @SuppressWarnings("unchecked")
        Map<String, Object> tokens = objectMapper.readValue(json, Map.class);
        return tokens;
    }

    /**
     * User 객체로부터 적절한 기본 토큰 로드
     * @param user User 엔티티
     * @return 토큰 Map
     * @throws IOException 토큰 로드 실패 시
     */
    public Map<String, Object> loadDefaultTokensForUser(User user) throws IOException {
        String profileId = getProfileId(user.getAge(), user.getGender());
        return loadDefaultTokens(profileId);
    }
}
