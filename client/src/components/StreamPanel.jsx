import React, { useEffect, useRef, useState } from 'react';
import { useRobot } from '../contexts/RobotContext';
import { Video, WifiOff } from 'lucide-react'; // 아이콘 추가

const StreamPanel = () => {
  const { client, isConnected } = useRobot();
  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const [status, setStatus] = useState("서버 연결 대기 중...");

  useEffect(() => {
    if (!client || !isConnected) return;

    setStatus("WebRTC 준비 중...");

    // 1. PeerConnection 생성 (STUN 서버 필수)
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" } // 구글 무료 STUN
      ]
    });
    pcRef.current = pc;

    // 2. [중요] 내 네트워크 정보(ICE Candidate)를 찾으면 로봇에게 보냄
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        client.publish({
          destination: '/pub/peer/ice', // 🚨 백엔드 Controller 확인 필요
          body: JSON.stringify(event.candidate)
        });
      }
    };

    // 3. 영상 트랙 수신 시 화면 연결
    pc.ontrack = (event) => {
      console.log("📹 영상 스트림 수신됨!");
      if (videoRef.current) {
        videoRef.current.srcObject = event.streams[0];
        setStatus("🟢 실시간 영상 연결됨");
      }
    };

    // 4. Offer 수신 (로봇 -> 나)
    const subOffer = client.subscribe('/sub/peer/offer', async (msg) => {
      try {
        const offer = JSON.parse(msg.body);
        console.log("📨 Offer 수신");
        
        await pc.setRemoteDescription(new RTCSessionDescription(offer));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

        // Answer 전송 (나 -> 로봇)
        client.publish({
          destination: '/pub/peer/answer',
          body: JSON.stringify(answer)
        });
        setStatus("🟡 연결 시도 중...");
      } catch (e) {
        console.error("WebRTC Error:", e);
      }
    });

    // 5. [중요] ICE Candidate 수신 (로봇 -> 나)
    // 로봇이 자신의 네트워크 정보를 보내주면 내 PC에 등록해야 함
    const subIce = client.subscribe('/sub/peer/ice', async (msg) => {
      try {
        const candidate = JSON.parse(msg.body);
        if (pcRef.current) {
            await pcRef.current.addIceCandidate(new RTCIceCandidate(candidate));
        }
      } catch (e) {
        console.error("ICE Error:", e);
      }
    });

    return () => {
      subOffer.unsubscribe();
      subIce.unsubscribe();
      if (pc) pc.close();
    };
  }, [client, isConnected]);

  return (
    <div className="bg-black p-4 rounded-xl shadow-lg w-full h-full flex flex-col border border-gray-800">
      {/* 헤더 */}
      <div className="flex justify-between items-center mb-4 px-2">
        <div className="flex items-center gap-2 text-white">
          <Video size={20} className="text-red-500 animate-pulse" />
          <h3 className="font-bold text-sm tracking-wider">LIVE STREAM</h3>
        </div>
        <span className="text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded">
          {status}
        </span>
      </div>

      {/* 비디오 영역 */}
      <div className="relative w-full flex-1 bg-gray-900 rounded-lg overflow-hidden flex items-center justify-center">
        <video 
          ref={videoRef} 
          autoPlay 
          playsInline 
          muted 
          className="w-full h-full object-contain"
        />
        
        {/* 연결 안 됐을 때 보여줄 아이콘 */}
        {status.includes("대기") && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600 gap-2">
                <WifiOff size={48} />
                <p className="text-sm">Connecting...</p>
            </div>
        )}
      </div>
    </div>
  );
};

export default StreamPanel;