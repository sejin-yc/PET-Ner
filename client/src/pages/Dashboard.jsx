import React, { useState, useEffect } from 'react';
import { useRobot } from '../contexts/RobotContext';
import { Wifi, Battery, Zap, Navigation, Power, Mic, Volume2, Play, BrainCircuit, Repeat, Hand } from 'lucide-react';
import DashboardSkeleton from '../components/skeletons/DashboardSkeleton'; // 경로 확인 필요
import StreamPanel from '../components/StreamPanel'; // ✅ 우리가 만든 완벽한 영상 패널 가져오기
import ConnectionStatus from '../components/ConnectionStatus';

const Dashboard = () => {
  const { 
    robotStatus, toggleMode, emergencyStop, moveRobot, 
    sendTTS, startWalkieTalkie, stopWalkieTalkie, isRecording,
    trainVoice, isVoiceCloned, useClonedVoice, setUseClonedVoice,
    isRobotLoading
  } = useRobot();

  const [ttsText, setTtsText] = useState("");
  const [showSkeleton, setShowSkeleton] = useState(true);
  
  // 로딩 스켈레톤 처리
  useEffect(() => {
    const timer = setTimeout(() => setShowSkeleton(false), 1000);
    return () => clearTimeout(timer);
  }, []);

  if (isRobotLoading || showSkeleton) {
    return <DashboardSkeleton />;
  }

  const handleMove = (linear, angular) => moveRobot(linear, angular);
  const isAuto = robotStatus.mode === 'auto';
  
  return (
    <div className="grid grid-cols-12 gap-6 h-full pb-10">
      
      <div className="col-span-12 flex flex-col md:flex-row justify-between items-center bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
            🤖 Intelligent Robot Dashboard
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Real-time control & monitoring system powered
          </p>
        </div>
        <div className="mt-4 md:mt-0">
          <ConnectionStatus />
        </div>
      </div>
      
      {/* === 왼쪽 패널 (지도 & 영상) === */}
      <div className="col-span-12 lg:col-span-8 space-y-6">
        
        {/* 1. 2D SLAM 맵 */}
        <section className="bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm h-[500px] flex flex-col">
          <div className="px-4 py-3 border-b border-gray-100 font-semibold text-gray-800 flex justify-between">
            <span>실시간 2D SLAM 맵</span>
            <span className="text-xs text-gray-400 font-normal mt-1">SLAM Map created by Robot</span>
          </div>
          <div className="relative flex-1 bg-gray-100 overflow-hidden">
            <div className="absolute inset-0 opacity-20" 
                 style={{ backgroundImage: 'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
            
            {/* 로봇 마커 */}
            <div className="absolute transition-all duration-300 ease-linear transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
                 style={{ 
                   left: `${robotStatus.position.x}%`, 
                   top: `${robotStatus.position.y}%` 
                 }}>
              <div className="w-8 h-8 bg-indigo-600 rounded-full border-4 border-white shadow-xl animate-pulse relative">
                <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-b-[8px] border-b-white"></div>
              </div>
              <span className="mt-1 text-xs font-bold text-indigo-800 bg-white/80 px-2 rounded shadow-sm">My Robot</span>
            </div>
          </div>
        </section>

        {/* 2. ✅ 실시간 영상 (StreamPanel 컴포넌트 재사용) */}
        <section className="bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm h-[400px]">
          {/* StreamPanel 안에 모든 영상/WebRTC 로직이 들어있습니다 */}
          <StreamPanel />
        </section>
      </div>

      {/* === 오른쪽 패널 (상태 & 제어) === */}
      <div className="col-span-12 lg:col-span-4 space-y-6">
        
        {/* 1. 상태 정보 */}
        <section className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-semibold text-gray-800 flex items-center gap-2"><Zap size={18} className="text-yellow-500" /> 로봇 상태</h3>
            <span className={`text-xs px-2 py-1 rounded font-medium ${robotStatus.isOnline ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
              {robotStatus.isOnline ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <div className="space-y-6">
             <div className="bg-gray-50 p-1 rounded-lg flex items-center relative">
                <div className={`absolute top-1 bottom-1 w-[48%] bg-white rounded shadow-sm transition-all duration-300 ${isAuto ? 'left-1' : 'left-[51%]'}`} />
                <button onClick={() => !isAuto && toggleMode()} className={`flex-1 relative z-10 py-2 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${isAuto ? 'text-indigo-600' : 'text-gray-500'}`}><Repeat size={16}/> 자동 모드</button>
                <button onClick={() => isAuto && toggleMode()} className={`flex-1 relative z-10 py-2 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${!isAuto ? 'text-indigo-600' : 'text-gray-500'}`}><Hand size={16}/> 수동 제어</button>
             </div>
             <div>
               <div className="flex justify-between text-sm mb-1">
                 <span className="flex items-center gap-1 text-gray-600"><Battery size={14}/> 배터리</span>
                 <span className={`font-bold ${robotStatus.battery < 20 ? 'text-red-600' : 'text-green-600'}`}>{Math.round(robotStatus.battery)}%</span>
               </div>
               <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                 <div className={`h-full transition-all duration-500 ${robotStatus.battery < 20 ? 'bg-red-500' : 'bg-green-500'}`} style={{width: `${robotStatus.battery}%`}} />
               </div>
             </div>
          </div>
        </section>

        {/* 2. 제어 컨트롤러 */}
        <section className={`bg-white rounded-lg border border-gray-200 shadow-sm p-5 transition-opacity duration-300 ${isAuto ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
           <div className="flex justify-between items-center mb-4"><h3 className="font-semibold text-gray-800 flex items-center gap-2"><Navigation size={18} /> 수동 제어</h3>{isAuto && <span className="text-[10px] text-red-500 font-bold border border-red-200 bg-red-50 px-2 py-0.5 rounded">자동 모드 중</span>}</div>
           <div className="flex flex-col items-center gap-3">
             <div className="grid grid-cols-3 gap-2">
               <div />
               <ControlButton onClick={() => handleMove(1, 0)} icon={<Navigation size={20} className="rotate-0"/>} label="W" />
               <div />
               <ControlButton onClick={() => handleMove(0, 1)} icon={<Navigation size={20} className="-rotate-90"/>} label="A" />
               <div className="w-14 h-14 bg-gray-50 rounded-xl flex items-center justify-center border border-gray-200"><div className="w-2 h-2 bg-gray-400 rounded-full" /></div>
               <ControlButton onClick={() => handleMove(0, -1)} icon={<Navigation size={20} className="rotate-90"/>} label="D" />
               <div />
               <ControlButton onClick={() => handleMove(-1, 0)} icon={<Navigation size={20} className="rotate-180"/>} label="S" />
               <div />
             </div>
             <button onClick={emergencyStop} className="w-full mt-2 bg-red-600 hover:bg-red-700 text-white py-3 rounded-lg text-sm font-bold flex items-center justify-center gap-2 transition-all shadow-red-200 shadow-lg active:scale-95 pointer-events-auto"><Power size={18} /> EMERGENCY STOP</button>
           </div>
        </section>

        {/* 3. 음성 제어 센터 */}
        <section className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 space-y-5">
          <h3 className="font-semibold text-gray-800 flex items-center gap-2"><Volume2 size={18} /> 음성 제어 센터</h3>
          <div className="bg-indigo-50 rounded-lg p-4 border border-indigo-100">
            <div className="flex justify-between items-center mb-3">
              <span className="text-sm font-bold text-indigo-900 flex items-center gap-1.5"><BrainCircuit size={16}/> 내 목소리 학습</span>
              {isVoiceCloned ? <span className="text-[10px] bg-indigo-200 text-indigo-800 px-2 py-0.5 rounded-full font-bold">학습 완료</span> : <button onClick={trainVoice} className="text-xs bg-white border border-indigo-200 px-2 py-1 rounded text-indigo-700 hover:bg-indigo-100">학습 시작</button>}
            </div>
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => isVoiceCloned && setUseClonedVoice(!useClonedVoice)}>
              <div className={`w-10 h-5 rounded-full relative transition-colors ${useClonedVoice ? 'bg-indigo-600' : 'bg-gray-300'}`}><div className={`w-3 h-3 bg-white rounded-full absolute top-1 transition-all ${useClonedVoice ? 'left-6' : 'left-1'}`} /></div>
              <span className={`text-xs ${useClonedVoice ? 'text-indigo-700 font-medium' : 'text-gray-400'}`}>{useClonedVoice ? '내 목소리로 출력' : '기본 기계음 사용'}</span>
            </div>
          </div>
          <div className="flex gap-2">
            <input type="text" value={ttsText} onChange={(e) => setTtsText(e.target.value)} placeholder="로봇에게 말하기..." className="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500" />
            <button onClick={() => { sendTTS(ttsText); setTtsText(''); }} disabled={!ttsText.trim()} className="bg-gray-900 text-white px-3 rounded-lg hover:bg-black disabled:opacity-50"><Play size={16} fill="white" /></button>
          </div>
          <button onMouseDown={startWalkieTalkie} onMouseUp={stopWalkieTalkie} onMouseLeave={stopWalkieTalkie} className={`w-full border-2 rounded-xl py-4 flex flex-col items-center justify-center gap-2 transition-all select-none ${isRecording ? 'border-red-500 bg-red-50 text-red-600 animate-pulse' : 'border-dashed border-gray-300 text-gray-500 hover:border-indigo-500 hover:text-indigo-600 hover:bg-indigo-50'}`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${isRecording ? 'bg-red-200' : 'bg-gray-100 group-hover:bg-white'}`}><Mic size={24} className={isRecording ? 'animate-bounce' : ''} /></div>
            <span className="text-xs font-medium">{isRecording ? "녹음 중... (떼면 전송)" : "누르고 말하기 (무전기 모드)"}</span>
          </button>
        </section>
      </div>
    </div>
  );
};

const ControlButton = ({ onClick, icon, label }) => (
  <button onMouseDown={onClick} className="w-14 h-14 bg-white border border-gray-200 rounded-xl shadow-sm hover:bg-gray-50 active:bg-gray-100 active:scale-95 transition-all flex flex-col items-center justify-center gap-1 text-gray-700">
    <div className="text-gray-900">{icon}</div>{label && <span className="text-[10px] font-bold text-gray-400">{label}</span>}
  </button>
);

export default Dashboard;