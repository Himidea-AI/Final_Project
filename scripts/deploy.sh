#!/bin/bash
# 수동 배포 스크립트 (긴급 시 서버에서 직접 실행용)
# CI/CD는 GitHub Actions (.github/workflows/deploy.yml)가 자동으로 처리합니다.
# 사용법:
#   ./scripts/deploy.sh          → 전체 재빌드
#   ./scripts/deploy.sh frontend → Frontend만 재빌드
#   ./scripts/deploy.sh backend  → Backend만 재빌드
set -e

TARGET=${1:-"all"}  # 인자 없으면 전체 빌드

echo "🚀 수동 배포 시작 (대상: $TARGET)..."

# 최신 코드 가져오기
echo "📥 최신 코드 가져오기 (dev 브랜치)..."
git fetch origin dev
git reset --hard origin/dev

# 미사용 Docker 리소스 정리
echo "🧹 Docker 리소스 정리..."
docker system prune -f --volumes=false

# 빌드 및 재시작
echo "📦 빌드 및 재시작..."
if [ "$TARGET" = "frontend" ]; then
  docker compose -f docker-compose.prod.yml up --build -d frontend
elif [ "$TARGET" = "backend" ]; then
  docker compose -f docker-compose.prod.yml up --build -d backend
else
  docker compose -f docker-compose.prod.yml up --build -d
fi

# 배포 후 상태 확인
echo "⏳ 기동 대기 (20초)..."
sleep 20
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 헬스체크
echo "🏥 Backend 헬스체크..."
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
  echo "✅ Backend 정상!"
else
  echo "❌ Backend 응답 없음. 로그:"
  docker logs mapo_backend_prod --tail 30
  exit 1
fi

echo "✅ 수동 배포 완료! $(date '+%Y-%m-%d %H:%M:%S')"
