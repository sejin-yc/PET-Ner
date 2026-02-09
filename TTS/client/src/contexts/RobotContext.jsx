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
  // 아래 두 변수는 WebRTC 연결 관련 변수
  const [remoteStream, setRemoteStream] = useState(null);
  const peerConnection = useRef(null);

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
    if (!user?.id) {
      setIsRobotLoading(false);
      return;
    }

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

  const { data: logs = [], refetch: refetchLogs } = useQuery({ queryKey: ['logs', user?.id], queryFn: async () => (await api.get(`/logs?userId=${user.id}`)).data, enabled: !!user?.id });
  const deleteLogMutation = useMutation({ mutationFn: (id) => api.delete(`/logs/${id}`), onSuccess: () => { queryClient.invalidateQueries(['logs']); toast.success("삭제되었습니다."); }});

  const [isVoiceTraining, setIsVoiceTraining] = useState(false);
  const [voiceTrainingText, setVoiceTrainingText] = useState("");
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const walkieRecorderRef = useRef(null);
  const walkieChunksRef = useRef([]);
  const walkieStreamRef = useRef(null);

  useEffect(() => {
    if (!user?.id) {
      setIsVoiceCloned(false);
      setUseClonedVoice(false);
      return;
    }
    setIsVoiceCloned(false);
    setUseClonedVoice(false);
    api.get(`/user/voice/${user.id}/status`)
      .then((res) => {
        if (res.data?.hasVoice) {
          setIsVoiceCloned(true);
          setUseClonedVoice(true);
        }
      })
      .catch(() => {
        setIsVoiceCloned(false);
        setUseClonedVoice(false);
      });
  }, [user?.id]);

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
  const startWalkieTalkie = async () => {
    if (!user?.id) {
      toast.error("로그인이 필요합니다.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      walkieStreamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      walkieRecorderRef.current = recorder;
      walkieChunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) walkieChunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        const blob = new Blob(walkieChunksRef.current, { type: recorder.mimeType });
        walkieStreamRef.current?.getTracks().forEach((t) => t.stop());
        walkieStreamRef.current = null;
        const formData = new FormData();
        formData.append("userId", user.id);
        formData.append("audio", blob, "walkie.webm");
        try {
          const res = await api.post("/audio/walkie", formData);
          if (res.data?.success) {
            addNotification({ type: 'robot', title: '📡 무전 전송', message: '음성이 저장되었고 Pi5로 재생 요청이 전송되었습니다.', link: '/' });
          } else {
            toast.error(res.data?.message || "무전 전송 실패");
          }
        } catch (err) {
          toast.error("무전 전송 실패: " + (err.response?.data?.message || err.message));
        }
        setIsRecording(false);
      };
      recorder.start();
      setIsRecording(true);
      toast.info("무전기 녹음 중... (종료 시 자동 전송)");
    } catch (err) {
      toast.error("마이크 권한이 필요합니다.");
    }
  };
  const stopWalkieTalkie = () => {
    if (walkieRecorderRef.current?.state === "recording") {
      walkieRecorderRef.current.stop();
    } else {
      setIsRecording(false);
    }
  };
  const trainVoice = async () => {
    if (!user) {
      toast.error("로그인이 필요합니다.");
      return;
    }

    const selectedText = "안녕하세요! 오늘 날씨가 정말 좋아요! 오늘도 행복한 하루 보내세요~ 사랑합니다 💗"
    setVoiceTrainingText(selectedText);
    setIsVoiceTraining(true);

    try {
      // 마이크 권한 요청
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // 형식 지정 없이 생성 → 브라우저가 사용하는 기본 형식으로 녹음됨
      const mediaRecorder = new MediaRecorder(stream);
      const actualMime = mediaRecorder.mimeType; // 실제 녹음 형식 (브라우저마다 다름: webm, mp4 등)

      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: actualMime });
        await sendVoiceToServer(audioBlob, selectedText, actualMime);
        stream.getTracks().forEach(track => track.stop());
      };

      toast.info(`"${selectedText}" 문구를 녹음해주세요.`);
      mediaRecorder.start();
      
      // 10초 후 자동 중지 (또는 사용자가 중지)
      setTimeout(() => {
        if (mediaRecorder.state === 'recording') {
          mediaRecorder.stop();
        }
      }, 10000);

    } catch (error) {
      console.error("녹음 시작 실패:", error);
      toast.error("마이크 권한이 필요합니다.");
      setIsVoiceTraining(false);
    }
  };

  // 녹음 중지
  const stopVoiceTraining = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setIsVoiceTraining(false);
  };

  // 실제 MIME 타입에서 확장자 추출 (webm, mp4, ogg, wav 등 뭐가 오든 그대로 반영)
  const getExtensionFromMime = (mime) => {
    if (!mime) return 'webm';
    const base = mime.split(';')[0].trim().toLowerCase(); // "audio/webm;codecs=opus" → "audio/webm"
    const subtype = base.includes('/') ? base.split('/')[1] : ''; // "audio/webm" → "webm"
    if (subtype === 'x-wav' || subtype === 'wav') return 'wav';
    if (subtype) return subtype; // webm, mp4, ogg, 그 외 모두 그대로 사용
    return 'webm';
  };

  // 서버로 음성 전송
  const sendVoiceToServer = async (audioBlob, promptText, recordedMimeType = 'audio/webm') => {
    if (!user?.id) {
      toast.error("로그인이 필요합니다.");
      setIsVoiceTraining(false);
      return;
    }
    try {
      setIsVoiceTraining(false);
      toast.info("음성을 서버로 전송 중...");

      const ext = getExtensionFromMime(recordedMimeType);
      const formData = new FormData();
      formData.append('userId', user.id);
      formData.append('promptText', promptText);
      formData.append('audio', audioBlob, `voice.${ext}`);

      // FormData 사용 시 Content-Type은 설정하지 않음. axios가 multipart/form-data; boundary=... 자동 설정
      const response = await api.post('/user/voice/train', formData);

      if (response.data.success) {
        setIsVoiceCloned(true);
        setUseClonedVoice(true);
        addNotification({ 
          type: 'robot', 
          title: '🎤 목소리 학습 완료', 
          message: '이제 내 목소리로 TTS를 사용할 수 있습니다.'
        });
      } else {
        toast.error(response.data.message || "학습 실패");
      }
    } catch (error) {
      console.error("음성 전송 실패:", error);
      toast.error("서버 연결 실패: " + (error.response?.data?.message || error.message));
    }
  };

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
      remoteStream, // ✅ 대시보드에서 영상 띄우기 위해 필수
      robotStatus, isRobotLoading, isVideoOn, toggleVideo,
      moveRobot, emergencyStop, toggleMode, feedRobot,
      sendTTS, startWalkieTalkie, stopWalkieTalkie, isRecording,
      trainVoice, stopVoiceTraining, isVoiceTraining, voiceTrainingText, isVoiceCloned, useClonedVoice, setUseClonedVoice,
      videos, deleteVideo, addTestVideo,
      logs, deleteLog: deleteLogMutation.mutate, addTestLog, refetchLogs
    }}>
      {children}
    </RobotContext.Provider>
  );
};
export const useRobot = () => useContext(RobotContext);