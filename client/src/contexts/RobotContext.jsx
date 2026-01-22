import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { useNotifications } from './NotificationContext';
import { useAuth } from './AuthContext';
import api from '../api/axios';
import { toast } from 'sonner';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import mqtt from 'mqtt'; // ✅ stompjs 대신 mqtt 사용

const RobotContext = createContext();

// ✅ Nginx 프록시 주소 (wss://...)
const MQTT_URL = 'wss://i14c203.p.ssafy.io/ws';

export const RobotProvider = ({ children }) => {
  const { user } = useAuth();
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();

  const [client, setClient] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  
  // ✅ WebRTC 및 MQTT 관련 Ref
  const mqttClientRef = useRef(null);
  const peerConnection = useRef(null); 
  const [remoteStream, setRemoteStream] = useState(null); // 📹 영상 스트림 상태

  /* 1. 로봇 상태 */
  const [robotStatus, setRobotStatus] = useState({
    isOnline: false, battery: 80, mode: 'manual', 
    position: { x: 50, y: 50 }, speed: 0, lastUpdate: new Date().toISOString(),
  });
  const [isRobotLoading, setIsRobotLoading] = useState(true);

  /* 2. MQTT 및 WebRTC 연결 설정 */
  useEffect(() => {
    console.log("🔌 MQTT 연결 시도:", MQTT_URL);

    // (1) MQTT 연결 생성
    const mClient = mqtt.connect(MQTT_URL, {
      clean: true,
      reconnectPeriod: 1000, // 끊기면 1초마다 재연결 시도
    });

    mClient.on('connect', () => {
      console.log('✅ MQTT 연결 성공!');
      setIsConnected(true);
      setIsRobotLoading(false);
      setRobotStatus(prev => ({ ...prev, isOnline: true }));
      
      // 토픽 구독
      mClient.subscribe(['/sub/robot/status', '/sub/peer/offer'], (err) => {
        if (!err) console.log("📡 토픽 구독 완료");
      });
    });

    mClient.on('error', (err) => {
      console.error('❌ MQTT 에러:', err);
      setIsConnected(false);
    });

    // (2) 메시지 수신 처리 (로봇 상태 + WebRTC)
    mClient.on('message', async (topic, message) => {
      const payload = JSON.parse(message.toString());

      // A. 로봇 상태 데이터 수신
      if (topic === '/sub/robot/status') {
        setRobotStatus(prev => ({
          ...prev,
          isOnline: true,
          battery: payload.batteryLevel !== undefined ? payload.batteryLevel : prev.battery,
          position: (payload.x !== undefined && payload.y !== undefined) ? { x: payload.x, y: payload.y } : prev.position,
          mode: payload.mode || prev.mode,
          lastUpdate: new Date().toISOString()
        }));
      }

      // B. 📹 WebRTC Offer 수신 (영상 연결 요청)
      if (topic === '/sub/peer/offer') {
        console.log("📹 [WebRTC] Offer 받음! 연결 시작...");
        handleWebRTCOffer(payload, mClient);
      }
    });

    setClient(mClient);
    mqttClientRef.current = mClient;

    return () => {
      if (mClient) mClient.end();
      if (peerConnection.current) peerConnection.current.close();
    };
  }, []);

  // ✅ WebRTC 핸들러 함수 (Offer 처리)
  const handleWebRTCOffer = async (offer, mClient) => {
    try {
      if (peerConnection.current) {
        peerConnection.current.close(); // 기존 연결이 있으면 닫음
      }

      // 1. PeerConnection 생성
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      });

      // 2. 트랙(영상) 수신 이벤트 핸들러
      pc.ontrack = (event) => {
        console.log("🎥 영상 스트림 수신 성공! Stream ID:", event.streams[0].id);
        setRemoteStream(event.streams[0]); // 상태 업데이트 -> 화면에 표시됨
      };

      // 3. ICE Candidate 처리 (필요시 구현, 현재는 Offer/Answer에 포함됨)
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          // console.log("🧊 ICE Candidate 발견 (전송 생략)");
        }
      };

      peerConnection.current = pc;

      // 4. Offer 적용 및 Answer 생성
      await pc.setRemoteDescription(new RTCSessionDescription(offer));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      // 5. Answer 전송 (로봇에게)
      const answerPayload = {
        sdp: pc.localDescription.sdp,
        type: pc.localDescription.type
      };
      
      mClient.publish('/pub/peer/answer', JSON.stringify(answerPayload));
      console.log("📤 [WebRTC] Answer 전송 완료!");

    } catch (error) {
      console.error("❌ WebRTC 연결 실패:", error);
    }
  };

  /* 3. 데이터 조회 (기존 유지) */
  const { data: videos = [] } = useQuery({ queryKey: ['videos', user?.id], queryFn: async () => (await api.get(`/videos?userId=${user.id}`)).data, enabled: !!user?.id });
  const { data: logs = [] } = useQuery({ queryKey: ['logs', user?.id], queryFn: async () => (await api.get(`/logs?userId=${user.id}`)).data, enabled: !!user?.id });
  const deleteVideoMutation = useMutation({ mutationFn: (id) => api.delete(`/videos/${id}`), onSuccess: () => { queryClient.invalidateQueries(['videos']); toast.success("삭제되었습니다."); }});
  const deleteLogMutation = useMutation({ mutationFn: (id) => api.delete(`/logs/${id}`), onSuccess: () => { queryClient.invalidateQueries(['logs']); toast.success("삭제되었습니다."); }});

  /* 4. 로봇 제어 */
  const [isVideoOn, setIsVideoOn] = useState(true);
  const [isVoiceCloned, setIsVoiceCloned] = useState(false);
  const [useClonedVoice, setUseClonedVoice] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const moveRobot = (linear, angular) => {
    if (!mqttClientRef.current || !mqttClientRef.current.connected) return;
    if (robotStatus.mode === 'auto') return;
    // publish 사용
    mqttClientRef.current.publish("/pub/robot/control", JSON.stringify({ type: 'MOVE', linear, angular }));
  };

  const emergencyStop = () => {
    if (mqttClientRef.current?.connected) mqttClientRef.current.publish("/pub/robot/control", JSON.stringify({ type: 'STOP' }));
    setRobotStatus(prev => ({ ...prev, mode: 'emergency', speed: 0 }));
    addNotification({ type: 'alert', title: '🚨 비상 정지', message: '사용자가 로봇을 긴급 정지시켰습니다.', link: '/' });
  };

  const toggleMode = () => {
    const newMode = robotStatus.mode === 'auto' ? 'manual' : 'auto';
    if (mqttClientRef.current?.connected) mqttClientRef.current.publish("/pub/robot/control", JSON.stringify({ type: 'MODE', value: newMode }));
    setRobotStatus(prev => ({ ...prev, mode: newMode }));
    addNotification({ type: 'robot', title: '모드 변경', message: `로봇이 ${newMode === 'auto' ? '자동' : '수동'} 모드로 전환되었습니다.`, link: '/' });
  };

  const toggleVideo = () => setIsVideoOn(prev => !prev);
  const sendTTS = async (text) => {
    if (!text.trim()) return;
    addNotification({ type: 'robot', title: '🔊 음성 출력', message: `로봇이 말합니다: "${text}"`, link: '/' });
    try { await api.post('/robot/tts', { text, useClonedVoice: isVoiceCloned && useClonedVoice }); } catch(e) {}
  };
  const startWalkieTalkie = () => { setIsRecording(true); };
  const stopWalkieTalkie = () => { if (isRecording) { setIsRecording(false); addNotification({ type: 'robot', title: '📡 무전 전송', message: '사용자의 음성을 로봇으로 전송했습니다.', link: '/' }); }};
  const trainVoice = () => { toast.info("목소리 학습 시작..."); setTimeout(() => { setIsVoiceCloned(true); setUseClonedVoice(true); toast.success("학습 완료!"); }, 3000); };

  /* 5. 키보드 제어 */
  const keysPressed = useRef({}); 
  const lastCommand = useRef({ linear: 0, angular: 0 });

  useEffect(() => {
    const handleKeyDown = (e) => { if (e.target.tagName !== 'INPUT') keysPressed.current[e.key.toLowerCase()] = true; };
    const handleKeyUp = (e) => { keysPressed.current[e.key.toLowerCase()] = false; };
    window.addEventListener('keydown', handleKeyDown); window.addEventListener('keyup', handleKeyUp);
    
    const moveLoop = setInterval(() => {
      let linear = 0, angular = 0;
      if (keysPressed.current['w']) linear += 1.0; if (keysPressed.current['s']) linear -= 1.0; 
      if (keysPressed.current['a']) angular += 1.0; if (keysPressed.current['d']) angular -= 1.0;
      if (linear !== lastCommand.current.linear || angular !== lastCommand.current.angular) {
        moveRobot(linear, angular); lastCommand.current = { linear, angular };
      }
    }, 100); 
    return () => { window.removeEventListener('keydown', handleKeyDown); window.removeEventListener('keyup', handleKeyUp); clearInterval(moveLoop); };
  }, [robotStatus.mode]); 

  const addTestVideo = async () => {}; 
  const addTestLog = async () => { if (!user) return; try { await api.post('/logs', { userId: user.id, mode: "자동 모드", status: "completed", details: "테스트 로그" }); queryClient.invalidateQueries(['logs']); toast.success("로그 생성 완료"); } catch(e) {} };

  return (
    <RobotContext.Provider value={{
      client,
      isConnected,
      remoteStream, // ✅ 대시보드에서 영상 띄우기 위해 필수!

      robotStatus, isVideoOn, toggleVideo, moveRobot, emergencyStop, toggleMode,
      sendTTS, startWalkieTalkie, stopWalkieTalkie, isRecording, trainVoice, isVoiceCloned, useClonedVoice, setUseClonedVoice,
      videos, deleteVideo: deleteVideoMutation.mutate, addTestVideo, logs, deleteLog: deleteLogMutation.mutate, addTestLog, isRobotLoading,
    }}>
      {children}
    </RobotContext.Provider>
  );
};
export const useRobot = () => useContext(RobotContext);