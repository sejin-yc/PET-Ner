package com.ssafy.robot_server.config;

import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.integration.channel.DirectChannel;
import org.springframework.integration.core.MessageProducer;
import org.springframework.integration.mqtt.core.DefaultMqttPahoClientFactory;
import org.springframework.integration.mqtt.core.MqttPahoClientFactory;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.outbound.MqttPahoMessageHandler;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageHandler;

@Configuration
public class MqttConfig {

    // application.yml에 적어둔 값들을 가져옵니다.
    //@Value("${mqtt.broker-url}")
    private String brokerUrl = "tcp://i14c203.p.ssafy.io:1883";

    @Value("${mqtt.client-id}")
    private String clientId;

    @Value("${mqtt.default-topic}")
    private String defaultTopic;

    // 1. MQTT 연결 공장 (Connection Factory)
    @Bean
    public MqttPahoClientFactory mqttClientFactory() {
        DefaultMqttPahoClientFactory factory = new DefaultMqttPahoClientFactory();
        MqttConnectOptions options = new MqttConnectOptions();
        options.setServerURIs(new String[]{brokerUrl});
        options.setCleanSession(true); // 껐다 켜면 이전 기록 삭제 (깔끔하게)
        factory.setConnectionOptions(options);
        return factory;
    }

    // 2. [수신용] 들어오는 데이터가 지나가는 통로 (Channel)
    @Bean
    public MessageChannel mqttInputChannel() {
        return new DirectChannel();
    }

    // 3. [수신용] 귀 (Inbound Adapter) - 로봇의 신호를 구독합니다.
    @Bean
    public MessageProducer inbound() {
        // 클라이언트 ID 뒤에 _in을 붙여 충돌 방지
        MqttPahoMessageDrivenChannelAdapter adapter =
                new MqttPahoMessageDrivenChannelAdapter(clientId + "_in", mqttClientFactory(), defaultTopic);
        
        adapter.setCompletionTimeout(5000);
        adapter.setConverter(new DefaultPahoMessageConverter());
        adapter.setQos(1); // 메시지 도달 보장 레벨 (1: 적어도 한 번은 도착)
        adapter.setOutputChannel(mqttInputChannel()); // 받은 데이터를 위 통로로 보냄
        return adapter;
    }

    // 4. [발신용] 나가는 데이터가 지나가는 통로 (Channel)
    @Bean
    public MessageChannel mqttOutboundChannel() {
        return new DirectChannel();
    }

    // 5. [발신용] 입 (Outbound Adapter) - 로봇에게 명령을 보냅니다.
    @Bean
    @ServiceActivator(inputChannel = "mqttOutboundChannel")
    public MessageHandler mqttOutbound() {
        // 클라이언트 ID 뒤에 _out을 붙여 충돌 방지
        MqttPahoMessageHandler messageHandler =
                new MqttPahoMessageHandler(clientId + "_out", mqttClientFactory());
        
        messageHandler.setAsync(true); // 비동기 전송 (서버 멈춤 방지)
        messageHandler.setDefaultTopic(defaultTopic);
        return messageHandler;
    }
}