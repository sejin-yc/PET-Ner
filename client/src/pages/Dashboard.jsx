import React, { useState, useEffect } from 'react';
import { useRobot } from '../contexts/RobotContext';
import { useAuth } from '../contexts/AuthContext';
import { Wifi, Battery, Zap, Navigation, Power, Mic, Volume2, Play, BrainCircuit, Repeat, Hand } from 'lucide-react';
import axios from 'axios';
import DashboardSkeleton from '../components/skeletons/DashboardSkeleton'; // 경로 확인 필요
import StreamPanel from '../components/StreamPanel'; // ✅ 우리가 만든 완벽한 영상 패널 가져오기
import ConnectionStatus from '../components/ConnectionStatus';

const Dashboard = () => {
  const { user } = useAuth();
  const { 
    robotStatus, toggleMode, emergencyStop, moveRobot, 
    sendTTS, startWalkieTalkie, stopWalkieTalkie, isRecording,
    trainVoice, stopVoiceTraining, isVoiceTraining, voiceTrainingText,
    isVoiceCloned, useClonedVoice, setUseClonedVoice,
    isRobotLoading
  } = useRobot();

  const [ttsText, setTtsText] = useState("");
  const [ttsLoading, setTtsLoading] = useState(false);
  const [ttsStatus, setTtsStatus] = useState(null); // 'generating' | 'generated' | 'playing' | 'play_error' | 'gen_error'
  const [ttsStatusMessage, setTtsStatusMessage] = useState("");
  const [showSkeleton, setShowSkeleton] = useState(true);
  /** 학습한 사람이 기본 음성 사용 선택 (품질이 마음에 안 들 때) */
  const [useDefaultVoiceForTts, setUseDefaultVoiceForTts] = useState(false);

  /** 내 목소리 토큰으로 TTS 합성 후 로컬 재생. 생성 성공/실패와 재생 성공/실패를 구분해 표시 */
  const playTtsWithVoice = async (text) => {
    if (!user?.id || !text.trim()) return;
    setTtsLoading(true);
    setTtsStatus('generating');
    setTtsStatusMessage('음성 생성 중...');
    try {
      const userId = Number(user.id);
      const params = new URLSearchParams({ userId, text: text.trim() });
      if (useDefaultVoiceForTts) params.set('useDefaultVoice', 'true');
      console.log('[TTS] 요청 userId=', userId, 'useDefaultVoice=', useDefaultVoiceForTts);
      const base = 'http://localhost:8080/user/voice';
      const res = await axios.post(`${base}/tts/speak?${params}`, null, { responseType: 'arraybuffer', validateStatus: () => true });
      if (res.status !== 200) {
        const d = res.data;
        let msg = res.status === 404
          ? '404: 경로 없음(백엔드 재빌드·재시작 필요) 또는 해당 사용자 목소리 없음'
          : '음성 생성 실패';
        if (d != null && (d instanceof ArrayBuffer) && d.byteLength > 0) {
          try {
            const parsed = JSON.parse(new TextDecoder().decode(d));
            msg = parsed.message || parsed.detail || msg;
          } catch (_) {}
        }
        setTtsStatus('gen_error');
        setTtsStatusMessage(`음성 생성 실패: ${msg} (HTTP ${res.status})`);
        return;
      }
      const data = res.data;
      const byteLength = data?.byteLength ?? 0;
      if (!byteLength) {
        setTtsStatus('gen_error');
        setTtsStatusMessage('음성 생성 실패: 서버에서 빈 데이터를 반환했습니다.');
        return;
      }
      setTtsStatus('generated');
      setTtsStatusMessage(`음성 생성 완료 (${(byteLength / 1024).toFixed(1)} KB), 재생 중...`);

      const blob = new Blob([data], { type: 'audio/wav' });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setTtsStatus(null);
        setTtsStatusMessage('');
      };
      audio.onerror = (e) => {
        setTtsStatus('play_error');
        setTtsStatusMessage('재생 실패 (스피커/볼륨 확인 또는 브라우저 음성 허용 확인)');
        URL.revokeObjectURL(url);
      };
      await audio.play();
      setTtsStatus('playing');
    } catch (err) {
      console.error('TTS 요청/재생 실패:', err);
      console.error('response:', err.response?.status, err.response?.data);
      setTtsStatus('gen_error');
      const status = err.response?.status;
      let msg = err.code === 'ERR_NETWORK' ? '서버 연결 실패' : '음성 생성 실패';
      if (err.response?.data != null) {
        const d = err.response.data;
        if (typeof d === 'string') {
          try {
            const parsed = JSON.parse(d);
            msg = parsed.message || parsed.detail || msg;
          } catch {
            msg = d.slice(0, 80);
          }
        } else if (d instanceof ArrayBuffer && d.byteLength) {
          try {
            const raw = new TextDecoder().decode(d);
            const parsed = JSON.parse(raw);
            msg = parsed.message || parsed.detail || msg;
          } catch {
            msg = '서버 오류 (HTTP ' + (status ?? '') + ')';
          }
        } else if (typeof d?.message === 'string') {
          msg = d.message;
        } else if (typeof d?.detail === 'string') {
          msg = d.detail;
        }
        if (status != null) msg = msg + ' (HTTP ' + status + ')';
        setTtsStatusMessage(`음성 생성 실패: ${msg}`);
      } else {
        setTtsStatusMessage(`요청 실패: ${msg}`);
      }
    } finally {
      setTtsLoading(false);
    }
  };

  /** TTS 전송 핸들러: useClonedVoice에 따라 내 목소리 또는 기본 TTS 사용 */
  const handleTTS = async () => {
    if (!ttsText.trim()) return;
    const text = ttsText;
    setTtsText('');
    
    if (useClonedVoice && isVoiceCloned) {
      await playTtsWithVoice(text);
    } else {
      sendTTS(text);
    }
  };
  
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
              <span className="text-sm font-bold text-indigo-900 flex items-center gap-2">
                <BrainCircuit size={16}/> 내 목소리 학습
                {isVoiceCloned && <span className="text-[10px] bg-indigo-200 text-indigo-800 px-2 py-0.5 rounded-full font-bold align-middle">학습 완료</span>}
              </span>
              <button 
                onClick={trainVoice} 
                disabled={isVoiceTraining}
                className="text-xs bg-white border border-indigo-200 px-2 py-1 rounded text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
              >
                {isVoiceTraining ? "녹음 중..." : isVoiceCloned ? "재학습" : "학습 시작"}
              </button>
            </div>
            {isVoiceTraining && (
              <div className="mt-3 p-3 bg-white rounded-lg border border-indigo-200">
                <p className="text-sm font-medium text-indigo-900 mb-2">다음 문구를 읽어주세요:</p>
                <p className="text-base text-gray-800 mb-3 font-semibold">"{voiceTrainingText}"</p>
                <div className="flex items-center gap-2 text-red-600">
                  <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                  <span className="text-xs font-medium">녹음 중...</span>
                </div>
                <button 
                  onClick={stopVoiceTraining}
                  className="mt-2 w-full text-xs bg-red-100 text-red-700 px-3 py-1.5 rounded hover:bg-red-200"
                >
                  녹음 중지
                </button>
              </div>
            )}
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => isVoiceCloned && setUseClonedVoice(!useClonedVoice)}>
              <div className={`w-10 h-5 rounded-full relative transition-colors ${useClonedVoice ? 'bg-indigo-600' : 'bg-gray-300'}`}><div className={`w-3 h-3 bg-white rounded-full absolute top-1 transition-all ${useClonedVoice ? 'left-6' : 'left-1'}`} /></div>
              <span className={`text-xs ${useClonedVoice ? 'text-indigo-700 font-medium' : 'text-gray-400'}`}>{useClonedVoice ? '내 목소리로 출력' : '기본 기계음 사용'}</span>
            </div>
            {isVoiceCloned && (
              <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-600">
                <input
                  type="checkbox"
                  checked={useDefaultVoiceForTts}
                  onChange={(e) => setUseDefaultVoiceForTts(e.target.checked)}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span>기본 음성 사용 (학습 품질이 마음에 안 들 때)</span>
              </label>
            )}
          </div>
          <div className="flex gap-2">
            <input 
              type="text" 
              value={ttsText} 
              onChange={(e) => setTtsText(e.target.value)} 
              placeholder="로봇에게 말하기..." 
              className="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500" 
              onKeyPress={(e) => e.key === 'Enter' && handleTTS()}
            />
            <button 
              onClick={handleTTS} 
              disabled={!ttsText.trim() || ttsLoading} 
              className="bg-gray-900 text-white px-3 rounded-lg hover:bg-black disabled:opacity-50 flex items-center gap-1"
            >
              {ttsLoading ? '...' : <Play size={16} fill="white" />}
            </button>
          </div>
          {/* 음성 상태: 생성 성공/실패 vs 재생 성공/실패 구분 (로컬 재생 확인용) */}
          {ttsStatusMessage && (
            <p className={`text-xs mt-1 px-2 py-1 rounded ${
              ttsStatus === 'gen_error' || ttsStatus === 'play_error'
                ? 'bg-red-100 text-red-700'
                : 'bg-green-100 text-green-700'
            }`}>
              {ttsStatusMessage}
            </p>
          )}
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