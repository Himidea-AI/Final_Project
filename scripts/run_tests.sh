#!/bin/bash
set -e

# Load environment variables if available
if [ -f ../.env ]; then
    export $(grep -v '^#' ../.env | xargs)
fi

echo "🚀 Docker 기반 테스트 스크립트 실행 시작"

# 1. 백엔드와 Redis 서버 띄우기 (DB는 RDS 연결을 사용하므로 생략)
echo "📦 백엔드 및 Redis 컨테이너 시작 중..."
docker compose up -d backend redis

echo "⏳ 컨테이너가 준비될 때까지 잠시 대기 (5초)..."
sleep 5

# 2. 통합 테스트(pytest) 실행
echo "🧪 pytest 통합 테스트 (E2E 및 RAG 등) 실행..."
# 백엔드 컨테이너 내에서 pytest 실행
docker compose exec backend pytest /app/tests/ -v

TEST_RESULT=$?

# 3. 환경 종료 (옵션 - 원하면 주석 처리 가능)
# echo "🧹 테스트 컨테이너 정리 중..."
# docker compose stop backend redis

if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ 모든 테스트가 성공적으로 완료되었습니다!"
else
    echo "❌ 일부 테스트가 실패했습니다. 로그를 확인하세요."
fi

exit $TEST_RESULT
