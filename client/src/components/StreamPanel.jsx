import React, { useEffect, useRef, useState } from 'react';
import { useRobot } from '../contexts/RobotContext';
import { Video, WifiOff, Activity } from 'lucide-react';

const StreamPanel = () => {
  // ✅ RobotContext에서 이미 만들어진 영상(remoteStream)을 가져옵니다.
  // 복잡한 연결 로직은 Context가 다 처리해줍니다.
  const { remoteStream, isConnected } = useRobot();
  const videoRef = useRef(null);

  useEffect(() => {
    // remoteStream(영상 데이터)이 들어오면 비디오 태그에 연결
    if (videoRef.current && remoteStream) {
      console.log("📺 StreamPanel: 영상 연결됨");
      videoRef.current.srcObject = remoteStream;
    }
  }, [remoteStream]);

  // 상태 메시지 결정
  const getStatusText = () => {
    if (!isConnected) return "서버 연결 끊김";
    if (!remoteStream) return "영상 신호 대기 중...";
    return "🟢 LIVE";
  };

  return (
    <div className="bg-black p-4 rounded-xl shadow-lg w-full h-full flex flex-col border border-gray-800">
      {/* 헤더 */}
      <div className="flex justify-between items-center mb-4 px-2">
        <div className="flex items-center gap-2 text-white">
          <Video size={20} className={`text-red-500 ${remoteStream ? 'animate-pulse' : ''}`} />
          <h3 className="font-bold text-sm tracking-wider">ROBOT VIEW</h3>
        </div>
        <div className="flex items-center gap-2">
           {/* 상태 배지 */}
           <span className={`text-xs px-2 py-1 rounded flex items-center gap-1 border ${
             remoteStream 
               ? 'bg-green-900/30 text-green-400 border-green-800' 
               : 'bg-gray-800 text-gray-400 border-gray-700'
           }`}>
             {remoteStream && <Activity size={10} className="animate-bounce" />}
             {getStatusText()}
           </span>
        </div>
      </div>

      {/* 비디오 영역 */}
      <div className="relative w-full flex-1 bg-gray-900 rounded-lg overflow-hidden flex items-center justify-center border border-gray-800/50">
        
        {/* 실제 비디오 화면 */}
        <video 
          ref={videoRef} 
          autoPlay 
          playsInline 
          muted 
          className={`w-full h-full object-contain transition-opacity duration-500 ${remoteStream ? 'opacity-100' : 'opacity-0'}`}
        />
        
        {/* 연결 안 됐을 때 보여줄 대기 화면 */}
        {!remoteStream && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600 gap-3">
                <div className={`p-4 rounded-full bg-gray-800/50 ${isConnected ? 'animate-pulse' : ''}`}>
                  <WifiOff size={32} />
                </div>
                <div className="text-center">
                  <p className="text-sm font-medium text-gray-400">Signal Lost</p>
                  <p className="text-xs text-gray-600 mt-1">
                    {isConnected ? "로봇의 영상을 기다리는 중..." : "서버와 연결되지 않았습니다."}
                  </p>
                </div>
            </div>
        )}
      </div>
    </div>
  );
};

export default StreamPanel;