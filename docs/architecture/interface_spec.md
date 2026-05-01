# 모듈 간 JSON 인터페이스 스펙

> 1주차 첫날 팀 전원 합의 후 변경 불가. 변경 시 전원 동의 필요.

## 1. 시뮬레이션 요청 (Client → API)

```json
{
  "business_type": "cafe",
  "brand_name": "이디야",
  "target_district": "망원1동",
  "existing_stores": [
    {"district": "서교동", "address": "서교동 123-4", "monthly_revenue": 32000000},
    {"district": "공덕동", "address": "공덕동 456-7", "monthly_revenue": 28000000}
  ],
  "initial_investment": 150000000,
  "monthly_rent": 3500000,
  "simulation_months": 12,
  "scenarios": ["base", "competitor_entry", "rent_increase_20pct"]
}
```

## 2. Agent 간 공유 상태 (AgentState)

```json
{
  "request_id": "sim_20260402_001",
  "business_type": "cafe",
  "brand_name": "이디야",
  "target_district": "망원1동",
  "existing_stores": [],
  "district_data": {
    "floating_population": {"weekday": 12340, "weekend": 18500, "peak_hour": "14:00"},
    "resident_population": {"total": 23400, "age_20_39_ratio": 0.42},
    "competition": {
      "direct_same_brand": 0,
      "direct_same_category": 12,
      "indirect_substitute": 8,
      "cannibalization_risk": 0.0
    },
    "rent_avg": 3500000,
    "closure_rate": 0.032
  },
  "analysis_results": {
    "location_score": 0,
    "estimated_monthly_revenue": 0,
    "bep_months": 0,
    "survival_probability_12m": 0,
    "cannibalization_impact": {},
    "legal_risks": []
  },
  "report": null,
  "iteration_count": 0,
  "status": "in_progress"
}
```

## 3. Agent → Supervisor 결과 전달

```json
{
  "agent_name": "competition",
  "status": "completed",
  "confidence": 0.85,
  "results": {
    "direct_competition_score": 72,
    "cannibalization_risk": {
      "store_1_impact": -0.18,
      "store_2_impact": -0.03,
      "net_revenue_gain": 10300000
    },
    "indirect_competition_pressure": 19.9
  },
  "warnings": ["반경 500m 내 동일 업종 12개 — 높은 경쟁 밀도"]
}
```

## 4. 시각화용 결과 데이터 (API → Frontend)

```json
{
  "request_id": "sim_20260402_001",
  "target_district": "망원1동",
  "simulation_months": 12,
  "monthly_projection": [
    {"month": 1, "revenue": 18000000, "cumulative_profit": -12000000},
    {"month": 2, "revenue": 22000000, "cumulative_profit": -7500000},
    {"month": 12, "revenue": 26000000, "cumulative_profit": 15000000}
  ],
  "comparison": [
    {
      "district": "망원1동",
      "score": 72, "revenue": 26000000, "bep": 8,
      "survival": 0.68, "cannibalization": -0.18
    },
    {
      "district": "공덕동",
      "score": 81, "revenue": 22000000, "bep": 5,
      "survival": 0.85, "cannibalization": -0.05
    },
    {
      "district": "대흥동",
      "score": 78, "revenue": 18000000, "bep": 5,
      "survival": 0.91, "cannibalization": 0.0
    }
  ],
  "legal_risks": [
    {"type": "가맹사업법", "risk_level": "주의", "detail": "반경 500m 내 동일 브랜드 가맹점 1개 존재"}
  ],
  "ai_recommendation": "대흥동을 추천합니다. 매출은 가장 낮지만 자기 잠식이 없고 생존 확률이 91%로 가장 높습니다."
}
```
