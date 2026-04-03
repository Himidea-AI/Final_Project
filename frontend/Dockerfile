# === Build stage ===
# Node 20에서 React+TypeScript 빌드 → dist/ 폴더에 정적 파일 생성
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# === Production stage ===
# Nginx에서 빌드된 정적 파일 서빙 + /api 프록시를 backend로 전달
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
