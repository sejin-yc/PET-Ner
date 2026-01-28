import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { Client } from '@stomp/stompjs';
import { useNotifications } from './NotificationContext';
import { useAuth } from './AuthContext';
import api from '../api/axios';
import { toast } from 'sonner';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
// import mqtt from 'mqtt'; // ✅ stompjs 대신 mqtt 사용

const RobotContext = createContext();

// ✅ Nginx 프록시 주소 (wss://...)
// const MQTT_URL = 'wss://i14c203.p.ssafy.io/ws';

const STOMP_URL = 'wss://i14c203.p.ssafy.io/ws';
const SIGNAL_URL = 'wss://i14c203.p.ssafy.io/signal';

// const STOMP_URL = 'ws://localhost:8080/ws';
// const SIGNAL_URL = 'ws://localhost:8080/signal';

export const RobotProvider = ({ children }) => {
  const { user } = useAuth();
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();

  const [videos, setVideos] = useState([]);

  // const [client, setClient] = useState(null);
  // const [isConnected, setIsConnected] = useState(false);
  
  // // ✅ WebRTC 및 MQTT 관련 Ref
  // const mqttClientRef = useRef(null);
  // const peerConnection = useRef(null); 
  // const [remoteStream, setRemoteStream] = useState(null); // 📹 영상 스트림 상태

  const [isConnected, setIsConnected] = useState(false);
  const stompClientRef = useRef(null);
  const signalWsRef = useRef(null);

  const peerConnection = useRef(null);
  const [remoteStream, setRemoteStream] = useState(null);

  /* 1. 로봇 상태 */
  const [robotStatus, setRobotStatus] = useState({
    isOnline: false, battery: 80, mode: 'manual', 
    position: { x: 50, y: 50 }, speed: 0, lastUpdate: new Date().toISOString(),
  });
  const [isRobotLoading, setIsRobotLoading] = useState(true);

  /* 2. MQTT 및 WebRTC 연결 설정 */
  // useEffect(() => {
  //   // 중복 연결 방지
  //   if (mqttClientRef.current) return;

  //   console.log("🔌 MQTT 연결 시도:", MQTT_URL);

  //   // (1) MQTT 연결 생성
  //   const mClient = mqtt.connect(MQTT_URL, {
  //     clean: true,
  //     reconnectPeriod: 1000,

  //     username: 'ssafy',
  //     password: '1',
  //   });

  //   mClient.on('connect', () => {
  //     console.log('✅ MQTT 연결 성공!');
  //     setIsConnected(true);
  //     setIsRobotLoading(false);
  //     setRobotStatus(prev => ({ ...prev, isOnline: true }));
      
  //     // 📡 토픽 구독 (콜백 함수 없이 토픽만 넣어야 함!)
  //     mClient.subscribe(['/sub/robot/status', '/sub/peer/offer'], (err) => {
  //       if (!err) console.log("📡 토픽 구독 완료");
  //       else console.error("❌ 구독 실패:", err);
  //     });
  //   });

  //   mClient.on('error', (err) => {
  //     console.error('❌ MQTT 에러:', err);
  //     setIsConnected(false);
  //   });

  //   // 📩 메시지 수신 통합 처리 (여기서 message.body가 아니라 그냥 message를 씁니다)
  //   mClient.on('message', async (topic, message) => {
  //     try {
  //       const payload = JSON.parse(message.toString()); // Buffer -> String -> JSON

  //       // A. 로봇 상태 데이터 수신
  //       if (topic === '/sub/robot/status') {
  //         setRobotStatus(prev => ({
  //           ...prev,
  //           isOnline: true,
  //           battery: payload.batteryLevel !== undefined ? payload.batteryLevel : prev.battery,
  //           position: (payload.x !== undefined && payload.y !== undefined) ? { x: payload.x, y: payload.y } : prev.position,
  //           mode: payload.mode || prev.mode,
  //           lastUpdate: new Date().toISOString()
  //         }));
  //       }

  //       // B. 📹 WebRTC Offer 수신 (영상 연결 요청)
  //       if (topic === '/sub/peer/offer') {
  //         console.log("📹 [WebRTC] Offer 받음! 연결 시작...");
  //         handleWebRTCOffer(payload, mClient);
  //       }
  //     } catch (e) {
  //       console.error("메시지 파싱 에러:", e);
  //     }
  //   });

  //   setClient(mClient);
  //   mqttClientRef.current = mClient;

  //   return () => {
  //     if (mClient) {
  //       console.log("🔌 MQTT 연결 종료");
  //       mClient.end();
  //     }
  //     if (peerConnection.current) peerConnection.current.close();
  //     mqttClientRef.current = null;
  //   };
  // }, []); // 의존성 배열 비움

  /* 2. 연결 설정 (STOMP + Signaling) */
  useEffect(() => {
    // ------------------------------------------------
    // A. STOMP 연결 (로봇 데이터 수신 & 제어)
    // ------------------------------------------------
    const client = new Client({
      brokerURL: STOMP_URL,
      reconnectDelay: 5000,
      onConnect: () => {
        console.log('✅ STOMP(데이터) 연결 성공!');
        setIsConnected(true);
        setIsRobotLoading(false);
        setRobotStatus(prev => ({ ...prev, isOnline: true}));

        client.subscribe('/sub/robot/status', (message) => {
          try {
            const payload = JSON.parse(message.body);
            setRobotStatus(prev => ({
              ...prev,
              isOnline: true,
              battery: payload.status?.vehicleStatus?.batteryLevel ?? prev.battery,
              position: (payload.currentLocation) ? { x: payload.currentLocation.x, y: payload.currentLocation.y } : prev.position,
              mode: payload.status?.module?.status === 'ACTIVE' ? 'auto' : 'manual',
              lastUpdate: new Date().toISOString()
            }));
          } catch (e) {
            console.error("데이터 파싱 에러:", e);
          }
        });
      },
      onDisconnect: () => {
        console.log('🔌 STOMP 연결 끊김');
        setIsConnected(false);
      },
    });
    client.activate();
    stompClientRef.current = client;

    const signalWs = new WebSocket(SIGNAL_URL);
    signalWsRef.current = signalWs;

    signalWs.onopen = () => {
      console.log("✅ Signaling(영상) 서버 연결 성공!");
    };

    signalWs.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);

        if (payload.type === 'offer') {
          console.log("📹 [WebRTC] Offer 수신");
          handleWebRTCOffer(payload);
        }
        else if (payload.candidate) {
          if (peerConnection.current) {
            peerConnection.current.addIceCandidate(new RTCIceCandidate(payload));
          }
        }
      } catch (e) {
        console.error("Signaling 에러:", e);
      }
    };

    return () => {
      if (client) client.deactivate();
      if (signalWs) signalWs.close();
      if (peerConnection.current) peerConnection.current.close();
    };
  }, []);

  // ✅ WebRTC 핸들러 함수 (Offer 처리)
  // const handleWebRTCOffer = async (offer, mClient) => {
    const handleWebRTCOffer = async (offer) => {
    try {
      if (peerConnection.current) {
        peerConnection.current.close(); 
      }

      // 1. PeerConnection 생성
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      });

      // 2. 트랙(영상) 수신 이벤트 핸들러
      pc.ontrack = (event) => {
        // console.log("🎥 영상 스트림 수신 성공! Stream ID:", event.streams[0].id);
        console.log("🎥 스트림 수신 시작!");
        setRemoteStream(event.streams[0]); 
      };

      // peerConnection.current = pc;

      // // 3. Offer 적용 및 Answer 생성
      // await pc.setRemoteDescription(new RTCSessionDescription(offer));
      // const answer = await pc.createAnswer();
      // await pc.setLocalDescription(answer);

      pc.onicecandidate = (event) => {
        if (event.candidate && signalWsRef.current?.readyState === WebSocket.OPEN) {
          signalWsRef.current.send(JSON.stringify({
            candidate: event.candidate.candidate,
            sdpMid: event.candidate.spdMid,
            sdpMLineIndex: event.candidate.sdpMLineIndex
          }));
        }
      };

      peerConnection.current = pc;

      // 4. Answer 전송
      // const answerPayload = {
      //   sdp: pc.localDescription.sdp,
      //   type: pc.localDescription.type
      // };

      await pc.setRemoteDescription(new RTCSessionDescription(offer));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      
      // 5. Answer 전송 (Signaling 서버로)
      if (signalWsRef.current?.readyState === WebSocket.OPEN) {
        signalWsRef.current.send(JSON.stringify({ type: 'answer', sdp: pc.localDescription.sdp }));
        console.log("📤 [WebRTC] Answer 전송 완료");
        // const answerPayload = {
          // type: 'answer',
          // sdp: pc.localDescription.sdp
        }
        // signalWsRef.current.send(JSON.stringify(answerPayload));
        // console.log("📤 [WebRTC] Answer 전송 완료")
      // STOMP가 아니므로 headers 없이( {}, ) 바로 보냅니다.
      // mClient.publish('/pub/peer/answer', JSON.stringify(answerPayload));
      // console.log("📤 [WebRTC] Answer 전송 완료!");
    } catch (error) {
      console.error("❌ WebRTC 연결 실패:", error);
    }
  };

  /* 3. 데이터 조회 (기존 유지) */
  // const { data: videos = [] } = useQuery({ queryKey: ['videos', user?.id], queryFn: async () => (await api.get(`/videos?userId=${user.id}`)).data, enabled: !!user?.id });
  const { data: logs = [] } = useQuery({ queryKey: ['logs', user?.id], queryFn: async () => (await api.get(`/logs?userId=${user.id}`)).data, enabled: !!user?.id });
  // const deleteVideoMutation = useMutation({ mutationFn: (id) => api.delete(`/videos/${id}`), onSuccess: () => { queryClient.invalidateQueries(['videos']); toast.success("삭제되었습니다."); }});
  const deleteLogMutation = useMutation({ mutationFn: (id) => api.delete(`/logs/${id}`), onSuccess: () => { queryClient.invalidateQueries(['logs']); toast.success("삭제되었습니다."); }});

  /* 4. 로봇 제어 */
  const [isVideoOn, setIsVideoOn] = useState(true);
  const [isVoiceCloned, setIsVoiceCloned] = useState(false);
  const [useClonedVoice, setUseClonedVoice] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  // MQTT Control
  // const moveRobot = (linear, angular) => {
  //   if (!mqttClientRef.current || !mqttClientRef.current.connected) return;
  //   if (robotStatus.mode === 'auto') return;
    
  //   // ✅ publish 사용 (send 아님)
  //   mqttClientRef.current.publish("/pub/robot/control", JSON.stringify({ type: 'MOVE', linear, angular }));
  // };

  // const emergencyStop = () => {
  //   if (mqttClientRef.current?.connected) mqttClientRef.current.publish("/pub/robot/control", JSON.stringify({ type: 'STOP' }));
  //   setRobotStatus(prev => ({ ...prev, mode: 'emergency', speed: 0 }));
  //   addNotification({ type: 'alert', title: '🚨 비상 정지', message: '사용자가 로봇을 긴급 정지시켰습니다.', link: '/' });
  // };

  // const toggleMode = () => {
  //   const newMode = robotStatus.mode === 'auto' ? 'manual' : 'auto';
  //   if (mqttClientRef.current?.connected) mqttClientRef.current.publish("/pub/robot/control", JSON.stringify({ type: 'MODE', value: newMode }));
  //   setRobotStatus(prev => ({ ...prev, mode: newMode }));
  //   addNotification({ type: 'robot', title: '모드 변경', message: `로봇이 ${newMode === 'auto' ? '자동' : '수동'} 모드로 전환되었습니다.`, link: '/' });
  // };

  // const toggleVideo = () => setIsVideoOn(prev => !prev);
  // const sendTTS = async (text) => {
  //   if (!text.trim()) return;
  //   addNotification({ type: 'robot', title: '🔊 음성 출력', message: `로봇이 말합니다: "${text}"`, link: '/' });
  //   try { await api.post('/robot/tts', { text, useClonedVoice: isVoiceCloned && useClonedVoice }); } catch(e) {}
  // };
  // const startWalkieTalkie = () => { setIsRecording(true); };
  // const stopWalkieTalkie = () => { if (isRecording) { setIsRecording(false); addNotification({ type: 'robot', title: '📡 무전 전송', message: '사용자의 음성을 로봇으로 전송했습니다.', link: '/' }); }};
  // const trainVoice = () => { toast.info("목소리 학습 시작..."); setTimeout(() => { setIsVoiceCloned(true); setUseClonedVoice(true); toast.success("학습 완료!"); }, 3000); };

  // 로봇 이동 제어 (STOMP 사용)
  const moveRobot = (linear, angular) => {
    if (!stompClientRef.current || !stompClientRef.current.connected) return;
    if (robotStatus.mode === 'auto') return;

    const payload = { type: 'MOVE', linear, angular };
    stompClientRef.current.publish({ destination: '/pub/robot/control', body: JSON.stringify(payload) });
  };

  // 비상 정지
  const emergencyStop = () => {
    if (stompClientRef.current?.connected) {
      stompClientRef.current.publish({ destination: '/pub/robot/control', body: JSON.stringify({ type: 'STOP' }) });
    }
    setRobotStatus(prev => ({ ...prev, mode: 'emergency', speed: 0}));
    addNotification({ type: 'alert', title: '🚨 비상 정지', message: '사용자가 로봇을 긴급 정지시켰습니다.', link: '/' });
  };

  // 모드 변경
  const toggleMode = () => {
    const newMode = robotStatus.mode === 'auto' ? 'manual' : 'auto';
    if (stompClientRef.current?.connected) {
      stompClientRef.current.publish({ destination: '/pub/robot/control', body: JSON.stringify({ type: 'MODE', value: newMode }) });
    }
    setRobotStatus(prev => ({ ...prev, mode: newMode }));
    addNotification({ type: 'robot', title: '모드 변경', message: `로봇이 ${newMode === 'auto' ? '자동' : '수동'} 모드로 전환되었습니다.`, link: '/' });
  };

  // ... (TTS, WalkieTalkie 등 기존 기능 유지) ...
  const toggleVideo = () => setIsVideoOn(prev => !prev);
  const sendTTS = async (text) => {
    if (!text.trim()) return;
    addNotification({ type: 'robot', title: '🔊 음성 출력', message: `로봇이 말합니다: "${text}"`, link: '/'});
    try { await api.post('/robot/tts', { text, useClonedVoice: isVoiceCloned && useClonedVoice }); } catch(e) {}
  };
  const startWalkieTalkie = () => { setIsRecording(true); };
  const stopWalkieTalkie = () => { if (isRecording) { setIsRecording(false); addNotification({ type: 'robot', title: '📡 무전 전송', message: '사용자의 음성을 로봇으로 전송했습니다.', link: '/'}); }};
  const trainVoice = () => { toast.info("목소리 학습 시작..."); setTimeout(() => { setIsVoiceCloned(true); setUseClonedVoice(true); toast.success("학습 완료!"); }, 3000); };
  const addTestVideo = async () => {
    try {
      const dummyData = {
        userId: 1,
        rentId: 999,
        vehicleId: 101,
        fileName: `test_${Date.now()}.jpg`,
        url: "/uploads/test.jpg",
        thumbnailUrl: "/uploads/test.jpg",
        duration: "00:15",
        behavior: "테스트 감지",
        catName: "테스트 냥이"
      };

      console.log("서버로 요청 보냄:", dummyData);

      const response = await axios.post('/api/videos', dummyData);
      if (response.status === 200 || response.status === 201) {
        setVideos((prev) => [response.data, ...prev]);
        toast.success("✅ 테스트 영상이 생성되었습니다!");
      }
    } catch (error) {
      console.error("영상 생성 실패:", error);
      toast.error("❌ 에러 발생: " + (error.response?.status || error.message));
    }
  };

  const deleteVideo = async (id) => {
    try {
      await api.delete(`/videos/${id}`);
      setVideos((prev) => prev.filter(v => v.id !== id));
      toast.success("삭제되었습니다.");
    } catch (error) {
      console.error("삭제 실패:", error);
      toast.error("삭제 실패");
    }
  };

  const addTestLog = async () => { if (!user) return; try { await api.post('/logs', { userId: user.id, rentId: 999, vehicleId: 101, mode: "자동 모드", status: "completed", details: "테스트 로그" }); queryClient.invalidateQueries(['logs']); toast.success("로그 생성 완료"); } catch(e) {console.error(e); toast.error("로그 생성 실패")} };

  /* 5. 키보드 제어 */
  // const keysPressed = useRef({}); 
  // const lastCommand = useRef({ linear: 0, angular: 0 });

  // 현재 속도를 기억
  const currentSpeed = useRef({ linear: 0.0, angular: 0.0 });

  // 속도 설정 상수
  const SPEED_STEP = 0.2;
  const MAX_SPEED = 2.0;

  useEffect(() => {
    // const handleKeyDown = (e) => {if (e.target.tagName !== 'INPUT') keysPressed.current[e.key.toLowerCase()] = true; };
    // const handleKeyUp = (e) => { keysPressed.current[e.key.toLowerCase()] = false; };

    const handleKeyDown = (e) => {
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;

      const key = e.key.toLowerCase();
      let isChanged = false;

      switch (key) {
        case 'w':
          currentSpeed.current.linear = Math.min(currentSpeed.current.linear + SPEED_STEP, MAX_SPEED);
          isChanged = true;
          break;

        case 'x':
          currentSpeed.current.linear = Math.max(currentSpeed.current.linear - SPEED_STEP, -MAX_SPEED);
          isChanged = true;
          break;

        case 'a':
          currentSpeed.current.angular = Math.min(currentSpeed.current.angular + SPEED_STEP, MAX_SPEED);
          isChanged = true;
          break;
        
        case 'd':
          currentSpeed.current.angular = Math.max(currentSpeed.current.angular - SPEED_STEP, -MAX_SPEED);
          isChanged = true;
          break;

        case 's':
          currentSpeed.current = { linear: 0.0, angular: 0.0 };
          isChanged = true;
          break;
        
        default:
          return;
      }

      if (isChanged) {
        moveRobot(currentSpeed.current.linear, currentSpeed.current.angular);
        console.log(`🚀 속도 변경: Linear=${currentSpeed.current.linear.toFixed(1)}, Angular=${currentSpeed.current.angular.toFixed(1)}`);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    
    // const moveLoop = setInterval(() => {
    //   let linear = 0, angular = 0;
    //   if (keysPressed.current['w']) linear += 1.0; if (keysPressed.current['s']) linear -= 1.0; 
    //   if (keysPressed.current['a']) angular += 1.0; if (keysPressed.current['d']) angular -= 1.0;
    //   if (linear !== lastCommand.current.linear || angular !== lastCommand.current.angular) {
    //     moveRobot(linear, angular); lastCommand.current = { linear, angular };
    //   }
    // }, 100); 
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []); 

  return (
    <RobotContext.Provider value={{
      client: stompClientRef.current,
      isConnected,
      remoteStream, // ✅ 대시보드에서 영상 띄우기 위해 필수

      robotStatus, isVideoOn, toggleVideo, moveRobot, emergencyStop, toggleMode,
      sendTTS, startWalkieTalkie, stopWalkieTalkie, isRecording, trainVoice, isVoiceCloned, useClonedVoice, setUseClonedVoice,
      videos, deleteVideo, addTestVideo, logs, deleteLog: deleteLogMutation.mutate, addTestLog, isRobotLoading,
    }}>
      {children}
    </RobotContext.Provider>
  );
};
export const useRobot = () => useContext(RobotContext);