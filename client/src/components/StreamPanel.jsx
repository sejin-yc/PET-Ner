import React, { useEffect, useState, useRef } from 'react';
import { useRobot } from '../contexts/RobotContext';
import { Video, VideoOff, Disc, PlayCircle, StopCircle, RefreshCw } from 'lucide-react';

const StreamPanel = () => {
  // 1. 설정
  const SIGNALING_SERVER_URL = "wss://i14c203.p.ssafy.io/ws"

  // 2. 상태 관리
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [isRecording, setIsRecording] = useState(false);

  const { robotStatus } = useRobot();

  // WebRTC 관련 레퍼런스
  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const wsRef = useRef(null);

  const mountedRef = useRef(true);

  useEffect(() => {
    setIsRecording(!!robotStatus?.isRecording);
  }, [robotStatus]);

  useEffect(() => {
    mountedRef.current = true;

    const wasStreaming = sessionStorage.getItem('isStreamingState');
    if(wasStreaming === 'true') {
      console.log("🔄 새로고침 감지: 영상 자동 재연결 시도");
      startStream();
    }

    return () => {
      mountedRef.current = false;
      stopStream(false);
    };
  }, []);

  // 1. WebRTC 연결 시작 함수
  const startStream = async () => {
    if (isConnecting || isStreaming) return;

    setIsConnecting(true);
    setErrorMsg(null);

    sessionStorage.setItem('isStreamingState', 'true');

    try {
      // 1-1. RTCPeerConnection 생성
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
      });
      pcRef.current = pc;

      // 1-2. 트랙 수신 이벤트 핸들러
      pc.ontrack = (event) => {
        console.log("🎥 비디오 트랙 수신됨!");
        if (videoRef.current){
          videoRef.current.srcObject = event.streams[0];
          if (mountedRef.current) {
            setIsStreaming(true);
            setIsConnecting(false);
          }
        }
      };

      // 1-3. 웹소켓 연결
      const ws = new WebSocket(SIGNALING_SERVER_URL);
      wsRef.current = ws;

      ws.onopen = async () => {
        console.log("✅ 시그널링 서버 연결됨");
        ws.send("CONNECT\naccept-version:1.1,1.0\n\n\0");
      };

      ws.onmessage = async (event) => {
        if (!mountedRef.current) return;

        const msg = event.data;

        if (msg.startsWith("CONNECTED")) {
          const startFrame = "SEND\ndestination:/pub/robot/stream/start\ncontent-type:application/json\n\n{}\0";
          ws.send(startFrame);

          console.log("📤 스트리밍 시작 요청 전송 (/pub/robot/stream/start)");

          subscribeToOffer(ws);
          return;
        }

        if (msg.startsWith("MESSAGE")) {
          const bodyIndex = msg.indexOf("\n\n");
          if (bodyIndex === -1) return;

          const body = msg.substring(bodyIndex + 2).replace(/\0/g, "");
          if (!body) return;

          try {
            const data = JSON.parse(body);

            if (data.type === "offer") {
              console.log("📩 로봇의 Offer 수신:", data.robotId);

              if (!pcRef.current) return;

              if (pcRef.current.signalingState !== "stable") {
                await Promise.all([
                  pcRef.current.setLocalDescription({ type: "rollback" }),
                  pcRef.current.setRemoteDescription(new RTCSessionDescription(data))
                ]);
              } else {
                await pc.setRemoteDescription(new RTCSessionDescription(data));
              }

              const answer = await pcRef.current.createAnswer();
              await pcRef.current.setLocalDescription(answer);

              const payload = JSON.stringify({
                sdp: pcRef.current.localDescription.sdp,
                type: pcRef.current.localDescription.type
              });

              const sendFrame = `SEND\ndestination:/pub/peer/answer\ncontent-type:application/json\n\n${payload}\0`;
              ws.send(sendFrame);
              console.log("📤 Answer 전송 완료");
            }
          } catch (e) {
            console.error("JSON 파싱 에러:", e);
          }
        }
      };

      ws.onerror = (err) => {
        console.error("웹소켓 에러:", err);
        if (mountedRef.current){
          setErrorMsg("서버 연결 실패");
          setIsConnecting(false);
        }
      };

      ws.onclose = () => {
        console.log("웹소켓 연결 종료");
        if (mountedRef.current){
          setIsConnecting(false);
          setIsStreaming(false);
        }
      }
    } catch (err) {
      console.error("스트림 시작 중 에러:", err);
      if (mountedRef.current){
        setErrorMsg("스트림 초기화 실패");
        setIsConnecting(false);
      }
    }
  };

  const subscribeToOffer = (ws) => {
    const subFrame = "SUBSCRIBE\nid:sub-1\ndestination:/sub/peer/offer\n\n\0";
    ws.send(subFrame);
    console.log("📡 Offer 구독 시작... 로봇 신호 대기 중");
  };

  const stopStream = (isManualStop = true) => {
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    if (mountedRef.current){
      setIsStreaming(false);
      setIsConnecting(false);
    }

    if (isManualStop) {
      sessionStorage.removeItem('isStreamingState');
    }
  };

  const toggleStream = () => {
    if (isStreaming) {
      stopStream(true);
    } else {
      startStream();
    }
  };

  return (
    <div className="bg-black p-4 rounded-xl shadow-lg w-full h-full flex flex-col border border-gray-800 relative overflow-hidden">
      {/* 헤더 */}
      <div className="flex justify-between items-center mb-4 px-2 z-10">
        <div className="flex items-center gap-2 text-white">
          {isStreaming ? (
            <Video size={20} className='text-green-500 animate-pulse' />
          ) : (
            <VideoOff size={20} className='text-gray-500' />
          )}
          <h3 className='font-bold text-sm tracking-wider text-gray-200'>
            ROBOT CAM
          </h3>
        </div>

        <div className='flex items-center gap-3'>
          {isRecording && (
            <span className='text-xs font-bold text-red-500 flex items-center gap-1 bg-red-900/20 px-2 py-1 rounded border border-red-900/50 animate-pulse'>
              <Disc size={12} fill='currentColor' /> REC
            </span>
          )}

          <button
            onClick={toggleStream}
            disabled={isConnecting}
            className={`text-xs px-3 py-1.5 rounded-full font-bold flex items-center gap-1.5 transition-all shadow-lg active:scale-95 ${
              isStreaming
                ? "bg-red-600 hover:bg-red-700 text-white border border-red-500"
                : "bg-green-600 hover:bg-green-700 text-white border border-green500"
            } ${isConnecting ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            {isConnecting ? (
              <><RefreshCw size={14} className='animate-spin' /> 연결 중 </>
            ) : isStreaming? (
              <> <StopCircle size={14} /> 영상 종료 </>
            ) : (
              <> <PlayCircle size={14} /> 영상 시작 </>
            )}
          </button>
        </div>
      </div>

      <div className='relative w-full flex-1 bg-gray-900 rounded-lg overflow-hidden border border-gray-800/50 group flex items-center justify-center'>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`w-full h-full object-contain ${isStreaming ? 'block' : 'hidden'}`}
          />

          {!isStreaming && !isConnecting && (
            <div className='absolute inset-0 flex flex-col items-center justify-center text-gray-500 bg-gray-950'>
              <div className='w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-4 shadow-inner'>
                <VideoOff size={32} className='opacity-50' />
              </div>
              <p className='text-sm font-medium'>
                {errorMsg ? <span className='text-red-400'>{errorMsg}</span> : "카메라 연결 대기 중"}
              </p>
              <button
                onClick={startStream}
                className='mt-6 px-6 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg transition-colors border border-gray-700'
              >
                연결하기
              </button>
            </div>
          )}
          
          {isConnecting && (
            <div className='absolute inset-0 flex flex-col items-center justify-center text-gray-400 bg-gray-900/90 z-20'>
              <RefreshCw size={32} className='animate-spin mb-2 text-green-500' />
              <p className='text-sm'>로봇 신호 대기 중</p>
              <p className='text-xs text-gray-500 mt-2'>로봇 코드가 실행되면 자동으로 연결됩니다.</p>
            </div>
          )}
      </div>
    </div>
  );
};

export default StreamPanel;