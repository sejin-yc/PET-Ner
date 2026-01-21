import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom'; // ✅ BrowserRouter(Router) 제거됨

// Providers
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { RobotProvider } from '@/contexts/RobotContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { CatProvider } from '@/contexts/PetContext';

// Components
import Layout from '@/components/Layout';

// Pages
import Dashboard from '@/pages/Dashboard';
import Login from '@/pages/Login';
import CatsPage from '@/pages/CatsPage';
import GalleryPage from '@/pages/GalleryPage';
import LogsPage from '@/pages/LogsPage';
import NotificationsPage from '@/pages/NotificationsPage';
import SettingsPage from '@/pages/SettingsPage';

// 보호된 라우트 (로그인 안 하면 튕겨내기)
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="h-screen flex items-center justify-center">로딩 중...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      
      {/* 대시보드 */}
      <Route path="/" element={
        <ProtectedRoute>
          <Layout>
            <Dashboard />
          </Layout>
        </ProtectedRoute>
      } />

      {/* 고양이 관리 */}
      <Route path="/cats" element={
        <ProtectedRoute>
          <Layout>
            <CatsPage />
          </Layout>
        </ProtectedRoute>
      } />

      {/* 갤러리 */}
      <Route path="/gallery" element={
        <ProtectedRoute>
          <Layout>
            <GalleryPage />
          </Layout>
        </ProtectedRoute>
      } />

      {/* 로그 리포트 */}
      <Route path="/logs" element={
        <ProtectedRoute>
          <Layout>
            <LogsPage />
          </Layout>
        </ProtectedRoute>
      } />

      {/* 알림 센터 */}
      <Route path="/notifications" element={
        <ProtectedRoute>
          <Layout>
            <NotificationsPage />
          </Layout>
        </ProtectedRoute>
      } />

      {/* 계정 설정 */}
      <Route path="/settings" element={
        <ProtectedRoute>
          <Layout>
            <SettingsPage />
          </Layout>
        </ProtectedRoute>
      } />
    </Routes>
  );
};

const App = () => {
  return (
    // ✅ Router와 Toaster는 main.jsx에 있으므로 여기서는 제거했습니다.
    <AuthProvider> 
      <NotificationProvider>
        <RobotProvider>
          <CatProvider>
            
            {/* Router 제거됨 */}
            <div className="min-h-screen bg-gray-50 text-gray-900 font-sans antialiased">
              <AppRoutes />
            </div>
            {/* Router 제거됨 */}

          </CatProvider>
        </RobotProvider>
      </NotificationProvider>
    </AuthProvider>
  );
};

export default App;