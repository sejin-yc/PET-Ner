import React, { useEffect, useRef, useState } from 'react';
import { useRobot } from '../contexts/RobotContext';

const StreamPanel = () => {
  // RobotContext에서 stomp client와 연결 상태를 가져옵니다.
  const { client, isConnected } = useRobot();
  
  const videoRef = useRef(null);
  const pcRef = useRef(null); // PeerConnection 저장용
  const [status, setStatus] = useState("대기 중...");

  useEffect(() => {
    // 1. 소켓이 연결되지 않았으면 아무것도 안 함
    if (!client || !isConnected) {
      setStatus("서버 연결 대기 중...");
      return;
    }

    // 2. WebRTC PeerConnection 생성 (Google STUN 서버 사용)
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" }
      ]
    });
    pcRef.current = pc;

    // 3. 로봇이 영상 트랙을 보내면 화면(video 태그)에 연결
    pc.ontrack = (event) => {
      console.log("📹 영상 스트림 수신됨!");
      if (videoRef.current) {
        videoRef.current.srcObject = event.streams[0];
        setStatus("✅ 영상 연결 성공!");
      }
    };

    // 4. Offer 수신 (로봇 -> 서버 -> React)
    // 주소 주의: MqttService.java에서 "/sub/peer/offer"로 보냄
    const subscription = client.subscribe('/sub/peer/offer', async (message) => {
      try {
        const offer = JSON.parse(message.body);
        console.log("📨 Offer 받음:", offer.type);
        setStatus("Offer 수신! 연결 시도 중...");

        // (1) Offer 설정
        await pc.setRemoteDescription(new RTCSessionDescription(offer));

        // (2) Answer 생성
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

        // (3) Answer 전송 (React -> 서버 -> 로봇)
        // 주소 주의: RobotController.java에서 "/pub/peer/answer"를 받음
        client.publish({
          destination: '/pub/peer/answer',
          body: JSON.stringify(answer)
        });
        console.log("📤 Answer 전송 완료!");

      } catch (error) {
        console.error("WebRTC 에러:", error);
        setStatus("연결 에러 발생 ❌");
      }
    });

    // 컴포넌트가 꺼질 때 정리(Cleanup)
    return () => {
      if (subscription) subscription.unsubscribe();
      if (pc) pc.close();
    };
  }, [client, isConnected]);

  return (
    <div style={styles.card}>
      <h3>📹 Real-time Cam</h3>
      <div style={styles.videoWrapper}>
        {/* 비디오 화면 */}
        <video 
          ref={videoRef} 
          autoPlay 
          playsInline 
          muted // 자동 재생을 위해 음소거 필수
          style={styles.video} 
        />
        {/* 상태 메시지 오버레이 */}
        <div style={styles.statusOverlay}>
          {status}
        </div>
      </div>
    </div>
  );
};

// 스타일 (CSS)
const styles = {
  card: {
    backgroundColor: '#222',
    padding: '20px',
    borderRadius: '12px',
    color: 'white',
    textAlign: 'center',
    boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
    width: '100%',
    maxWidth: '640px',
    margin: '0 auto', // 가운데 정렬
  },
  videoWrapper: {
    position: 'relative',
    width: '100%',
    height: '0',
    paddingBottom: '75%', // 4:3 비율 유지
    backgroundColor: 'black',
    borderRadius: '8px',
    overflow: 'hidden',
    marginTop: '15px',
  },
  video: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    objectFit: 'contain', // 비율 깨지지 않게
  },
  statusOverlay: {
    position: 'absolute',
    bottom: '10px',
    left: '10px',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    padding: '5px 10px',
    borderRadius: '4px',
    fontSize: '0.8rem',
    color: '#0f0', // 녹색 글씨
  }
};

export default StreamPanel;