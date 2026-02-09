import React from 'react';
import { useRobot } from '@/contexts/RobotContext';
import { Film, Play, Clock, Cat, Video, Trash2, PlusCircle } from 'lucide-react';

const GalleryPage = () => {
  // Context에서 실제 데이터와 함수 가져오기
  const { videos, deleteVideo, addTestVideo } = useRobot();

  return (
    <div className="space-y-6">
      {/* 상단 헤더 */}
      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Film size={24} className="text-indigo-600" />
            영상 갤러리
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            반려동물이 감지된 순간(최대 15초)을 자동으로 저장한 영상입니다.
          </p>
        </div>

        {/* 🧪 [테스트용] 샘플 데이터 생성 버튼 */}
        <button 
          onClick={addTestVideo}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors text-sm font-bold"
        >
          <PlusCircle size={16} />
          테스트 영상 생성 (DB저장)
        </button>
      </div>

      {/* 영상 그리드 리스트 */}
      {!videos || videos.length === 0 ? (
        <div className="text-center py-20 bg-gray-50 rounded-lg border border-dashed border-gray-300 text-gray-400">
          <Video size={48} className="mx-auto mb-4 opacity-20" />
          <p>저장된 영상이 없습니다.</p>
          <p className="text-xs mt-2">상단 '테스트 영상 생성' 버튼을 눌러보세요.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {videos.map((video) => (
            <div key={video.id} className="bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition-all group relative">
              
              {/* 1. 썸네일 영역 (검은 배경) */}
              <div className="aspect-video bg-black relative flex items-center justify-center cursor-pointer overflow-hidden group-video">
                {video.thumbnailUrl ? (
                  <img src={video.thumbnailUrl} alt="thumbnail" className="w-full h-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-500" />
                ) : (
                  <Video size={48} className="text-gray-700" />
                )}

                {/* 플레이 버튼 */}
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
                  <div className="w-12 h-12 bg-white/20 backdrop-blur rounded-full flex items-center justify-center border border-white/50 text-white">
                    <Play size={20} fill="white" />
                  </div>
                </div>

                {/* 우측 상단 뱃지 */}
                <div className="absolute top-3 right-3 bg-white/10 backdrop-blur border border-white/20 text-white text-[10px] px-2 py-1 rounded flex items-center gap-1">
                  <Cat size={10} /> 고양이 감지
                </div>

                {/* 좌측 하단 시간 */}
                <div className="absolute bottom-3 right-3 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded font-mono">
                  {video.duration}
                </div>
              </div>

              {/* 2. 영상 정보 영역 */}
              <div className="p-4">
                <div className="flex justify-between items-center mb-3">
                  <div className="font-bold text-gray-900">{video.catName || '알 수 없음'}</div>
                  
                  {/* 행동 태그 */}
                  <span className={`text-xs px-2 py-1 rounded border ${
                    video.behavior === '수면' ? 'bg-indigo-50 text-indigo-700 border-indigo-100' : 
                    video.behavior === '그루밍' ? 'bg-pink-50 text-pink-700 border-pink-100' :
                    'bg-green-50 text-green-700 border-green-100'
                  }`}>
                    {video.behavior}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs text-gray-500 border-t border-gray-100 pt-3">
                  <div className="flex items-center gap-2">
                    <Clock size={12} />
                    <span>{new Date(video.timestamp).toLocaleString()}</span>
                  </div>
                  
                  {/* 🗑️ 삭제 버튼 */}
                  <button 
                    onClick={(e) => { e.stopPropagation(); deleteVideo(video.id); }}
                    className="text-gray-400 hover:text-red-500 transition-colors p-1"
                    title="영상 삭제"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default GalleryPage;