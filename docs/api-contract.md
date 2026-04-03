# API 엔드포인트 (프론트엔드-백엔드 계약)

| Method | Path | 설명 | 요청 스키마 | 응답 스키마 |
|--------|------|------|-----------|-----------|
| GET | `/health` | 서버 상태 확인 | — | `{"status": "ok"}` |
| POST | `/simulate` | 시뮬레이션 실행 | `SimulationInput` | `SimulationOutput` |
| GET | `/report/{request_id}` | 리포트 조회 | — | `SimulationOutput` |
| GET | `/status/{job_id}` | 작업 상태 확인 | — | `{"status": "..."}` |

## SimulationInput (요청)

```python
{
    "business_type": "cafe" | "restaurant" | "convenience",
    "brand_name": str,
    "target_district": str,           # 마포구 행정동명
    "existing_stores": [              # 기존 매장 목록
        {"district": str, "address": str, "monthly_revenue": int}
    ],
    "initial_investment": int,        # 기본값 150,000,000원
    "monthly_rent": int,
    "simulation_months": int,         # 기본값 12
    "scenarios": ["base"]             # What-if 시나리오
}
```

## SimulationOutput (응답)

```python
{
    "request_id": str,
    "target_district": str,
    "simulation_months": int,
    "monthly_projection": [           # 월별 매출 예측
        {"month": int, "revenue": int, "cumulative_profit": int}
    ],
    "comparison": [                   # 행정동 비교
        {"score": float, "revenue": int, "bep_month": int,
         "survival_rate": float, "cannibalization_rate": float}
    ],
    "legal_risks": [                  # 법률 리스크
        {"type": str, "risk_level": str, "detail": str}
    ],
    "ai_recommendation": str          # AI 종합 추천
}
```

> **주의**: 이 스키마를 변경하면 프론트엔드와 백엔드 모두 영향받습니다. 변경 시 반드시 프론트엔드(E)와 백엔드(B) 담당자가 함께 협의하세요.
