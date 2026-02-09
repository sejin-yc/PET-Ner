import React from 'react';
import { useNotifications } from '@/contexts/NotificationContext';
import { Bell, Check, Trash2, Info, AlertTriangle, Zap, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom'; // ✅ 페이지 이동을 위해 필수

const NotificationsPage = () => {
  const { 
    notifications, 
    markAllAsRead, 
    clearAllNotifications, 
    removeNotification, 
    markAsRead, 
    addTestNotification 
  } = useNotifications();
  
  const navigate = useNavigate();

  // ✅ 알림 클릭 핸들러 (읽음 처리 + 페이지 이동)
  const handleNotificationClick = (noti) => {
    markAsRead(noti.id); // 1. 읽음 처리
    
    if (noti.link) {
      navigate(noti.link); // 2. 링크가 있으면 해당 페이지로 이동
    }
  };

  // 알림 타입별 아이콘 선택
  const getIcon = (type) => {
    switch (type) {
      case 'alert': return <AlertTriangle className="text-red-500" />;
      case 'robot': return <Zap className="text-yellow-500" />;
      case 'info': return <Info className="text-blue-500" />;
      default: return <Bell className="text-gray-500" />;
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 pb-20">
      {/* 상단 헤더 */}
      <div className="flex justify-between items-end mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">알림 센터</h1>
          <p className="text-sm text-gray-500 mt-1">로봇과 시스템의 주요 이벤트를 확인하세요.</p>
        </div>
        
        {/* ✅ 테스트용 버튼: 누르면 샘플 알림 생성 */}
        <button 
          onClick={addTestNotification} 
          className="px-3 py-1.5 text-xs bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100 font-medium transition-colors border border-indigo-100"
        >
           + 테스트 알림 생성
        </button>
      </div>

      {/* 알림 리스트 컨테이너 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        
        {/* 리스트 헤더 (컨트롤 버튼) */}
        <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
          <span className="font-semibold text-gray-700">전체 알림 ({notifications.length})</span>
          <div className="flex gap-2">
            <button 
              onClick={markAllAsRead} 
              className="text-xs flex items-center gap-1 text-gray-600 hover:text-indigo-600 px-2 py-1 rounded hover:bg-white transition-colors"
            >
              <Check size={14} /> 모두 읽음
            </button>
            {/* ✅ 전체 삭제 버튼 */}
            <button 
              onClick={clearAllNotifications} 
              className="text-xs flex items-center gap-1 text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-white transition-colors"
            >
              <Trash2 size={14} /> 전체 삭제
            </button>
          </div>
        </div>

        {/* 알림 목록 */}
        <div className="divide-y divide-gray-100">
          {notifications.length === 0 ? (
            <div className="p-12 text-center text-gray-400 flex flex-col items-center">
              <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-3">
                <Bell size={24} className="opacity-30" />
              </div>
              <p>새로운 알림이 없습니다.</p>
            </div>
          ) : (
            notifications.map((noti) => (
              <div 
                key={noti.id} 
                onClick={() => handleNotificationClick(noti)}
                className={`p-4 hover:bg-gray-50 transition-colors flex gap-4 items-start cursor-pointer group relative ${!noti.isRead ? 'bg-indigo-50/40' : ''}`}
              >
                {/* 왼쪽 아이콘 */}
                <div className={`mt-1 p-2 rounded-full border shadow-sm flex-shrink-0 ${!noti.isRead ? 'bg-white border-indigo-100' : 'bg-gray-50 border-gray-200'}`}>
                  {getIcon(noti.type)}
                </div>

                {/* 내용 */}
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-start">
                    <h3 className={`font-medium text-sm truncate pr-6 ${!noti.isRead ? 'text-gray-900' : 'text-gray-500'}`}>
                      {noti.title}
                      {/* 링크가 있으면 아이콘 표시 */}
                      {noti.link && <ExternalLink size={12} className="inline ml-1 text-gray-400" />}
                    </h3>
                    <span className="text-xs text-gray-400 whitespace-nowrap ml-2 flex-shrink-0">
                      {new Date(noti.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                    </span>
                  </div>
                  <p className={`text-sm mt-1 line-clamp-2 ${!noti.isRead ? 'text-gray-600' : 'text-gray-400'}`}>
                    {noti.message}
                  </p>
                </div>
                
                {/* 개별 삭제 버튼 (우측 상단, 호버 시 표시) */}
                <button 
                  onClick={(e) => { 
                    e.stopPropagation(); // 부모의 onClick(페이지 이동) 막기
                    removeNotification(noti.id); 
                  }}
                  className="absolute right-2 top-2 p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100 transition-all"
                  title="알림 삭제"
                >
                  <Trash2 size={14} />
                </button>

                {/* 읽지 않음 표시 점 */}
                {!noti.isRead && (
                  <div className="absolute left-2 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-indigo-500 rounded-full" />
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default NotificationsPage;