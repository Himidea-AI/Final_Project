# GEMINI.md

> Gemini CLI 전용 추가 지시. 공통 규칙은 `AGENTS.md`를 참조합니다.

## 필수 참조

- 작업 전 반드시 `AGENTS.md`를 읽고 팀원별 담당 영역을 확인하세요.
- 현재 작업자의 담당 디렉토리 외 파일을 수정하지 마세요.

## 작업 방식

- 코드 수정 전 관련 파일을 먼저 읽어서 기존 패턴을 파악하세요.
- Python 코드 작성 후 `ruff check --fix` 및 `ruff format`을 실행하세요.
- 프론트엔드 코드 작성 후 `cd frontend && npx prettier --write .`을 실행하세요.

## 커밋

- 사용자가 요청할 때만 커밋하세요.
- 커밋 메시지는 변경 내용을 명확히 설명하세요.

## 프로젝트 실행

```bash
# 백엔드 개발서버
cd backend && uvicorn src.main:app --reload

# 프론트엔드 개발서버
cd frontend && npm run dev

# 전체 서비스 (Docker)
docker compose up --build
```
