package com.ssafy.robot_server.controller;

import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.handler.annotation.SendTo;
import org.springframework.stereotype.Controller;
import java.util.Map;

@Controller
public class WebRTCController {
    // 1. 로봇(Offer) -> 웹에게 전달
    @MessageMapping("/peer/offer")
    @SendTo("/sub/peer/offer")
    public Map<String, Object> handleOffer(@Payload Map<String, Object> payload) {
        System.out.println("[WebRTC] Robot Offer Received -> Sending to Web");
        return payload;
    }

    // 2. 웹(Answer) -> 로봇에게 전달
    @MessageMapping("/peer/answer")
    @SendTo("/sub/peer/answer")
    public Map<String, Object> handleAnswer(@Payload Map<String, Object> payload) {
        System.out.println("[WebRTC] Web Answer Received -> Sending to Robot");
        return payload;
    }

    // ICE Candidate 교환용
    @MessageMapping("/peer/iceCandidate")
    @SendTo("/sub/peer/iceCandidate")
    public Map<String, Object> handleIceCandidate(@Payload Map<String, Object> payload) {
        return payload;
    }
}
