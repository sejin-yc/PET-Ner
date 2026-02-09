import React, { useState } from 'react';
import { VideoOff, Video } from 'lucide-react';

const CameraView = ({ streamUrl }) => {
  const [hasError, setHasError] = useState(false);

  // 스트림 URL이 바뀌면 에러 상태 초기화 (다시 시도)
  React.useEffect(() => {
    setHasError(false);
  }, [streamUrl]);

  return (
    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col w-full h-full">
      {/* 헤더 영역 */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                <Video size={20} />
            </div>
            <h3 className="font-bold text-gray-800">실시간 카메라</h3>
        </div>
        
        {/* 라이브 표시기 */}
        {streamUrl && !hasError && (
          <span className="bg-red-500 text-white px-2 py-0.5 rounded text-xs font-bold animate-pulse">
            LIVE
          </span>
        )}
      </div>
      
      {/* 비디오 화면 영역 */}
      <div className="w-full aspect-video bg-black rounded-lg overflow-hidden flex justify-center items-center relative group">
        {streamUrl && !hasError ? (
          // ✅ MJPEG 스트림 (성공 시)
          <img 
            src={streamUrl} 
            alt="Robot Live Stream" 
            className="w-full h-full object-cover"
            onError={() => setHasError(true)} // 에러 나면 상태 변경
          />
        ) : (
          // ❌ 연결 끊김 또는 에러 시
          <div className="flex flex-col items-center text-gray-500 gap-3">
            <VideoOff size={48} />
            <p className="text-sm font-medium">카메라 신호 없음</p>
            {hasError && <p className="text-xs text-red-400">연결이 끊어졌습니다.</p>}
          </div>
        )}
      </div>
    </div>
  );
};

export default CameraView;