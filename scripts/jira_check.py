import requests
import json
import sys
import io
import os
from requests.auth import HTTPBasicAuth

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

URL = "https://bat981120.atlassian.net"
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
DONE_TRANSITION_ID = "31"

# 완료 처리할 파트
completed_tickets = [
    "IM3-149", # docker-compose.yml RDS 전환
    "IM3-150"  # 통합 테스트 기반 구축
]

print("--- C2 완료 티켓 전환 ---")
for ticket_key in completed_tickets:
    r = requests.post(
        f"{URL}/rest/api/3/issue/{ticket_key}/transitions",
        auth=AUTH,
        headers=HEADERS,
        data=json.dumps({"transition": {"id": DONE_TRANSITION_ID}})
    )
    if r.status_code == 204:
        print(f"  {ticket_key} -> Done!")
    else:
        print(f"  {ticket_key} -> Failed ({r.status_code}: {r.text[:200]})")

# 최종 상태 확인
print("\n--- IM3-91 하위 전체 상태 ---")
jql = "parent = IM3-91 ORDER BY key ASC"
r2 = requests.post(
    f"{URL}/rest/api/3/search/jql",
    auth=AUTH,
    headers=HEADERS,
    data=json.dumps({"jql": jql, "maxResults": 50, "fields": ["summary", "status"]})
)
for issue in r2.json().get("issues", []):
    key = issue["key"]
    summary = issue["fields"]["summary"]
    status = issue["fields"]["status"]["name"]
    mark = "[DONE]" if "완료" in status or "Done" in status else "[TODO]"
    print(f"  {mark} {key}: {summary}")
