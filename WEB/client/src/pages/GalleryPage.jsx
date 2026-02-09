import React, { useState } from 'react'; // useState 추가
import { useRobot } from '../contexts/RobotContext';
import { Film, Play, Clock, Cat, Video, Trash2, PlusCircle, X } from 'lucide-react'; // X 아이콘 추가

const GalleryPage = () => {
  const { videos, deleteVideo, addTestVideo } = useRobot();
  
  // 🎥 [추가] 현재 선택된(재생 중인) 비디오 상태
  const [selectedVideo, setSelectedVideo] = useState(null);

  // 🖱️ 썸네일 클릭 시 실행되는 함수
  const handleVideoClick = (video) => {
    // 만약 video 객체에 url이 없다면 백엔드 주소와 파일명을 조합해야 할 수도 있습니다.
    // 예: const fullUrl = `https://i14c203.p.ssafy.io/videos/${video.fileName}`;
    setSelectedVideo(video); 
  };

  // ❌ 모달 닫기 함수
  const closeVideo = () => {
    setSelectedVideo(null);
  };

  return (
    <div className="space-y-6">
      {/* 상단 헤더 */}
      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Film size={24} className="text-indigo-600" />
            냥이들 ♡✧。
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            반려동물이 감지된 순간(최대 15초)을 자동으로 저장한 영상입니다.
          </p>
        </div>

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
              
              {/* 1. 썸네일 영역 (클릭 이벤트 추가) */}
              <div 
                onClick={() => handleVideoClick(video)} // 👈 [추가] 클릭 시 재생
                className="aspect-video bg-black relative flex items-center justify-center cursor-pointer overflow-hidden group-video"
              >
                {/* 썸네일이 있으면 보여주고, 없으면 까만 화면 */}
                {video.thumbnailUrl ? (
                  <img src={video.thumbnailUrl} alt="thumbnail" className="w-full h-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-500" />
                ) : (
                   <div className="w-full h-full bg-gray-900 flex items-center justify-center">
                      <Video size={48} className="text-gray-700" />
                   </div>
                )}

                {/* 플레이 버튼 오버레이 */}
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
                  <div className="w-12 h-12 bg-white/20 backdrop-blur rounded-full flex items-center justify-center border border-white/50 text-white hover:bg-white/30 transition-colors">
                    <Play size={20} fill="white" />
                  </div>
                </div>

                <div className="absolute top-3 right-3 bg-white/10 backdrop-blur border border-white/20 text-white text-[10px] px-2 py-1 rounded flex items-center gap-1">
                  <Cat size={10} /> 고양이 감지
                </div>

                <div className="absolute bottom-3 right-3 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded font-mono">
                  {video.duration || '00:05'}
                </div>
              </div>

              {/* 2. 영상 정보 영역 */}
              <div className="p-4">
                <div className="flex justify-between items-center mb-3">
                  <div className="font-bold text-gray-900">{video.catName || '감지된 고양이'}</div>
                  <span className={`text-xs px-2 py-1 rounded border ${
                    video.behavior === '수면' ? 'bg-indigo-50 text-indigo-700 border-indigo-100' : 
                    video.behavior === '그루밍' ? 'bg-pink-50 text-pink-700 border-pink-100' :
                    'bg-green-50 text-green-700 border-green-100'
                  }`}>
                    {video.behavior || '활동 중'}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs text-gray-500 border-t border-gray-100 pt-3">
                  <div className="flex items-center gap-2">
                    <Clock size={12} />
                    <span>{new Date(video.timestamp).toLocaleString()}</span>
                  </div>
                  <button 
                    onClick={(e) => { e.stopPropagation(); deleteVideo(video.id); }}
                    className="text-gray-400 hover:text-red-500 transition-colors p-1"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 🎥 [추가] 비디오 재생 모달 (Popup) */}
      {selectedVideo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="relative w-full max-w-4xl bg-black rounded-xl overflow-hidden shadow-2xl border border-gray-800">
            
            {/* 닫기 버튼 */}
            <button 
              onClick={closeVideo}
              className="absolute top-4 right-4 z-10 p-2 bg-black/50 hover:bg-red-600/80 text-white rounded-full transition-colors backdrop-blur-md"
            >
              <X size={24} />
            </button>

            {/* 실제 비디오 플레이어 */}
            <video 
              controls 
              autoPlay 
              className="w-full h-auto max-h-[80vh] aspect-video object-contain"
              // 중요: video 객체 안에 실제 mp4 주소가 있어야 함 (예: video.url)
              // 만약 주소가 없다면 Nginx 주소를 직접 넣어줘야 함: 
              // src={`https://i14c203.p.ssafy.io/videos/${selectedVideo.fileName}`}
              src={selectedVideo.url} 
            >
              브라우저가 비디오 재생을 지원하지 않습니다.
            </video>

            {/* 하단 정보 바 */}
            <div className="bg-gray-900 p-4 flex justify-between items-center text-white">
               <div>
                 <h3 className="font-bold text-lg">{selectedVideo.catName || '감지된 고양이'}</h3>
                 <p className="text-xs text-gray-400">{new Date(selectedVideo.timestamp).toLocaleString()}</p>
               </div>
               <span className="text-xs px-2 py-1 bg-gray-700 rounded text-gray-300">
                 {selectedVideo.behavior || '녹화된 영상'}
               </span>
            </div>
          </div>
          
          {/* 배경 클릭 시 닫기 */}
          <div className="absolute inset-0 -z-10" onClick={closeVideo}></div>
        </div>
      )}
    </div>
  );
};

export default GalleryPage;