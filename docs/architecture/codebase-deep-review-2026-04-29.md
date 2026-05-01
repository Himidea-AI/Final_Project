# 코드베이스 깊이 리뷰 (Deep Review)
**작성일**: 2026-04-29
**대상 브랜치**: `IM3-243-dong-fk-followup` → `dev`
**분석 방식**: 정적 코드 분석 (3개 영역 병렬, Explore agent thorough)
**범위**: backend/ + models/ + validation/ + frontend/ (606+ 파일)

---

## 0. Executive Summary

이전 리뷰(2026-04-28)는 **데이터 레이어/FK/ORM 동기화** 중심이었고, 이번 리뷰는 **품질/보안/성능/일관성** 중심. 총 **66개 발견**.

| 영역 | Critical 🔴 | High 🟠 | Medium 🟡 | Low 🟢 | 합계 |
|---|---|---|---|---|---|
| **Backend** (보안/성능/에러) | 6 | 12 | 6 | 14 | 38 |
| **Models** (학습/추론/스케일러) | 2 | 4 | 5 | 0 | 11 |
| **Frontend** (API/타입/보안) | 2 | 6 | 9 | 0 | 17 |
| **합계** | **10** | **22** | **20** | **14** | **66** |

### 가장 시급한 5건 (운영 사고 가능)

1. **🔴 SQL Injection** — `auth.py`의 동적 set_clause (5개 라인)
2. **🔴 JWT secret dev fallback** — settings.py 환경변수 미설정 시 약한 키 사용
3. **🔴 Frontend bep_months 잔재** — 4개 컴포넌트가 deprecated 필드 참조 → BEP 항상 null
4. **🔴 Emerging district 데이터 누수** — predict()에서 매번 fit_transform → reconstruction error 신뢰도 0
5. **🔴 /simulate vs /analyze 응답 wrapping 불일치** — 프론트가 분기 처리

---

## 1. 🔴 CRITICAL (10건) — 즉시 수정 필수

### CR-1. SQL Injection — `backend/src/services/auth.py`
**라인**: 786-788, 819-821, 839, 851

```python
# 현재 (위험)
set_clause = ", ".join(f"{k} = :{k}" for k in updates)
conn.execute(text(f"UPDATE users SET {set_clause} WHERE id = :id"), updates)
```

**문제**: `updates`의 키는 사용자 입력 dict에서 옴. 검증 없음 → `"; DROP TABLE users; --"` 같은 키 가능.

**해결**:
```python
ALLOWED = {"contact_name", "position", "phone", "store_count"}
updates = {k: v for k, v in data.items() if k in ALLOWED and v is not None}
if not updates:
    return {"status": "error", "message": "수정할 항목이 없습니다."}
set_clause = ", ".join(f"{k} = :{k}" for k in updates)
conn.execute(text(f"UPDATE users SET {set_clause} WHERE id = :id"), updates)
```

---

### CR-2. JWT secret dev-only fallback — `backend/src/config/settings.py:66`

```python
# 현재 (위험)
jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-only-not-secret-replace-in-prod")
```

**문제**: 운영에서 환경변수 누락 시 약한 키로 JWT 생성 → 토큰 위조 가능.

**해결**:
```python
jwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
if not jwt_secret_key or len(jwt_secret_key) < 32:
    raise ValueError("JWT_SECRET_KEY 환경변수 미설정 또는 32자 미만 — .env 점검 필수")
```

---

### CR-3. 에러 메시지 그대로 응답 — `backend/src/main.py:773-774, 821-823, 1283-1287`

```python
# 현재
except Exception as e:
    print(f"!!! [API ERROR] !!! {str(e)}")
    return {"status": "error", "message": str(e)}  # ← 스택트레이스/DB 에러 노출
```

**해결**:
```python
import logging
logger = logging.getLogger(__name__)

except Exception as e:
    logger.exception(f"[SIMULATE] {type(e).__name__}")  # 내부 로그
    return {"status": "error", "message": "분석 중 오류 발생, 관리자 문의"}  # 사용자용
```

