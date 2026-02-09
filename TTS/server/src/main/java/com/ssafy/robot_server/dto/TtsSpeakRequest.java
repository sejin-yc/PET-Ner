package com.ssafy.robot_server.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class TtsSpeakRequest {
    private Long userId;
    private String text;
    /** true: Edge TTS 기본 음성 (GPU 미사용), false: CosyVoice 학습 목소리 */
    private boolean useDefaultVoice = false;
}
