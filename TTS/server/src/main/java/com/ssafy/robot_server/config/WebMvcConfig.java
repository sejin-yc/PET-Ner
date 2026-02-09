package com.ssafy.robot_server.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Value("${audio.upload-dir:/app/uploads/audio}")
    private String audioUploadDir;

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // /uploads/audio/** → 로컬 폴더 (Pi5 다운로드용)
        String uploadsBase = audioUploadDir.replace("/audio", "");
        if (!uploadsBase.endsWith("/")) {
            uploadsBase += "/";
        }
        registry.addResourceHandler("/uploads/**")
                .addResourceLocations("file:" + uploadsBase);
    }
}
