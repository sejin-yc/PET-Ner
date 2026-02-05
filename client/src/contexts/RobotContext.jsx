import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import mqtt from 'mqtt';
import { useNotifications } from './NotificationContext';
import { useAuth } from './AuthContext';
import api from '../api/axios';
import { toast } from 'sonner';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const RobotContext = createContext();

export const RobotProvider = ({ children }) => {
  const { user } = useAuth();
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();

  const MQTT_BROKER_URL = "wss://i14c203.p.ssafy.io/mqtt"

  const [client, setClient] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  const lastCommandTime = useRef(0);
  const currentSpeed = useRef({ linear: 0.0, angular: 0.0 });

  /* 1. 로봇 상태 */
  const [robotStatus, setRobotStatus] = useState({
    isOnline: false, battery: 0, mode: 'manual', 
    position: { x: 0, y: 0 },x: 0.0, y: 0.0, theta: 0.0,
    speed: 0, charging: false,
    temperature: 0.0, lastUpdate: new Date().toISOString(),
  });

  const[isVoiceCloned, setIsVoiceCloned] = useState(() => {
    return localStorage.getItem('isVoiceCloned') === 'true';
  });

  const[useClonedVoice, setUseClonedVoice] = useState(false);
  const[isRecording, setIsRecording] = useState(false);

  const[isRobotLoading, setIsRobotLoading] = useState(true);
  const[videos, setVideos] = useState([]);
  const[isVideoOn, setIsVideoOn] = useState(true);

  const getLocalVideos = () => {
    try {
      const saved = localStorage.getItem('localTestVideos');
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      return [];
    }
  };

  useEffect(() => {
    localStorage.setItem('isVoiceCloned', isVoiceCloned);
  }, [isVoiceCloned]);

  const fetchVideos = useCallback(async () => {
    if (!user?.id) return;

    try {
      let serverVideos = [];

      try {
        const res = await api.get(`/videos?userId=${user.id}`);
        serverVideos = res.data || [];
      } catch (e) {
        console.log("서버 영상 없음 혹은 에러 (무시 가능)");
      }

      const localVideos = getLocalVideos();
      const formattedLocal = localVideos.map(v => ({ ...v, isLocal: true }));
      setVideos([...formattedLocal, ...serverVideos]);
    } catch (err) {
      console.error("영상 목록 로드 실패:", err);
    }
  }, [user]);

  useEffect(() => {
    if (!user?.id) return;

    const fetchInitialState = async () => {
      try {
        const res = await api.get(`/robot/state?userId=${user.id}`);
        if (res.data) {
          if (res.data.isVoiceTrained !== undefined){
            setIsVoiceCloned(res.data.isVoiceTrained);
          }
          setRobotStatus(prev => ({
            ...prev,
            mode: res.data.currentMode || 'manual',
            battery: res.data.battery || prev.battery
          }));
        }
      } catch (err) {
        console.error("초기 상태 로드 실패:", err);
      } finally {
        setIsRobotLoading(false);
      }
    };
    fetchInitialState();
    fetchVideos();
  }, [user, fetchVideos]);

  /* 2. 연결 설정 (STOMP + Signaling) */
  useEffect(() => {
    const userId = user?.id || '1';
    const mqttClient = mqtt.connect(MQTT_BROKER_URL, {
      keepalive: 60,
      protocolId: 'MQTT',
      protocolVersion: 4,
      reconnectPeriod: 2000,
      connectTimeout: 30 * 1000,
      clean: true,
      path: '/mqtt'
    });

    mqttClient.on('connect', () => {
      console.log('✅ MQTT 연결 성공!');
      setIsConnected(true);
      setRobotStatus(prev => ({ ...prev, isOnline: true }));

      const statusTopic = `robot/${userId}/status`;

      mqttClient.subscribe([statusTopic], (err) => {
        if (!err) console.log(`📡 토픽 구독 완료: ${statusTopic}`);
      });
    });

    mqttClient.on('message', (topic, message) => {
      const msgString = message.toString();

      try{
        if (topic === `robot/${userId}/status`) {
          const payload = JSON.parse(msgString);
          setRobotStatus(prev => ({
            ...prev,
            isOnline: true,
            battery: payload.battery ?? prev.battery,
            charging: payload.charging ?? prev.charging,
            temperature: payload.temperature ?? prev.temperature,
            mode: payload.mode ?? prev.mode,
            x: payload.x ?? prev.x,
            y: payload.y ?? prev.y,
            theta: payload.theta ?? prev.theta,
            position: { x: payload.x ?? prev.position.x, y: payload.y ?? prev.position.y },
            lastUpdate: new Date().toISOString()
          }));
        } 
      } catch (e) {
        console.error("MQTT 메시지 파싱 에러:", e);
      }
    });

    mqttClient.on('close', () => {
      setIsConnected(false);
      setRobotStatus(prev => ({ ...prev, isOnline: false }));
    });

    setClient(mqttClient);

    return () => {
      if (mqttClient) mqttClient.end();
    };
  }, [user]);

  // 로봇 이동 제어 (STOMP 사용)
  const moveRobot = useCallback((linear, angular) => {
    if (!client?.connected) return;

    const payload = JSON.stringify({
      userId: user?.id || 1,
      type: "MOVE",
      linear,
      angular
    });
    
    client.publish(`robot/${user?.id || '1'}/control`, payload);
  }, [client, user]);

  // 비상 정지
  const emergencyStop = () => {
    if (client?.connected) {
      const payload = JSON.stringify({ userId: user?.id || 1, type: "EMERGENCY_STOP" });
      client.publish(`robot/${user?.id || '1'}/control`, payload);
    }
    setRobotStatus(prev => ({ ...prev, mode: 'manual', speed: 0}));
    addNotification({ type: 'alert', title: '🚨 비상 정지', message: '사용자가 로봇을 긴급 정지시켰습니다.', link: '/' });
  };

  // 모드 변경
  const toggleMode = () => {
    const newMode = robotStatus.mode === 'auto' ? 'manual' : 'auto';
    if (client?.connected) {
      const payload = JSON.stringify({
        userId: user?.id || 1,
        type: "MODE_CHANGE",
        mode: newMode
      });
      
      client.publish(`robot/${user?.id || '1'}/control`, payload)
    }
    setRobotStatus(prev => ({ ...prev, mode: newMode }));
    addNotification({ type: 'robot', title: '모드 변경', message: `로봇이 ${newMode === 'auto' ? '자동' : '수동'} 모드로 전환되었습니다.`, link: '/' });
  };

  const feedRobot = (itemType) => {
    if (!client?.connected) {
      toast.error("로봇이 연결되지 않았습니다.");
      return;
    }

    const payload = JSON.stringify({
      userId: user?.id || 1,
      type: "FEED",
      item: itemType
    });

    client.publish(`robot/${user?.id || '1'}/control`, payload);

    const message = itemType === 'churu' ? "츄르를 줍니다! 🍭" : "밥을 줍니다! 🍚";
    toast.success(message);
    addNotification({ type: 'info', title: '급여 실행', message: message, link: '/'});
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
        userId: user?.id
      });
    } catch(e) {
      console.error("TTS 전송 실패", e);
    }
  };

  const startWalkieTalkie = () => setIsRecording(true);
  const stopWalkieTalkie = () => {
    if (isRecording) {
      setIsRecording(false);
      addNotification({ type: 'robot', title: '📡 무전 전송', message: '사용자의 음성을 로봇으로 전송했습니다.', link: '/'});
    }
  };

  const trainVoice = async () => {
    toast.info("목소리 학습 시작...");
    setTimeout(async () => {
      try {
        await api.post('/robot/training/complete', { userId: user?.id });
        setIsVoiceCloned(true);
        setUseClonedVoice(true);
        toast.success("학습 완료!");
      } catch (e) {
        console.error("학습 저장 실패", e);
        toast.error("학습 상태 저장 실패");
      }
    }, 3000);
  };

  const { data: logs = [], refetch: refetchLogs } = useQuery({
    queryKey: ['logs', user?.id],
    queryFn: async () => (await api.get(`/logs?userId=${user?.id}`)).data,
    enabled: !!user?.id
  });

  const deleteLogMutation = useMutation({
    mutationFn: (id) => api.delete(`/logs/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries(['logs']);
      toast.success("삭제되었습니다.");
    }
  });

  const addTestVideo = async () => {
    try {
      const dummyId = Date.now();
      const dummyData = {
        id: dummyId,
        userId: user?.id || 1,
        rentId: 999,
        vehicleId: 101,
        fileName: `test_${dummyId}.jpg`,
        url: "https://placehold.co/600x400?text=Test+Video",
        thumbnailUrl: "https://placehold.co/600x400?text=Test+Video",
        duration: "00:15",
        behavior: "테스트 감지",
        catName: "테스트 냥이",
        isLocal: true,
        createAt: new Date().toISOString()
      };

      setVideos((prev) => [dummyData, ...prev]);

      const currentLocal = getLocalVideos();
      localStorage.setItem('localTestVideos', JSON.stringify([dummyData, ...currentLocal]));

      toast.success("✅ 테스트 영상이 생성되었습니다!");
    } catch (error) {
      toast.error("영상 생성 실패");
    }
  };

  const deleteVideo = async (id) => {
    if (!id) {
      console.error("삭제할 ID가 없습니다.");
      return;
    }

    try {
      const targetVideo = videos.find(v => v.id === id);
      const isLocalVideo = targetVideo?.isLocal || (typeof id === 'number' && id > 1700000000000);
      if (isLocalVideo) {
        const currentLocal = getLocalVideos();
        const updatedLocal = currentLocal.filter(v => v.id !== id);
        localStorage.setItem('localTestVideos', JSON.stringify(updatedLocal));

        setVideos((prev) => prev.filter(v => v.id !== id));
        toast.success("삭제되었습니다.");
        return;
      } else {
        await api.delete(`/videos/${id}`);
        setVideos((prev) => prev.filter(v => v.id !== id));
        toast.success("삭제되었습니다.") 
      }
    } catch (error) {
      console.error("영상 삭제 에러:", error)
      setVideos((prev) => prev.filter(v => v.id !== id));
      toast.error("삭제 실패");
    }
  };

  const addTestLog = async () => {
    if (!user) return;
    
    try {
      await api.post('/logs', {
        userId: user.id,
        rentId: 999,
        vehicleId: 101,
        mode: "자동 모드",
        status: "completed",
        details: "테스트 로그"
      });
      queryClient.invalidateQueries(['logs']);
      toast.success("로그 생성 완료");
    } catch(e) {
      toast.error("로그 생성 실패");
    }
  };

  /* 5. 키보드 제어 */
  // 속도 설정 상수
  const SPEED_STEP = 0.2;
  const MAX_SPEED = 2.0;

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
      if (robotStatus.mode === 'auto') return;

      const now = Date.now();
      if (now - lastCommandTime.current < 100) return;
      lastCommandTime.current = now;

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
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [robotStatus.mode, moveRobot]);

  return (
    <RobotContext.Provider value={{
      client,
      isConnected,
      robotStatus, isRobotLoading,
      isVideoOn, toggleVideo,
      moveRobot, emergencyStop, toggleMode, feedRobot,
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