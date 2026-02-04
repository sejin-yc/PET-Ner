import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';
import api from '../api/axios'; // ✅ 우리가 만든 api 객체 사용
import { toast } from 'sonner';

const CatContext = createContext();

export const CatProvider = ({ children }) => {
  const { user } = useAuth();
  const [cats, setCats] = useState([]);

  // 1. 유저 변경 시 목록 불러오기
  useEffect(() => {
    if (user && user.id) {
      fetchCats(user.id);
    } else {
      setCats([]);
    }
  }, [user]);

  const fetchCats = async (userId) => {
    try {
      // ⚠️ api 객체에는 이미 '/api'가 포함되어 있으므로 '/cats'만 씁니다.
      const res = await api.get(`/cats?userId=${userId}`);
      setCats(res.data);
    } catch (err) {
      console.error("고양이 목록 불러오기 실패:", err);
    }
  };

  // 2. 고양이 등록
  const addCat = async (catData) => {
    if (!user) return;

    try {
      // 서버로 데이터 전송 (userId 포함)
      await api.post('/cats', {
        ...catData,
        userId: user.id
      });
      
      fetchCats(user.id); // 목록 갱신
      toast.success('새 고양이가 등록되었습니다!');
    } catch (err) {
      console.error("고양이 등록 실패:", err);
      toast.error('등록에 실패했습니다.');
    }
  };

  // 3. 고양이 삭제
  const deleteCat = async (id) => {
    if (!confirm('정말 삭제하시겠습니까?')) return;

    try {
      // ✅ api.delete 사용 (토큰 자동 첨부)
      await api.delete(`/cats/${id}`);
      
      setCats(prev => prev.filter(cat => cat.id !== id));
      toast.info('삭제되었습니다.');
    } catch (err) {
      console.error("삭제 실패:", err);
      toast.error("삭제 중 오류가 발생했습니다.");
    }
  };

  // (AI 연동용 - 추후 사용)
  const updateCatStatus = (id, status) => {
    setCats(prev => prev.map(cat => 
      cat.id === id ? { ...cat, ...status } : cat
    ));
  };

  return (
    <CatContext.Provider value={{ cats, addCat, deleteCat, updateCatStatus }}>
      {children}
    </CatContext.Provider>
  );
};

export const useCats = () => useContext(CatContext);