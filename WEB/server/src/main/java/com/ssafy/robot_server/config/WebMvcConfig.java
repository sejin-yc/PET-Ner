package com.ssafy.robot_server.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.nio.file.Paths;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Value("/app/uploads/audio")
    private String audioUploadDir;

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // /uploads/audio/** → 로컬 폴더 (Pi5 다운로드용)
        String uploadsBase = Paths.get(audioUploadDir).getParent().toString();
        String resourceLocation = "file:" + uploadsBase + "/";

        registry.addResourceHandler("/uploads/**")
                .addResourceLocations(resourceLocation);
    }
}
