import React, { useEffect, useState, useRef } from 'react';
import { useRobot } from '../contexts/RobotContext';
import { Video, VideoOff, Disc, PlayCircle, StopCircle, RefreshCw } from 'lucide-react';

const StreamPanel = () => {
  const SIGNALING_SERVER_URL = "wss://i14c203.p.ssafy.io/ws";

  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  
  const { isRecording } = useRobot();

  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const wsRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      stopStream();
    };
  }, []);

  const startStream = () => {
    if (isConnecting || isStreaming) return;

    setIsConnecting(true);
    setErrorMsg(null);

    try {
      const ws = new WebSocket(SIGNALING_SERVER_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("✅ WebSocket Open");

        const connectFrame = "CONNECT\naccept-version:1.1,1.0\nheart-beat:10000,10000\n\n\0";
        ws.send(connectFrame);
      };

      ws.onmessage = async (event) => {
        const msg = event.data;
        
        if (msg === '\n' || msg === '\r\n') return;

        if (msg.startsWith("CONNECTED")) {
          console.log("✅ STOMP 연결 성공");

          const startFrame = "SEND\ndestination:/pub/robot/stream/start\ncontent-type:application/json\n\n{}\0";
          ws.send(startFrame);
          console.log("📤 스트리밍 시작 요청");

          subscribeToOffer(ws);
          return;
        }

        if (msg.startsWith("MESSAGE")) {
          const parts = msg.split(/\n\n|\r\n\r\n/);

          if (parts.length < 2) return;

          const rawBody = parts[parts.length - 1].replace(/\0/g, "");

          if (!rawBody) return;

          try {
            const data = JSON.parse(rawBody);

            if (data.type === "offer") {
              console.log("Offer 수신");
              await handleOffer(data, ws);
            }
          } catch (e) {
            console.error("JSON 파싱 에러:", e);
          }
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket 에러:", err);

        setErrorMsg("Server Connecting Failed")
        setIsConnecting(false);
      };

      ws.onclose = () => {
        console.log("WebSocket 연결 종료");

        if (mountedRef.current) {
          setIsConnecting(false);
          setIsStreaming(false);
        }
      };
    } catch (err) {
      console.error("스트림 시작 실패:", err);

      setIsConnecting(false);
    }
  };

  const subscribeToOffer = (ws) => {
    const subFrame = "SUBSCRIBE\nid:sub-0\ndestination:/sub/peer/offer\n\n\0";
    ws.send(subFrame);
    console.log("📡 Offer 구독 시작");
  };

  const handleOffer = async (offerData, ws) => {
    try {
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
      });

      pcRef.current = pc;

      pc.ontrack = (event) => {
        console.log("🎥 비디오 트랙 수신됨!");

        if (videoRef.current) {
          videoRef.current.srcObject = event.streams[0];
          videoRef.current.play().catch(e => console.log("자동 재생 정책:", e));

          setIsStreaming(true);
          setIsConnecting(false);
        }
      };

      await pc.setRemoteDescription(new RTCSessionDescription(offerData));

      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      const payload = JSON.stringify({
        sdp: pc.localDescription.sdp,
        type: pc.localDescription.type
      });

      const sendFrame = `SEND\ndestination:/pub/peer/answer\ncontent-type:application/json\n\n${payload}\0`;
      ws.send(sendFrame);
      console.log("📤 Answer 전송 완료");
    } catch (e) {
      console.error("WebRTC 핸들링 에러:", e);
      setErrorMsg("연결 처리 중 오류");
      setIsConnecting(false);
    }
  };

  const stopStream = () => {
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

    setIsStreaming(false);
    setIsConnecting(false);
  };

  const toggleStream = () => {
    if (isStreaming) stopStream();
    else startStream();
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
            HOME CAM
          </h3>
        </div>

        <div className='flex items-center gap-3'>
          {isRecording && (
            <span className='text-xs font-bold text-red-500 flex items-center gap-1 bg-red-900/20 px-2 py-1 rounded border border-red-900/50 animate-pulse'>
              <Disc size={12} fill='currentColor' /> REC
            </span>
          )}

          {/* 영상 제어 버튼 복구 */}
          <button
            onClick={toggleStream}
            disabled={isConnecting}
            className={`text-xs px-3 py-1.5 rounded-full font-bold flex items-center gap-1.5 transition-all shadow-lg active:scale-95 ${
              isStreaming
                ? "bg-red-600 hover:bg-red-700 text-white border border-red-500"
                : "bg-green-600 hover:bg-green-700 text-white border border-green-500"
            } ${isConnecting ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            {isConnecting ? (
              <><RefreshCw size={14} className='animate-spin' />연결 중</>
            ) : isStreaming ? (
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
            muted={true}
            className={`w-full h-full object-contain ${isStreaming ? 'block' : 'hidden'}`}
          />

          {!isStreaming && (
            <div className='absolute inset-0 flex flex-col items-center justify-center text-gray-500 bg-gray-950'>
              <div className='w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-4 shadow-inner'>
                <VideoOff size={32} className='opacity-50' />
              </div>
              <p className='text-sm font-medium'>
                {errorMsg ? <span className='text-red-400'>{errorMsg}</span> : "카메라가 꺼져 있습니다"}
              </p>
            </div>
          )}
      </div>
    </div>
  );
};

export default StreamPanel;