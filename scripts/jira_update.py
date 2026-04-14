"""
Jira 티켓 상태 변경 + 코멘트 자동화 CLI

담당: A1 — 데이터 엔지니어 (찬영)

Usage:
    # 상태 변경 + 코멘트
    python scripts/jira_update.py IM3-86 --status done --comment "kakao_store 792건 적재 완료"

    # 코멘트만
    python scripts/jira_update.py IM3-86 --comment "진행 중: 카카오 API 연동 테스트"

    # 상태만 변경
    python scripts/jira_update.py IM3-86 --status in_progress

    # 티켓 설명 업데이트
    python scripts/jira_update.py IM3-86 --description "카카오 API로 마포구 점포 수집"

    # 티켓 정보 조회
    python scripts/jira_update.py IM3-86 --info

    # 새 티켓 생성
    python scripts/jira_update.py --create --summary "A1: kakao_store 테이블 신규 생성" --description "카카오 API 기반 실시간 점포 수집"

Status shortcuts:
    todo / t       → 해야 할 일
    in_progress / i → 진행 중
    done / d       → 완료
"""

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# .env 파일에서 환경변수 로드
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_BASE = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
PROJECT_KEY = "IM3"

# 상태 → transition ID 매핑
STATUS_MAP = {
    "todo": 11,
    "t": 11,
    "해야 할 일": 11,
    "in_progress": 21,
    "i": 21,
    "진행 중": 21,
    "done": 31,
    "d": 31,
    "완료": 31,
}


def _auth_header() -> str:
    return base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()


def _request(method: str, url: str, data: dict | None = None) -> dict:
    """Jira REST API 호출."""
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Basic {_auth_header()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def get_info(issue_key: str) -> None:
    """티켓 정보 조회."""
    url = f"{JIRA_BASE}/rest/api/3/issue/{issue_key}?fields=summary,status,description"
    data = _request("GET", url)
    fields = data["fields"]
    print(f"  Key:    {data['key']}")
    print(f"  제목:   {fields['summary']}")
    print(f"  상태:   {fields['status']['name']}")

    desc = fields.get("description")
    if desc:
        # ADF(Atlassian Document Format)에서 텍스트 추출
        texts = []
        if isinstance(desc, dict):
            for block in desc.get("content", []):
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        texts.append(item["text"])
        desc_text = " ".join(texts) if texts else str(desc)
        print(f"  설명:   {desc_text[:200]}")
    else:
        print("  설명:   (없음)")


def transition(issue_key: str, status: str) -> None:
    """상태 전환."""
    tid = STATUS_MAP.get(status.lower())
    if not tid:
        print(f"ERROR: 알 수 없는 상태 '{status}'", file=sys.stderr)
        print(f"  사용 가능: {', '.join(STATUS_MAP.keys())}", file=sys.stderr)
        sys.exit(1)

    url = f"{JIRA_BASE}/rest/api/3/issue/{issue_key}/transitions"
    _request("POST", url, {"transition": {"id": str(tid)}})
    status_name = {11: "해야 할 일", 21: "진행 중", 31: "완료"}[tid]
    print(f"  [{issue_key}] 상태 → {status_name}")


def add_comment(issue_key: str, text: str) -> None:
    """코멘트 추가 (ADF 형식)."""
    url = f"{JIRA_BASE}/rest/api/3/issue/{issue_key}/comment"
    body = {
        "body": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        }
    }
    _request("POST", url, body)
    print(f"  [{issue_key}] 코멘트 추가: {text[:80]}")


def update_description(issue_key: str, text: str) -> None:
    """설명 업데이트 (ADF 형식)."""
    url = f"{JIRA_BASE}/rest/api/3/issue/{issue_key}"
    body = {
        "fields": {
            "description": {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": text}],
                    }
                ],
            }
        }
    }
    _request("PUT", url, body)
    print(f"  [{issue_key}] 설명 업데이트 완료")


def create_issue(summary: str, description: str = "") -> str:
    """새 티켓 생성."""
    url = f"{JIRA_BASE}/rest/api/3/issue"
    body: dict = {
        "fields": {
            "project": {"key": PROJECT_KEY},
            "summary": summary,
            "issuetype": {"name": "Task"},
        }
    }
    if description:
        body["fields"]["description"] = {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}],
                }
            ],
        }
    data = _request("POST", url, body)
    key = data["key"]
    print(f"  생성 완료: {key} — {summary}")
    return key


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Jira 티켓 상태/코멘트 자동화")
    parser.add_argument("issue_key", nargs="?", help="이슈 키 (예: IM3-86)")
    parser.add_argument("--status", "-s", help="상태 변경 (todo/in_progress/done)")
    parser.add_argument("--comment", "-c", help="코멘트 추가")
    parser.add_argument("--description", "-desc", help="설명 업데이트")
    parser.add_argument("--info", action="store_true", help="티켓 정보 조회")
    parser.add_argument("--create", action="store_true", help="새 티켓 생성")
    parser.add_argument("--summary", help="새 티켓 제목 (--create 시)")
    args = parser.parse_args()

    if not JIRA_EMAIL or not JIRA_TOKEN or not JIRA_BASE:
        print("ERROR: .env에 JIRA_EMAIL, JIRA_API_TOKEN, JIRA_BASE_URL 설정 필요", file=sys.stderr)
        sys.exit(1)

    # 티켓 생성 모드
    if args.create:
        if not args.summary:
            print("ERROR: --create 시 --summary 필수", file=sys.stderr)
            sys.exit(1)
        create_issue(args.summary, args.description or "")
        return

    if not args.issue_key:
        parser.print_help()
        sys.exit(1)

    # 정보 조회
    if args.info:
        get_info(args.issue_key)
        return

    # 상태 변경
    if args.status:
        transition(args.issue_key, args.status)

    # 코멘트 추가
    if args.comment:
        add_comment(args.issue_key, args.comment)

    # 설명 업데이트
    if args.description:
        update_description(args.issue_key, args.description)

    if not args.status and not args.comment and not args.description:
        get_info(args.issue_key)


if __name__ == "__main__":
    main()
