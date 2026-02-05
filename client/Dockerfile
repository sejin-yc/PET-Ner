# 1. 빌드 단계 (Node.js)
FROM node:20 as builder
WORKDIR /app

# 캐시 문제 방지를 위해 clean install 권장
COPY package*.json ./
RUN npm install && npm install mqtt

COPY . .
RUN npm run build

# 2. 실행 단계 (Nginx)
FROM nginx:alpine

# 빌드된 리액트 결과물을 Nginx로 복사
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx 설정 파일이 있다면 복사 (없으면 기본값 사용되므로 생략 가능)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