---

### CR-4. Redis 연결 누수 — `backend/src/main.py:92-99`

```python
# 현재 — 매 요청마다 새 연결
async with aioredis.from_url(settings.redis_url, decode_responses=True) as r:
```

**해결**: 싱글톤 풀 사용 (FastAPI startup event에 한 번 생성).

---

### CR-5. 패스워드 검증 타이밍 공격 — `backend/src/services/auth.py:196`

```python
# 현재
if not row:
    return {"status": "error", "message": "가입되지 않은 이메일입니다."}  # 계정 열거 가능
if not _verify_password(password, user["password_hash"]):
    return {"status": "error", "message": "비밀번호가 일치하지 않습니다."}
```

**해결**: 메시지 통일 + 더미 verify로 타이밍 동일화.

---

### CR-6. `auth.login` 동기 함수 — `backend/src/main.py:904`

`auth.login`이 동기인데 threadpool로 호출 → bcrypt + DB 쿼리 모두 스레드풀 점유. 동시 로그인 시 응답 지연. 장기적으로 async DB 드라이버로 리팩터.

---

### CR-7. Frontend `bep_months` 잔재 — 4개 컴포넌트

**파일들**:
- `frontend/src/pages/SimulationCompare.tsx:79`
- `frontend/src/components/SimulationResult/dashboard/tabs/FinancialTab.tsx:28`
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx:25`
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx:29`

**문제**: 백엔드는 `bep_quarters`로 보내는데 프론트는 `bep_months` 읽음 → 항상 `null`. PR #116(BEP 분기 전환) 미반영.

**해결**: 4개 컴포넌트 모두 `ps?.bep_months ?? null` → `ps?.bep_quarters ?? null` 변경. C1(강민) 영역.

---

### CR-8. `/simulate` vs `/analyze` 응답 wrapping 불일치 — `backend/src/main.py:1261, 739`

```python
# /simulate (라인 1261-1282) — 직접 dict 반환
return result

# /analyze (라인 771) — wrapping
return {"status": "success", "data": result}
```

**문제**: 프론트가 둘 다 처리하느라 코드 분기 + 에러 시 `.message` 위치 불확정.

**해결**: 둘 다 `{status: "success", "data": result}` 형식으로 통일.

---

### CR-9. Emerging District 모델 — 데이터 누수 — `models/emerging_district/predict.py:192-194`

```python
# 현재 (위험)
scaler = MinMaxScaler()
feat_scaled = scaler.fit_transform(feat_vals)  # ← 추론마다 fit
```

**문제**: 학습 시 전체 마포 16동 통합 스케일러로 학습한 후, 추론 시 현재 동×업종 데이터로만 재 fit → 완전히 다른 스케일. reconstruction error 신뢰도 0.

**해결**:
```python
scaler = _load_scaler()  # 학습 시 저장한 scaler.pkl
feat_scaled = scaler.transform(feat_vals)  # transform만
```

---

### CR-10. TCN/LSTM 가중치 버전 혼동 — `models/tcn_forecast/predict.py:128`

```python
input_size = len(feat_scaler.scale_)  # ← 스케일러로 input_size 추론 (brittle)
```

**문제**: `weights/` 디렉토리에 `finetuned_mapo_tcn.pt`, `_34f.pt`, `_imp_a.pt`, `_seed2026.pt` 등 다양. 어느 게 production? input_size 불일치 시 silent fail.

**해결**: 가중치별 `_meta.json` 저장 (`{"input_size": 34, "feature_columns": [...]}`).

---

## 2. 🟠 HIGH (22건) — 단기 수정 (1-2주)

### Backend (12건)

