import React, { createContext, useContext, useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useAuth } from './AuthContext';

const NotificationContext = createContext();

export const NotificationProvider = ({ children }) => {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!user || !user.id) {
      setNotifications([]);
      return;
    }

    const storageKey = `notifications_${user.id}`;
    const saved = localStorage.getItem(storageKey);

    if (saved) {
      setNotifications(JSON.parse(saved));
    } else {
      setNotifications([]);
    }
  }, [user]);

    useEffect(() => {
      if (!user || !user.id) return;

      const storageKey = `notifications_${user.id}`;
      localStorage.setItem(storageKey, JSON.stringify(notifications));

      const count = notifications.filter(n => !n.isRead).length;
      setUnreadCount(count);
    }, [notifications, user]);

  // 알림 추가 함수
  const addNotification = ({ type, title, message, link = null }) => {
    const newNoti = {
      id: Date.now(),
      timestamp: new Date(),
      isRead: false,
      type, title, message, link // 링크 정보 저장
    };

    setNotifications(prev => [newNoti, ...prev]);
    
    // 토스트 팝업 (화면 상단 알림)
    toast(title, { 
      description: message,
      action: link ? { label: '이동', onClick: () => window.location.href = link } : null
    });
  };

  // 테스트용 알림 생성기
  const addTestNotification = () => {
    addNotification({
      type: 'alert',
      title: '⚠️ 테스트 경고',
      message: '이 알림을 누르면 로그 페이지로 이동합니다.',
      link: '/logs' // ✅ 이동 테스트용 링크
    });
  };

  const markAsRead = (id) => {
    setNotifications(prev => prev.map(n => 
      n.id === id ? { ...n, isRead: true } : n
    ));
  };

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, isRead: true })));
  };

  const removeNotification = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const clearAllNotifications = () => {
    setNotifications([]);
    localStorage.removeItem('notifications'); // 저장소에서도 삭제
    toast.info("모든 알림이 삭제되었습니다.");
  };

  return (
    <NotificationContext.Provider value={{ 
      notifications, unreadCount, 
      addNotification, addTestNotification,
      markAsRead, markAllAsRead, removeNotification, clearAllNotifications 
    }}>
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = () => useContext(NotificationContext);