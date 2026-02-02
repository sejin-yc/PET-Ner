import React, { useEffect, useState } from 'react';
import { useRobot } from '../contexts/RobotContext';
import { Video, VideoOff, Activity, Disc, PlayCircle, StopCircle } from 'lucide-react';

const StreamPanel = () => {
  // 1. 설정
  const STREAM_URL = "http://i14c203.p.ssafy.io:8889/cam"

  // 2. 상태 관리
  const [isStreaming, setIsStreaming] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const { robotStatus } = useRobot();

  useEffect(() => {
    if (robotStatus?.isRecording) {
      setIsRecording(true);
    } else {
      setIsRecording(false);
    }
  }, [robotStatus]);

  const toggleStream = () => {
    setIsStreaming(!isStreaming);
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
            ROBOT CAM {isStreaming ? "(LIVE)" : "(OFF)"}
          </h3>
        </div>

        <div className='flex items-center gap-3'>
          {isRecording && (
            <span className='text-xs font-bold text-red-500 flex items-center gap-1 bg-red-900/20 px-2 py-1 rounded border border-red-900/50 animate-pulse'>
              <Disc size={12} fill='currentColor' /> REC (Pet Detected)
            </span>
          )}

          <button
            onClick={toggleStream}
            className={`text-xs px-3 py-1.5 rounded-full font-bold flex items-center gap-1.5 transition-all shadow-lg active:scale-95 ${
              isStreaming
                ? "bg-red-600 hover:bg-red-700 text-white border border-red-500"
                : "bg-green-600 hover:bg-green-700 text-white border border-green500"
            }`}
          >
            {isStreaming ? (
              <> <StopCircle size={14} /> 영상 종료 </>
            ) : (
              <> <PlayCircle size={14} /> 영상 시작 </>
            )}
          </button>
        </div>
      </div>

      <div className='relative w-full flex-1 bg-gray-900 rounded-lg overflow-hidden border border-gray-800/50 group'>
          {isStreaming ? (
            <>
              <iframe
                src={STREAM_URL}
                className='w-full h-full object-contain border-none'
                allow='autoplay; fullscreen'
                title='Robot Camera Stream'
              />

              {isRecording && (
                <div className='absolute inset-0 border-4 border-red-500/50 animate-pulse pointer-events-none rounded-lg'></div>
              )}
            </>
          ): (
            <div className='absolute inset-0 flex flex-col items-center justify-center text-gray-500 bg-gray-950'>
              <div className='w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-4 shadow-inner'>
                <VideoOff size={32} className='opacity-50' />
              </div>
              <p className='text-sm font-medium'>카메라 연결이 종료되었습니다.</p>
              <p className='text-xs text-gray-600 mt-1'>배터리 절약을 위해 대기 모드로 전환</p>
              <button
                onClick={toggleStream}
                className='mt-6 px-6 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg transition-colors border border-gray-700'
              >
                다시 연결하기
              </button>
            </div>
          )}
      </div>
    </div>
  );
};

export default StreamPanel;