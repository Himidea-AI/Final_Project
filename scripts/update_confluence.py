"""Confluence 페이지에 산출물 구조 섹션 추가."""

import json
import os
import sys

import requests

JIRA_AUTH = (os.environ.get("JIRA_EMAIL", ""), os.environ.get("JIRA_API_TOKEN", ""))
PAGE_ID = "1900719"
BASE_URL = "https://bat981120.atlassian.net/wiki/api/v2"

# 1. 기존 페이지 가져오기
resp = requests.get(f"{BASE_URL}/pages/{PAGE_ID}?body-format=storage", auth=JIRA_AUTH)
page = resp.json()
existing_body = page["body"]["storage"]["value"]
current_version = page["version"]["number"]

# 2. 추가할 산출물 섹션
append_html = """
<h2>9. 모델 산출물 구조</h2>

<h3>전체 파이프라인</h3>
<pre>
사용자 요청 (동코드 + 업종코드 + 비용설정)
      |
      v
ModelOutput.generate()
      |
      +-- LSTM 매출 예측 --> revenue_forecast (12개월 매출 + 신뢰구간)
      |
      +-- 생존률 예측    --> survival (생존률 + 리스크레벨 + 월별감쇄)
      |
      +-- BEP 계산      --> bep (손익분기점 + 월별 손익)
      |
      v
B2 시뮬레이션 (12개월 시나리오 + SHAP 분석)
</pre>

<h3>산출물 JSON 구조 (예시: 합정동 커피-음료)</h3>
<pre>
{
  "input": {
    "dong_code": "11440680", "dong_name": "합정동",
    "industry_code": "CS100010", "industry_name": "커피-음료"
  },
  "revenue_forecast": {
    "monthly_avg": 47200000,
    "monthly_predictions": [
      {"month": 1, "predicted_sales": 45000000, "confidence_lower": 38000000, "confidence_upper": 52000000},
      {"month": 2, "predicted_sales": 46000000, ...},
      ... (12개월)
    ]
  },
  "survival": {
    "survival_rate": 0.72,
    "risk_level": "safe",
    "monthly_survival_rates": [0.97, 0.94, 0.91, 0.88, 0.86, 0.83, 0.81, 0.78, 0.76, 0.74, 0.72, 0.70]
  },
  "bep": {
    "bep_months": 18,
    "monthly_profit": 2800000,
    "total_initial_investment": 130000000,
    "annual_roi": 25.8,
    "monthly_simulation": [
      {"month": 1, "revenue": 45000000, "cost": 42200000, "profit": 2800000,
       "cumulative_profit": -127200000, "bep_reached": false},
      ... (12개월)
    ]
  },
  "metadata": {"model_version": "0.1.0", "generated_at": "...", "data_period": "2019Q1~2024Q4"}
}
</pre>

<h3>revenue_forecast (매출 예측)</h3>
<table>
<thead><tr><th>필드</th><th>타입</th><th>설명</th></tr></thead>
<tbody>
<tr><td>monthly_avg</td><td>int</td><td>12개월 평균 예상 월매출 (원)</td></tr>
<tr><td>monthly_predictions[].month</td><td>int</td><td>월 (1~12)</td></tr>
<tr><td>monthly_predictions[].predicted_sales</td><td>float</td><td>해당 월 예상매출 (원)</td></tr>
<tr><td>monthly_predictions[].confidence_lower</td><td>float</td><td>95% 신뢰구간 하한</td></tr>
<tr><td>monthly_predictions[].confidence_upper</td><td>float</td><td>95% 신뢰구간 상한</td></tr>
</tbody></table>
<p>LSTM 모델이 4분기를 예측하고, 각 분기를 3개월로 분배. 신뢰구간은 예측값 기반 산출.</p>

<h3>survival (생존률)</h3>
<table>
<thead><tr><th>필드</th><th>타입</th><th>설명</th></tr></thead>
<tbody>
<tr><td>survival_rate</td><td>float</td><td>향후 1분기 생존 확률 (0~1)</td></tr>
<tr><td>risk_level</td><td>string</td><td>safe (&ge;0.7) / caution (&ge;0.4) / danger (&lt;0.4)</td></tr>
<tr><td>monthly_survival_rates</td><td>float[]</td><td>12개월 월별 생존률 (감쇄 곡선)</td></tr>
</tbody></table>

<h3>bep (손익분기점)</h3>
<table>
<thead><tr><th>필드</th><th>타입</th><th>설명</th></tr></thead>
<tbody>
<tr><td>bep_months</td><td>int</td><td>BEP 도달 예상 개월수 (-1이면 도달 불가)</td></tr>
<tr><td>monthly_profit</td><td>float</td><td>월 순이익 (원)</td></tr>
<tr><td>total_initial_investment</td><td>float</td><td>초기투자 합계 (보증금+권리금+인테리어+가맹비)</td></tr>
<tr><td>annual_roi</td><td>float</td><td>연간 ROI (%)</td></tr>
<tr><td>monthly_simulation[]</td><td>array</td><td>12개월 월별 매출/비용/손익/누적손익/BEP도달여부</td></tr>
</tbody></table>
<p>BEP = 초기투자비 / (월매출 - 월고정비 - 월변동비). 비용은 업종별 기본값 또는 사용자 입력.</p>

<h3>업종별 기본 비용 구조</h3>
<table>
<thead><tr><th>업종</th><th>원가율</th><th>월 인건비</th></tr></thead>
<tbody>
<tr><td>한식음식점</td><td>35%</td><td>500만원</td></tr>
<tr><td>중식음식점</td><td>33%</td><td>450만원</td></tr>
<tr><td>일식음식점</td><td>38%</td><td>550만원</td></tr>
<tr><td>양식음식점</td><td>35%</td><td>500만원</td></tr>
<tr><td>제과점</td><td>30%</td><td>400만원</td></tr>
<tr><td>패스트푸드점</td><td>32%</td><td>350만원</td></tr>
<tr><td>치킨전문점</td><td>40%</td><td>350만원</td></tr>
<tr><td>분식전문점</td><td>30%</td><td>300만원</td></tr>
<tr><td>호프-간이주점</td><td>35%</td><td>400만원</td></tr>
<tr><td>커피-음료</td><td>25%</td><td>400만원</td></tr>
</tbody></table>

<h3>B2 사용 방법</h3>
<pre>
from models.interface import ModelOutput

result = ModelOutput.generate(
    dong_code="11440680",
    industry_code="CS100010",
    industry_name="커피-음료",
    cost_config=None  # 업종 기본값 사용
)

monthly_sales = result["revenue_forecast"]["monthly_predictions"]
survival = result["survival"]["monthly_survival_rates"]
bep_sim = result["bep"]["monthly_simulation"]
</pre>
<p>모델 가중치가 없는 환경에서는 자동으로 mock 데이터를 반환하여 B2 개발을 즉시 시작할 수 있습니다.</p>
"""

# 3. 업데이트
new_body = existing_body + append_html
payload = {
    "id": PAGE_ID,
    "status": "current",
    "title": page["title"],
    "body": {"representation": "storage", "value": new_body},
    "version": {"number": current_version + 1, "message": "산출물 구조 섹션 추가"},
}

resp = requests.put(f"{BASE_URL}/pages/{PAGE_ID}", auth=JIRA_AUTH, json=payload)
result = resp.json()
if "id" in result:
    print(f"URL: https://bat981120.atlassian.net/wiki/spaces/IM3/pages/{result['id']}")
    print(f"version: {result['version']['number']}")
else:
    print(json.dumps(result, indent=2, ensure_ascii=False)[:500])
