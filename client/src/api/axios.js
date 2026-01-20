import axios from 'axios';

// 1. Axios 인스턴스 생성
const api = axios.create({
  baseURL: 'https://i14c203.p.ssafy.io/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// 2. 요청 인터셉터 (Request Interceptor) 설정
// 👉 요청이 서버로 날아가기 직전에 낚아채서 작업을 수행함
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

// 3. 응답 인터셉터 (Response Interceptor) - 선택 사항
// 👉 토큰이 만료되어 401 에러가 오면 자동으로 로그아웃 처리 등을 할 수 있음
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && (error.response.status === 401 || error.response.status === 403)) {
      // 인증 에러 발생 시 처리 (예: 로그인 페이지로 튕기기)
      // window.location.href = '/login'; // 필요 시 주석 해제
      console.error("인증 실패! 토큰이 없거나 만료됨.");
    }
    return Promise.reject(error);
  }
);

export default api;