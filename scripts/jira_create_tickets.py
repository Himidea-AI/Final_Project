import requests
import json
import os
from requests.auth import HTTPBasicAuth

URL = "https://bat981120.atlassian.net"
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

# 에픽(IM3-91) 하위에 "작업(Task)" 타입으로 생성 (에픽 링크 = parent)
TASK_TYPE_ID = "10006"  # Task (프로젝트 전용)

tickets = [
    # 3주차
    {
        "summary": "IM3-C2: AWS RDS PostgreSQL 세팅 + pgvector 확장",
        "description": "- RDS PostgreSQL 16.6 생성 (db.t3.micro, 단일 DB)\n- pgvector v0.8.0 확장 활성화\n- Alembic 마이그레이션 4버전 실행\n- 보안그룹 5432 팀원 IP 등록\n- .env RDS 주소로 전환\n\n엔드포인트: mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com",
        "labels": ["infra", "week3"],
    },
    {
        "summary": "IM3-C2: RDS 데이터 적재 조율 (A1 찬영 24테이블 + A2 봉환 법률임베딩)",
        "description": "- 찬영: load_to_db.py → 24개 테이블 (~180만 행) RDS 적재\n- 봉환: 14개 법령, 3,775 청크 pgvector 적재\n- 팀원 보안그룹 IP 추가\n- 적재 후 row 수 검증\n- 테스트 동: 서교동(11440660), 합정동(11440680)",
        "labels": ["infra", "week3"],
    },
    {
        "summary": "IM3-C2: docker-compose.yml RDS 전환 업데이트",
        "description": "- 로컬 db 서비스 주석 처리\n- backend depends_on에서 db 제거\n- Redis만 로컬 Docker 유지\n- .env.example 업데이트",
        "labels": ["infra", "week3"],
    },
    {
        "summary": "IM3-C2: 통합 테스트 기반 구축",
        "description": "- tests/integration/ 디렉토리 생성\n- conftest.py: RDS 연결 기반 pytest fixture\n- test_auth_flow.py: 회원가입 → 로그인 → JWT\n- test_simulate_flow.py: /simulate, /analyze 호출 검증\n- 테스트 동 데이터: 서교동(11440660)",
        "labels": ["test", "week3"],
    },
    {
        "summary": "IM3-C2: 전체 파이프라인 통합 테스트 (데이터→Agent→UI)",
        "description": "- test_full_pipeline.py 작성\n- RDS 실데이터 → 5인 Agent → synthesis JSON 검증\n- Docker 환경에서 테스트 실행 확인\n- scripts/run_tests.sh + pytest 커버리지 리포트",
        "labels": ["test", "week3"],
    },
    {
        "summary": "IM3-C2: Docker 프로덕션 최적화",
        "description": "- docker-compose.prod.yml 작성 (개발/프로덕션 분리)\n- restart: always, 로그 드라이버, 리소스 제한\n- 볼륨 마운트 최적화 (RDS 사용으로 DB 볼륨 불필요)\n- scripts/deploy.sh 배포 스크립트 작성",
        "labels": ["infra", "week3"],
    },
    # 4주차
    {
        "summary": "IM3-C2: EC2(Lightsail) 서비스 배포",
        "description": "- Lightsail 4~8GB 인스턴스 생성\n- Docker + docker-compose 설치\n- git clone → docker compose up --build -d\n- 전체 서비스 정상 동작 확인\n- 메모리/CPU 사용량 모니터링",
        "labels": ["infra", "week4"],
    },
    {
        "summary": "IM3-C2: Route 53 도메인 + SSL 연결",
        "description": "- Route 53 도메인 연결\n- Let's Encrypt SSL 인증서 설치 (certbot)\n- Nginx HTTPS 리다이렉트 설정\n- 전체 HTTPS 통신 확인",
        "labels": ["infra", "week4"],
    },
    {
        "summary": "IM3-C2: 발표 자료 작성",
        "description": "- 아키텍처 다이어그램 (LangGraph Hub-and-Spoke)\n- 기술 스택 요약표\n- 데모 시나리오 구성\n- 팀원별 역할/성과 슬라이드",
        "labels": ["docs", "week4"],
    },
    {
        "summary": "IM3-C2: 시연 스크립트 + 리허설",
        "description": "- 시연 대본 작성 (시간 배분)\n- 장애 대응 플랜 (API 실패 시 mock 전환 등)\n- 팀 리허설 실행\n- 최종 데모 시나리오 확정",
        "labels": ["docs", "week4"],
    },
]

print(f"총 {len(tickets)}개 티켓 생성 시작 (IM3-91 하위)...\n")

created = []
for i, ticket in enumerate(tickets, 1):
    payload = {
        "fields": {
            "project": {"key": "IM3"},
            "parent": {"key": "IM3-91"},
            "summary": ticket["summary"],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": line}]
                    }
                    for line in ticket["description"].split("\n") if line.strip()
                ]
            },
            "issuetype": {"id": TASK_TYPE_ID},
            "labels": ticket.get("labels", []),
        }
    }

    r = requests.post(
        f"{URL}/rest/api/3/issue",
        auth=AUTH,
        headers=HEADERS,
        data=json.dumps(payload)
    )

    if r.status_code in (200, 201):
        key = r.json()["key"]
        print(f"  [{i}/{len(tickets)}] {key}: {ticket['summary']}")
        created.append(key)
    else:
        print(f"  [{i}/{len(tickets)}] FAIL: {ticket['summary']}")
        err = r.text[:300]
        print(f"    Error: {r.status_code} {err}")

print(f"\n완료! {len(created)}/{len(tickets)}개 티켓 생성됨")
if created:
    print(f"생성된 티켓: {', '.join(created)}")
