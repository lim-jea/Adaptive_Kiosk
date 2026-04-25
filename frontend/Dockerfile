FROM node:20-alpine AS builder

WORKDIR /app

# 빌드 타임 환경변수 (Vite는 빌드 시점에 번들에 삽입)
ARG VITE_API_URL=http://localhost:5000
ARG VITE_KIOSK_API_KEY
ARG VITE_ENCRYPTION_ENABLED=false
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_KIOSK_API_KEY=$VITE_KIOSK_API_KEY
ENV VITE_ENCRYPTION_ENABLED=$VITE_ENCRYPTION_ENABLED

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# 빌드 결과를 nginx로 서빙
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