| # | 항목 | 파일 | 영향 |
|---|---|---|---|
| H-B1 | NTS API 키 매 요청마다 `os.environ.get()` 호출 | main.py 17곳 | 성능 |
| H-B2 | `print()` vs `logger` 혼용 (~25회) | main.py + nodes/* | 운영 모니터링 |
| H-B3 | `except Exception: pass` silent fail | nodes/demographic_depth.py:208 외 | 디버깅 |
| H-B4 | N+1 쿼리 가능성 | services/operational_fit.py | 성능 |
| H-B5 | 외부 API 일부 timeout 미설정 | services/seoul_realtime.py | 행업 위험 |
| H-B6 | DEBUG 플래그가 캐시 동작 좌우 | settings.py | 운영 사고 |
| H-B7 | Response model 누락 | main.py /simulate, /analyze, /predict | API 계약 |
| H-B8 | HTTP 상태 코드 비일관 (에러도 200) | main.py | REST 위반 |
| H-B9 | `sim_result["bep"]["..."]` KeyError 위험 | main.py:385, 559 | 런타임 에러 |
| H-B10 | Transaction `commit()` 실패 시 rollback 누락 | services/auth.py:81 | 데이터 무결성 |
| H-B11 | `main.py` 1561줄 — 모듈화 부족 | main.py | 유지보수성 |
| H-B12 | CORS 운영 설정 부재 (localhost wildcard) | main.py:113-122 | 보안 |

### Models (4건)

| # | 항목 | 파일 | 영향 |
|---|---|---|---|
| H-M1 | Revenue Predictor 추세 무시 (4분기 평균만) | revenue_predictor/predict.py:104 | 예측 부정확 |
| H-M2 | Closure Risk TCN 스케일러 fallback 시 데이터 누수 | closure_risk/predict.py:79-87 | 모델 신뢰도 |
| H-M3 | Living Pop Forecast v1/v2 호환 위험 | living_pop_forecast/predict.py:49-79 | shape mismatch |
| H-M4 | Interface BEP 단위 불일치 (분기 vs 월) | interface.py:490-501 | BEP 부정확 |

### Frontend (6건)

| # | 항목 | 파일 | 영향 |
|---|---|---|---|
| H-F1 | `/analyze` 에러 응답 wrapping 비일관 | main.py:739-774 | 프론트 에러 |
| H-F2 | `simResult` 옵셔널 필드 null guard 부족 | App.tsx:1170 등 | TypeError |
| H-F3 | `AbmPersonaMap.tsx` 2880줄 monolithic | components/AbmPersonaMap.tsx | 성능 |
| H-F4 | API 중복 호출 (race condition) | AbmPersonaMap.tsx:728-756 | 네트워크 |
| H-F5 | fetch 에러 시 HTML 응답 처리 X | App.tsx:3796-3840 | silent fail |
| H-F6 | JWT를 plaintext localStorage 저장 | api/client.ts:64 | XSS 위험 |

---

## 3. 🟡 MEDIUM (20건) — 다음 스프린트 (3-4주)

### Backend (6건)

| # | 항목 | 파일 |
|---|---|---|
| M-B1 | 하드코딩 동 좌표 (market_analyst.py vs main.py 중복) | nodes/market_analyst.py:75-92 |
| M-B2 | Redis 캐시 키 collision 가능 (단순 `:` 구분) | nodes/district_ranking.py:487 |
| M-B3 | `/analyze` etc — 입력 sanitize 누락 (Pydantic field_validator 미사용) | schemas/simulation_input.py |
| M-B4 | 캐시 key version 정책 부재 (각 노드마다 다른 prefix) | nodes/* |
| M-B5 | `traceback.print_exc()` 에러 노출 | main.py:1283 |
| M-B6 | uvicorn workers=1 (운영 추천 4) | (설정 미명시) |

### Models (5건)

| # | 항목 | 파일 |
|---|---|---|
| M-M1 | Closure Risk label leak 의심 (industry_avg 전 기간 평균) | closure_risk/data_prep.py:117-125 |
| M-M2 | Hot Deck 보간 비결정성 (`np.random.normal(1, 0.02)`) | lstm_forecast/data_prep.py:330 |
| M-M3 | Feature column 순서 fragile | data_prep.py 전반 |
| M-M4 | Closure Rate predict DB 호출 매번 (캐시 없음) | revenue_predictor/predict.py:92 |
| M-M5 | Customer Revenue 부분 실패 처리 미약 | interface.py:517-531 |

### Frontend (9건)

| # | 항목 | 파일 |
|---|---|---|
| M-F1 | `closure_risk`, `competitor_intel`, `trend_forecast` Pydantic 모델 미정의 (dict) | schemas/simulation_output.py:152-169 |
| M-F2 | `MonthlyProjection` deprecated alias 존재 | types/index.ts:62 |
| M-F3 | Kakao Maps API 로드 검증 없음 | AbmPersonaMap.tsx:772 |
| M-F4 | Vacancy fetch — Promise.all 한 곳 실패 시 전체 lost | AbmPersonaMap.tsx:659-696 |
| M-F5 | ABM thoughts 백엔드 contract 문서화 부재 | AbmPersonaMap.tsx:539-562 |
| M-F6 | Unused `CustomerSegmentRequest` type | api/client.ts:168 |
| M-F7 | `/report`, `/status` mock 미사용 | main.py:724-736 |
| M-F8 | Auth 만료 시 zombie state | auth/AuthContext.tsx:80-96 |
| M-F9 | `competitor_intel.market_entry_signal` 검증 없음 | App.tsx:4087 |

---

## 4. 🟢 LOW (14건) — 기술 부채

| # | 항목 | 파일 |
|---|---|---|
| L-1 | 사용 안 되는 import (소수) | main.py |
| L-2 | print/한글 혼용 로그 | main.py |
| L-3 | `_mock_simulation_response` 테스트 모드 fallback | main.py:1197-1216 |
| L-4 | LangGraph timeout 600초 하드코딩 | main.py:343 |
| L-5 | 시뮬 캐시에서 `trajectory` 제거 표시 부족 | main.py:1554-1559 |
| L-6 | `/simulate-abm` 거대 함수 (150+ 줄) | main.py:1354 |
| L-7 | 법규 cache TTL 24시간 (1주일 권장) | nodes/legal.py:700 |
| L-8 | 인구 조회 14일 폴백 (적절) | services/population_api.py:39-53 |
| L-9 | 예외 타입 너무 넓음 (Exception only) | nodes/legal.py:80 |
| L-10 | DB connection pool 기본값 | database/postgres.py |
| L-11 | 한/영 메시지 혼용 | main.py |
| L-12 | uvicorn worker 설정 부재 | docker-compose |
| L-13 | uncommitted .gitignore 보강 | repo root |
| L-14 | docs/issues 디렉토리 정리 | docs/issues |

---

## 5. 우선순위 로드맵

### Week 1 (Critical 10건 + High Backend 6건)

**보안 (CR-1, CR-2, CR-5, H-B12)**:
- SQL Injection 방어 (auth.py whitelist)
- JWT secret 검증 강제
- 패스워드 응답 메시지 통일
- CORS 운영 설정

**Frontend 동기화 (CR-7, CR-8, H-F1)**:
- bep_months → bep_quarters (4 컴포넌트, **C1 강민 영역**)
- /simulate /analyze response wrapping 통일
- /analyze 에러 wrapping 통일

**Models 데이터 누수 (CR-9, CR-10)**:
- emerging_district scaler 학습본 사용
- TCN/LSTM 가중치 메타데이터 저장

**Backend 안정성 (CR-3, CR-4, CR-6)**:
- 에러 메시지 sanitize
- Redis 풀 싱글톤
- auth.login async 검토

### Week 2 (High 16건)

- print → logger 일괄 전환 (H-B2)
- Response model 정의 (H-B7)
- HTTP 상태 코드 정규화 (H-B8)
- Dict 접근 `.get()` 패턴 (H-B9)
- Transaction `with engine.begin()` (H-B10)
- AbmPersonaMap 분리 + memoization (H-F3)
- JWT httpOnly cookie (H-F6)
- 외부 API timeout 일관성 (H-B5)
- Living Pop v1/v2 강제 분리 (H-M3)
- BEP 단위 명확화 (H-M4)
- Revenue Predictor 추세 반영 (H-M1)
- Closure Risk scaler 명시적 에러 (H-M2)

### Week 3-4 (Medium 20건)
- main.py 모듈화 (H-B11)
- Pydantic 모델 정의 (M-F1)
- Promise.allSettled (M-F4)
- 캐시 key version 정책 (M-B4)
- Hot Deck seed 관리 (M-M2)
- Feature column 명시적 검증 (M-M3)

### 다음 메이저 (Low 14건)
- 코드 정리, 상수 통합, mock 제거 등

---

## 6. 영역별 책임 매트릭스

| 영역 | 항목 | 담당 |
|---|---|---|
| 보안/SQL/JWT | CR-1, CR-2, CR-5, H-B12 | A1 (찬영) — `services/`, `config/` |
| 프론트 BEP/응답 | CR-7, CR-8, H-F1, H-F2 | C1 (강민) — `frontend/` |
| 모델 데이터 누수 | CR-9, CR-10 | B2 (수지니) — `models/` |
| LangGraph 노드 | H-B3, H-B7, M-B4 | B1 (예진) — `agents/nodes/` |
| 인프라/CORS/uvicorn | H-B12, M-B6, L-12 | C2 (혁) — `docker/`, CI |

---

## 7. 검증 명령어 모음

### 보안 점검
```bash
# SQL Injection 가능 패턴
grep -n "f\"UPDATE\|f\"INSERT\|f\"DELETE" backend/src/services/

# JWT secret env 미설정 시 강제 에러
python -c "from src.config.settings import settings; print(settings.jwt_secret_key)"
```

### Frontend 타입 동기화
```bash
# bep_months 잔재 검색
grep -rn "bep_months" frontend/src/
# 0건이어야 정상

# 백엔드 schema와 frontend type 비교
diff <(grep "bep_quarters\|bep_months" backend/src/schemas/) \
     <(grep "bep_quarters\|bep_months" frontend/src/types/)
```

### 모델 가중치 일관성
```bash
ls -la models/tcn_forecast/weights/
ls -la models/closure_risk/weights/
# 각 .pt 파일에 _meta.json 동반 확인
```

### 로깅 일관성
```bash
# print 사용처 (logger로 전환 대상)
grep -rn "print(" backend/src/ | grep -v "test_" | wc -l
```

---

## 8. 다음 행동

### 즉시 처리 (Auto mode 가능)
- A1 영역 `CR-2` (settings.py JWT 검증) — 안전, 의심 없음
- A1 영역 `H-B6` (DEBUG 플래그 캐시 분리) — 안전

### 위임 필요
- **C1 (강민)**: CR-7 (bep_months 4컴포넌트 수정)
- **B1 (예진)**: H-B3 (silent fail 로깅 개선) — 휴지 중이라 PM 위임
- **B2 (수지니)**: CR-9, CR-10, H-M1, H-M2 (모델 데이터 누수)
- **C2 (혁)**: H-B12 (CORS 운영 설정)

### PM 결정
- main.py 모듈화 (H-B11) 일정
- 보안 항목(CR-1~CR-6)을 즉시 hotfix vs 차주 정기 sprint

---

## 부록: 분석 메타데이터

- **분석 시점**: 2026-04-29
- **분석 도구**: Claude Code Explore agent × 3 (병렬, thorough)
- **분석 영역**: backend/src/ (78 파일), models/ (40+ 파일), frontend/src/ (200+ 파일)
- **이전 리뷰**: `docs/architecture/codebase-review-2026-04-28.md` (FK/ORM 중심)
- **본 리뷰**: 보안/품질/성능/타입 동기화 중심

이전 리뷰와 합치면 **총 ~90개 발견**. 우선순위 매트릭스에 따라 단계적 처리 권장.
