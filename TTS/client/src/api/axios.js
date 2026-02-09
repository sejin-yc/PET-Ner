import axios from 'axios';

// 1. Axios 인스턴스 생성
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// 2. 요청 인터셉터 (Request Interceptor) 설정
api.interceptors.request.use(
  (config) => {
    // FormData 요청 시 Content-Type 제거 → 브라우저가 multipart/form-data; boundary=... 자동 설정
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    // 로컬 스토리지에서 토큰 꺼내기
    const token = localStorage.getItem('token');
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