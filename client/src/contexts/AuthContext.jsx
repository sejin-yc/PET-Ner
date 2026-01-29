import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/axios'; // 토큰이 필요한 요청용
import axios from 'axios';      // ✅ 토큰 없는 순수 요청용 (새로 추가)
import { toast } from 'sonner';

const AuthContext = createContext();

// ✅ 백엔드 주소 직접 정의 (순수 axios용)
// const BASE_URL = 'https://i14c203.p.ssafy.io/api';  // 배포용 (주석 처리)
const BASE_URL = 'http://localhost:8080';              // 로컬용 (백엔드에 /api prefix 없음)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // 1. 초기 로드 (새로고침 시 로그인 유지)
  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    const storedToken = localStorage.getItem('token');
    if (storedUser && storedToken) {
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  // 2. 로그인
  const login = async (email, password) => {
    try {
      // ✅ api 대신 axios 사용 (옛날 토큰 간섭 방지)
      const response = await axios.post(`${BASE_URL}/user/login`, { email, password });
      
      const { token: rawToken, user: receivedUser } = response.data;
      // const rawToken = response.data.token;
      const pureToken = rawToken.startsWith('Bearer ') ? rawToken.slice(7) : rawToken;
      
      // 토큰 저장
      localStorage.setItem('token', pureToken);
      localStorage.setItem('user', JSON.stringify(receivedUser));
      setUser(receivedUser);
      
      toast.success(`${receivedUser.name}님 환영합니다!`);
      return true;
    } catch (error) {
      console.error("로그인 에러:", error);
      toast.error("로그인 실패: 이메일이나 비밀번호를 확인하세요.");
      return false;
    }
  };

  // 3. 회원가입 (추가됨)
  const register = async (userData) => {
    try {
      // ✅ 여기도 순수 axios 사용! 토큰 없이 요청 보냄
      await axios.post(`${BASE_URL}/user`, userData);
      
      toast.success("회원가입 성공! 로그인해주세요.");
      return true;
    } catch (error) {
      console.error("회원가입 에러:", error);
      toast.error("회원가입 실패: 서버 연결을 확인하세요.");
      return false;
    }
  };

  // 4. 로그아웃
  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
    toast.info("로그아웃 되었습니다.");
  };

  // 프로필 수정 등은 기존 api 객체 사용 (토큰 필요하니까)
  const updateProfile = async (newName) => {
    try {
      await api.put(`/user/${user.id}/profile`, { name: newName });
      const updatedUser = { ...user, name: newName };
      setUser(updatedUser);
      localStorage.setItem('user', JSON.stringify(updatedUser));
      toast.success("프로필 이름이 변경되었습니다.");
      return true;
    } catch (error) {
      toast.error("프로필 수정 실패");
      return false;
    }
  };

  const changePassword = async (currentPassword, newPassword) => {
    try {
      await api.post('/user/verify-password', { userId: user.id, password: currentPassword });
      await api.put(`/user/${user.id}/password`, { newPassword });
      toast.success("비밀번호 변경 완료. 다시 로그인해주세요.");
      logout();
      return true;
    } catch (error) {
      toast.error("비밀번호 변경 실패");
      return false;
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading, updateProfile, changePassword }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);