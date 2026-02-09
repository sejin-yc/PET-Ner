package com.ssafy.robot_server.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "audio_playback")
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AudioPlayback {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long userId;

    /** tts_default, tts_cloned, walkie */
    @Column(nullable = false, length = 20)
    private String type;

    @Column(length = 2000)
    private String text;

    /** URL for Pi5 to download (e.g. http://server/api/uploads/audio/xxx.wav) */
    @Column(nullable = false, length = 512)
    private String audioUrl;

    /** Relative path under uploads/audio (e.g. tts_cloned_1_20260204153011234_41.wav) */
    @Column(nullable = false, length = 256)
    private String fileName;

    /** CREATED, PLAYING, PLAYED, FAILED */
    @Column(nullable = false, length = 20)
    @Builder.Default
    private String status = "CREATED";

    @Column(nullable = false)
    @Builder.Default
    private LocalDateTime createdAt = LocalDateTime.now();

    private LocalDateTime playedAt;

    @Column(length = 500)
    private String errorMessage;

    public void setStatus(String status) {
        this.status = status;
    }

    public void setPlayedAt(LocalDateTime playedAt) {
        this.playedAt = playedAt;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }
}
