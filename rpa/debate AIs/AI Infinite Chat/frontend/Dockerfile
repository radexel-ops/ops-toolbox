# frontend/Dockerfile

# 1단계: 빌드 (Node.js)
FROM node:18-alpine as build

WORKDIR /app

# 의존성 먼저 복사 (캐싱 활용)
COPY package.json package-lock.json ./
RUN npm ci

# 소스 코드 복사 및 빌드
COPY . .

# 환경변수 설정 (빌드 시점에 필요)
ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_WS_URL=${VITE_WS_URL}

RUN npm run build

# 2단계: 실행 (Nginx)
FROM nginx:alpine

# 빌드된 결과물을 Nginx가 서빙할 경로로 복사
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx 설정 파일 복사
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 포트 노출
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
