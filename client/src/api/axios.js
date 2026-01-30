import axios from 'axios';

// 1. Axios 인스턴스 생성
const api = axios.create({
  // Server Connect
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// 2. 요청 인터셉터 (Request Interceptor) 설정
api.interceptors.request.use(
  (config) => {
    // 로컬 스토리지에서 토큰 꺼내기
    const token = localStorage.getItem('token');
    
    // 토큰이 있으면 헤더에 'Bearer 토큰' 형태로 붙이기
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 3. 응답 인터셉터 (Response Interceptor)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && (error.response.status === 401 || error.response.status === 403)) {
      console.error("인증 실패! 토큰이 없거나 만료됨.");
    }
    return Promise.reject(error);
  }
);

export default api;