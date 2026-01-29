import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { Client } from '@stomp/stompjs';
import { useNotifications } from './NotificationContext';
import { useAuth } from './AuthContext';
import api from '../api/axios';
import { toast } from 'sonner';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

const RobotContext = createContext();

export const RobotProvider = ({ children }) => {
  const { user } = useAuth();
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();

  const [isConnected, setIsConnected] = useState(false);
  const [remoteStream, setRemoteStream] = useState(null);
  const stompClientRef = useRef(null);
  const peerConnection = useRef(null);

  /* 1. 로봇 상태 */
  const [robotStatus, setRobotStatus] = useState({
    isOnline: false, battery: 0, mode: 'manual', 
    position: { x: 50, y: 50 }, speed: 0, charging: false,
    temperature: 0.0, lastUpdate: new Date().toISOString(),
  });

  const[isVoiceCloned, setIsVoiceCloned] = useState(false);
  const[useClonedVoice, setUseClonedVoice] = useState(false);
  const[isRecording, setIsRecording] = useState(false);

  const[isRobotLoading, setIsRobotLoading] = useState(true);
  const[videos, setVideos] = useState([]);
  const[isVideoOn, setIsVideoOn] = useState(true);

  useEffect(() => {
    if (!user?.id) return;

    const fetchInitialState = async () => {
      try {
        const res = await api.get(`/robot/state?userId=${user.id}`);
        if (res.data) {
          setIsVoiceCloned(res.data.isVoiceTrained);
          setRobotStatus(prev => ({ ...prev, mode: res.data.currentMode || 'manual'}));
        }
      } catch (err) {
        console.error("초기 상태 로드 실패:", err);
      }
    };
    fetchInitialState();
  }, [user]);

  /* 2. 연결 설정 (STOMP + Signaling) */
  useEffect(() => {
    if (!user?.id) return;

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws';

    const client = new Client({
      brokerURL: wsUrl,
      reconnectDelay: 5000,
      onConnect: () => {
        console.log('✅ STOMP(데이터) 연결 성공!');
        setIsConnected(true);
        setRobotStatus(prev => ({ ...prev, isOnline: true}));

        client.subscribe(`/sub/${user.id}/robot/status`, (message) => {
          try {
            const payload = JSON.parse(message.body);
            setRobotStatus(prev => ({
              ...prev,
              isOnline: true,
              battery: payload.batteryLevel ?? prev.battery,
              charging: payload.charging ?? prev.charging,
              temperature: payload.temperature ?? prev.temperature,
              position: { x: payload.x ?? prev.position.x, y: payload.y ?? prev.position.y },
              mode: payload.mode ?? prev.mode,
              lastUpdate: new Date().toISOString()
            }));
          } catch (e) {
            console.error("데이터 파싱 에러:", e);
          }
        });

        // WebRTC Offer
        client.subscribe(`/sub/${user.id}/peer/offer`, (message) => {
          console.log("📹 [STOMP] Offer 수신됨!");
          const offer = JSON.parse(message.body);
          handleWebRTCOffer(offer);
        });

        // ICE Candidate
        client.subscribe(`/sub/${user.id}/peer/ice`, (message) => {
          const payload = JSON.parse(message.body);
          if (peerConnection.current) {
            peerConnection.current.addIceCandidate(new RTCIceCandidate(payload));
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

    return () => {
      if (client) client.deactivate();
      if (peerConnection.current) peerConnection.current.close();
    };
  }, [user]);

  // ✅ WebRTC 핸들러 함수 (Offer 처리)
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
        console.log("🎥 스트림 수신 시작!");
        setRemoteStream(event.streams[0]); 
      };

      pc.onicecandidate = (event) => {
        if (event.candidate && stompClientRef.current?.connected) {
          stompClientRef.current.publish({
            destination: '/pub/peer/ice',
            body: JSON.stringify({
              userId: user.id,
              candidate: event.candidate.candidate,
              sdpMid: event.candidate.sdpMid,
              sdpMLineIndex: event.candidate.sdpMLineIndex
            })
          });
        }
      };

      peerConnection.current = pc;
      // 4. Answer 전송
      await pc.setRemoteDescription(new RTCSessionDescription(offer));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      
      // 5. Answer 전송 (Signaling 서버로)
      if (stompClientRef.current?.connected) {
        stompClientRef.current.publish({
          destination: '/pub/peer/answer',
          body: JSON.stringify({
            userId: user.id,
            type: 'answer',
            sdp: pc.localDescription.sdp
          })
        });
      }
    } catch (error) {
      console.error("❌ WebRTC 연결 실패:", error);
    }
  };

  // 로봇 이동 제어 (STOMP 사용)
  const moveRobot = (linear, angular) => {
    if (!stompClientRef.current?.connected) return;

    const payload = { userId: user.id, type: 'MOVE', linear, angular };
    stompClientRef.current.publish({
      destination: '/pub/robot/control',
      body: JSON.stringify(payload)
    });
  };

  // 비상 정지
  const emergencyStop = () => {
    if (stompClientRef.current?.connected) {
      const payload = { userId: user.id, type: 'STOP' };
      stompClientRef.current.publish({
        destination: '/pub/robot/control',
        body: JSON.stringify(payload)
      });
    }
    setRobotStatus(prev => ({ ...prev, mode: 'emergency', speed: 0}));
    addNotification({ type: 'alert', title: '🚨 비상 정지', message: '사용자가 로봇을 긴급 정지시켰습니다.', link: '/' });
  };

  // 모드 변경
  const toggleMode = () => {
    const newMode = robotStatus.mode === 'auto' ? 'manual' : 'auto';
    if (stompClientRef.current?.connected) {
      const payload = { userId: user.id, type: 'MODE', value: newMode };
      stompClientRef.current.publish({
        destination: '/pub/robot/control',
        body: JSON.stringify(payload)
      });
    }
    setRobotStatus(prev => ({ ...prev, mode: newMode }));
    addNotification({ type: 'robot', title: '모드 변경', message: `로봇이 ${newMode === 'auto' ? '자동' : '수동'} 모드로 전환되었습니다.`, link: '/' });
  };

  // ... (TTS, WalkieTalkie 등 기존 기능 유지) ...
  const toggleVideo = () => setIsVideoOn(prev => !prev);
  const sendTTS = async (text) => {
    if (!text.trim()) return;

    addNotification({ type: 'robot', title: '🔊 음성 출력', message: `로봇이 말합니다: "${text}"`, link: '/'});
    try {
      await api.post('/robot/tts', {
        text,
        useClonedVoice: isVoiceCloned && useClonedVoice,
        userId: user.id
      });
    } catch(e) {}
  };
  const startWalkieTalkie = () => { setIsRecording(true); };
  const stopWalkieTalkie = () => { if (isRecording) { setIsRecording(false); addNotification({ type: 'robot', title: '📡 무전 전송', message: '사용자의 음성을 로봇으로 전송했습니다.', link: '/'}); }};
  const trainVoice = async () => {
    toast.info("목소리 학습 시작...");
    setTimeout(async () => {
      try {
        await api.post('/robot/training/complete', { userId: user.id });
        setIsVoiceCloned(true);
        setUseClonedVoice(true);
        toast.success("학습 완료!");
      } catch (e) {
        console.error("학습 저장 실패", e);
        toast.error("학습 상태 저장 실패");
      }
    }, 3000);
  };

  const { data: logs = [], refetch: refetchLogs } = useQuery({ queryKey: ['logs', user?.id], queryFn: async () => (await api.get(`/logs?userId=${user.id}`)).data, enabled: !!user?.id });
  const deleteLogMutation = useMutation({ mutationFn: (id) => api.delete(`/logs/${id}`), onSuccess: () => { queryClient.invalidateQueries(['logs']); toast.success("삭제되었습니다."); }});
  const addTestVideo = async () => {
    try {
      const dummyData = {
        userId: user?.id || 1,
        rentId: 999,
        vehicleId: 101,
        fileName: `test_${Date.now()}.jpg`,
        url: "/uploads/test.jpg",
        thumbnailUrl: "/uploads/test.jpg",
        duration: "00:15",
        behavior: "테스트 감지",
        catName: "테스트 냥이"
      };

      const response = await axios.post('/api/videos', dummyData);
      if (response.status === 200 || response.status === 201) {
        setVideos((prev) => [response.data, ...prev]);
        toast.success("✅ 테스트 영상이 생성되었습니다!");
      }
    } catch (error) {
      toast.error("영상 생성 실패");
    }
  };
  const deleteVideo = async (id) => {
    try {
      await api.delete(`/videos/${id}`);
      setVideos((prev) => prev.filter(v => v.id !== id));
      toast.success("삭제되었습니다.");
    } catch (error) {
      toast.error("삭제 실패");
    }
  };

  const addTestLog = async () => { if (!user) return; try { await api.post('/logs', { userId: user.id, rentId: 999, vehicleId: 101, mode: "자동 모드", status: "completed", details: "테스트 로그" }); queryClient.invalidateQueries(['logs']); toast.success("로그 생성 완료"); } catch(e) {console.error(e); toast.error("로그 생성 실패")} };

  /* 5. 키보드 제어 */
  // 현재 속도를 기억
  const currentSpeed = useRef({ linear: 0.0, angular: 0.0 });
  // 속도 설정 상수
  const SPEED_STEP = 0.2;
  const MAX_SPEED = 2.0;

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
      if (robotStatus.mode === 'auto') return;

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
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [robotStatus.mode]);

  return (
    <RobotContext.Provider value={{
      client: stompClientRef.current,
      isConnected,
      remoteStream, // ✅ 대시보드에서 영상 띄우기 위해 필수
      robotStatus, isRobotLoading,
      isVideoOn, toggleVideo,
      moveRobot, emergencyStop, toggleMode,
      sendTTS, startWalkieTalkie, stopWalkieTalkie, isRecording,
      trainVoice, isVoiceCloned, useClonedVoice, setUseClonedVoice,
      videos, deleteVideo, addTestVideo,
      logs, deleteLog: deleteLogMutation.mutate, addTestLog, refetchLogs
    }}>
      {children}
    </RobotContext.Provider>
  );
};
export const useRobot = () => useContext(RobotContext);