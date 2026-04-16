#!/bin/bash
set -e

echo "🚀 애플리케이션 프로덕션 배포 스크립트 시작..."

# 1. 최신 코드 가져오기 (필요시 활성화)
# git pull origin dev

# 2. 기존 컨테이너 및 미사용 리소스 정리
echo "🧹 기존 Docker 리소스 정리 중..."
docker system prune -f

# 3. docker-compose.prod.yml 기반으로 컨테이너 빌드 및 재시작
echo "📦 컨테이너 빌드 및 프로덕션 환경 시작 중..."
docker compose -f docker-compose.prod.yml up --build -d

# 4. 배포 후 상태 확인
echo "⏳ 컨테이너 상태 대기 (10초)..."
sleep 10
docker ps

echo "✅ 배포가 성공적으로 완료되었습니다!"
