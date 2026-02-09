import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Cat, Image, FileText, Bell, User, Bot, LogOut } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useNotifications } from '@/contexts/NotificationContext';

const Layout = ({ children }) => {
  const location = useLocation();
  const { logout, user } = useAuth();
  const { unreadCount } = useNotifications();

  // 메뉴 목록 정의
  const menuItems = [
    { path: '/', label: '대시보드', icon: <LayoutDashboard size={18} /> },
    { path: '/cats', label: '고양이', icon: <Cat size={18} /> },
    { path: '/gallery', label: '갤러리', icon: <Image size={18} /> },
    { path: '/logs', label: '로그', icon: <FileText size={18} /> },
    { path: '/notifications', label: '알림', icon: <Bell size={18} />, badge: unreadCount },
    { path: '/settings', label: '계정', icon: <User size={18} /> },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 1. 최상단 헤더 */}
      <header className="bg-white border-b border-gray-200 h-16 flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 p-2 rounded-lg text-white">
            <Bot size={24} />
          </div>
          <div>
            <h1 className="font-bold text-lg text-gray-900 leading-none">펫케어 로봇 시스템</h1>
            <span className="text-xs text-gray-500">Pet Care Robot Management</span>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
             <User size={16} />
             <span>{user?.name || '관리자'}</span>
          </div>
          <button onClick={logout} className="text-gray-400 hover:text-red-500 transition-colors">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {/* 2. 네비게이션 탭 메뉴 */}
      <nav className="bg-white border-b border-gray-200 px-6 shrink-0">
        <div className="flex gap-6 overflow-x-auto">
          {menuItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors whitespace-nowrap
                  ${isActive 
                    ? 'border-gray-900 text-gray-900' 
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
              >
                {item.icon}
                {item.label}
                {item.badge > 0 && (
                  <span className="bg-red-500 text-white text-[10px] px-1.5 rounded-full">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* 3. 실제 페이지 내용이 들어가는 곳 */}
      <main className="flex-1 p-6 overflow-auto max-w-[1600px] mx-auto w-full">
        {children}
      </main>
    </div>
  );
};

export default Layout;