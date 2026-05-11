### A1 — 데이터 + DB + RAG + ABM (찬영)

**담당 영역**: 데이터베이스 설계, ETL 파이프라인, RAG 최적화, ABM 시뮬레이션, Brand 매핑, API 개발

#### 1. Database 스키마 설계 및 관리 (78 ORM, 1,019 컬럼, 32 FK)

**전체 DB 아키텍처**:
- **78개 ORM 모델** (`backend/src/database/models.py`)
- **1,019개 컬럼** (평균 13컬럼/테이블)
- **32개 명시적 FK** 관계
- Naming convention: `master_`, `seoul_`, `mapo_` prefix로 데이터 출처 구분

**주요 테이블 카테고리** (10개):
1. **Population** (6 tables): living_population, sgis_population, mapo_resident_pop, seoul_population_quarterly, sgis_household, seoul_dong_migration_monthly
2. **Sales** (7 tables): district_sales, golmok_commercial, golmok_sales, golmok_stores, seoul_district_sales, seoul_district_stores, cpi_dining_quarterly
3. **Rent** (7 tables): rent_cost, golmok_rent, seoul_golmok_rent, jeonse_dong_master, rent_cost_summary_2025, jeonse_monthly_rent, small_store_rent_q
4. **Location Master** (5 tables): dong_mapping, seoul_dong_master, dong_centroid, master_subway_station, master_ttareungi_station
5. **Business** (8 tables): industry_master, store_info, store_quarterly, kakao_store, kakao_store_hours, kakao_store_menu, seoul_adstrd_(change_ix/fclty/flpop/stor)
6. **Franchise / Brand** (5 tables): ftc_brand_franchise (16K rows), biz_brand_mapping, mart_brand_territory, naver_vacancy, vacancy_enriched
7. **Auth** (4 tables): users, manager_users, invite_codes, customer
8. **Simulation** (2 tables): simulation_foresee (ML 결과), simulation_ai (LLM 결과) - 분리 저장
9. **Trends** (6 tables): naver_trend_industry, naver_trend_monthly, naver_trend_quarterly, mapo_sns_sentiment, seoul_trdar_(change_ix/flpop/stor)
10. **Legal** (2 tables): law_legislations, law_precedents

**ER Diagram 설계**:
- `dong_code` 8자리 String 통일 (FK Group A/B1/B2 audit)
- 시계열 테이블: `year_quarter` 복합키 (2019Q1 ~ 2024Q3)
- Brand → Corp 다대일 관계 (ftc_brand_franchise.corpNm)

#### 2. Alembic 마이그레이션 관리 (IM3-alembic-user-lifecycle-catchup)

**마이그레이션 체인 복구**:
- **Phantom revision 제거**: a9c2d3e4f5b6 zombie 마이그레이션 삭제
- **Current head**: `a8f3d2e7c1b9`
- **simulation_history drop** (91b66e68ec18): 단일 테이블 → simulation_foresee + simulation_ai 분리

**테이블 생성 마이그레이션**:
1. `IndustryMaster` 신규 생성
   - 10종 업종 정의 (한식, 일식, 중식, 양식, 카페, 패스트푸드, 주점, 치킨, 분식, 제과제빵)
   - `business_type` VARCHAR(50) PRIMARY KEY
   - `category_codes` JSON (CS 코드 리스트)

2. `MartBrandTerritory` 신규 생성
   - 브랜드별 영업구역 정의
   - `brand_name`, `territory_radius_m`, `exclusivity_level`

3. `DongCentroid` 신규 생성
   - 마포 16동 중심 좌표
   - `dong_code`, `latitude`, `longitude`
   - PostGIS 활용 가능하도록 설계

**FK 제약 조건**:
```sql
ALTER TABLE simulation_foresee 
ADD CONSTRAINT fk_user 
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE kakao_store
ADD CONSTRAINT fk_dong
FOREIGN KEY (dong_code) REFERENCES dong_mapping(dong_code);
```

#### 3. 외부 API ETL 파이프라인 (5종, backend/scripts/)

**1. fill_subway_coords_seoul.py**:
- **API**: 서울시 공공 데이터 (지하철역 정보)
- **처리**: 노선별 역 좌표 크롤링 + PostGIS Point 변환
- **결과**: master_subway_station 테이블 300+ rows 채움
- **좌표계**: WGS84 (EPSG:4326)

**2. fill_ttareungi_dong_code.py**:
- **API**: 따릉이 대여소 정보
- **처리**: Haversine 거리 계산 (마포 16동 중심점 기준)
- **결과**: master_ttareungi_station.dong_code 매핑
- **알고리즘**:
  ```python
  def haversine(lat1, lon1, lat2, lon2):
      R = 6371  # 지구 반지름 (km)
      dLat = radians(lat2 - lat1)
      dLon = radians(lon2 - lon1)
      a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
      c = 2 * atan2(sqrt(a), sqrt(1-a))
      return R * c * 1000  # meter
  ```

**3. backfill_ecos_cycle.py**:
- **API**: ECOS (한국은행 경제통계시스템)
- **처리**: ecos_timeseries.cycle 컬럼 100% 채움
- **결과**: 2,783 rows / 2,783 rows (100%)
- **데이터**: 기준금리, GDP, CPI 등 월별 시계열

**4. refresh_realtime_hotspots.py**:
- **API**: 서울시 실시간 유동인구 (seoul_realtime_hotspots)
- **처리**: 일 1회 cron job으로 최신 데이터 갱신
- **결과**: 거주/방문 비율, 시간대별 인구 밀도
- **스케줄**: 매일 새벽 3시 실행

**5. backfill_master_meta.py**:
- **처리**: dong_mapping, industry_master 메타 enrichment
- **Enrichment**:
  - dong_mapping: 면적, 인구수, 행정동명 한글/영문
  - industry_master: ftc_keywords 매핑 (정보공개서 업종명 → 우리 10종)

#### 4. Legal RAG 완성 및 최적화 (봉환 초기 작업 리팩토링)

**Primary-law Boost 구현** (찬영 최적화):
```python
# 봉환 초기: RRF만 적용 (Hit@10: 62.1%)
def rrf_score(vec_rank, bm25_rank):
    return 0.4 / (60 + vec_rank) + 0.6 / (60 + bm25_rank)

# 찬영 최적화: Primary law 가중치 상승
def boosted_score(score, is_primary):
    if is_primary:
        return min(score * 2.0, 1.0)  # saturate at 1.0
    else:
        return score * 0.4  # supplementary penalty
```

**성능 개선**:
- Hit@10: 62.1% → **100%** (+37.9%p)
- MRR: 0.570 (Mean Reciprocal Rank)
- NDCG: 0.525

**OpenAI Rerank 구현** (찬영 최적화):
```python
def rerank_with_llm(query, candidates):
    prompt = f"""
    다음 법률 조항 중 '{query}'와 가장 관련성 높은 순서대로 정렬하세요.
    
    후보:
    {candidates}
    
    정렬된 순서만 숫자 리스트로 출력 (예: [3, 1, 5, 2, 4])
    """
    response = openai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_ranking(response.choices[0].message.content)
```

**성능 개선**:
- MRR: 0.785 → **0.931** (+0.146)
- NDCG: 0.642 → **0.776** (+0.134)

**Legal z-score 폐점률 구현** (2026-05-07):
```python
# 봉환 초기: 하드코딩 10% threshold
def assess_closure_risk(closure_rate):
    return 'safe' if closure_rate < 0.10 else 'danger'

# 찬영 개선: FTC 업종별 통계 기반 z-score
def assess_closure_risk_v2(closure_rate, business_type):
    industry_stats = ftc_stats[business_type]  # {mean: 0.267, std: 0.073}
    z_score = (closure_rate - industry_stats['mean']) / industry_stats['std']
    
    if z_score < -0.5:
        return 'safe'    # 평균보다 0.5 표준편차 낮음
    elif z_score < 0.5:
        return 'caution'  # 평균 ±0.5 표준편차 범위
    else:
        return 'danger'   # 평균보다 0.5 표준편차 높음
```

**예시**: 한신포차 (한식)
- 폐업률: 12.9%
- 한식 평균: 26.7%, 표준편차: 7.3%
- z-score: (0.129 - 0.267) / 0.073 = **-1.89**
- 판정: **safe** (실제로 평균 대비 매우 낮음)

**Windows 호환성 fix** (2026-05-07):
```python
# 문제: Windows ProactorEventLoop에서 psycopg async 오류
# 해결: sync retriever + asyncio.to_thread
async def retrieve_legal_docs(query):
    # sync_retriever는 sync engine 사용
    results = await asyncio.to_thread(sync_retriever.invoke, query)
    return results
```

#### 5. ABM (Agent-Based Model) 시뮬레이션 (2026-04~05)

**마포구 5,000 에이전트 모델링** (mesa 프레임워크):

**에이전트 계층 (3-Tier)**:
1. **Tier S** (상위 10%): 고소득, 신상품 얼리어답터
   - LLM: Claude Haiku
   - 의사결정: 브랜드 평판, 최신 트렌드 가중
   
2. **Tier A** (중간 60%): 중산층, 가성비 중시
   - LLM: Gemini Flash-Lite
   - 의사결정: 가격, 리뷰, 거리 균형

3. **Tier B** (하위 30%): 저소득, 가격 민감
   - LLM: 없음 (룰 기반)
   - 의사결정: 가격 우선, 거리 2순위

**에이전트 속성**:
```python
class Customer(Agent):
    def __init__(self, unique_id, model):
        self.age_group = random.choice(['10s', '20s', '30s', '40s', '50s', '60s+'])
        self.gender = random.choice(['male', 'female'])
        self.income_tier = assign_tier(self.age_group)  # S/A/B
        self.home_dong = random.choice(mapo_16_dongs)
        self.preferences = {
            'brand': random.uniform(0, 1),
            'price': random.uniform(0, 1),
            'distance': random.uniform(0, 1),
        }
```

**시뮬레이션 프로세스**:
1. **Initialization**: 5,000 에이전트 마포 16동 분포 (인구 비율 반영)
2. **Step (1일 = 1 step)**:
   - 각 에이전트 방문 여부 결정 (Poisson 분포)
   - 방문 시간대 선택 (연령대별 피크 시간 반영)
   - 매장 선택 (거리, 가격, 브랜드 스코어 조합)
   - `visits_log` 기록
3. **Aggregation (30일)**:
   - 매장별 일평균 방문자 수
   - 시간대별 분포 (peak_hours)
   - 연령/성별 breakdown

**`peak_hours` 버그 수정**:
```python
# 버그: trajectory_path 가드가 visits_log 채움 차단
if agent.trajectory_path:  # 이 조건이 항상 False
    self.visits_log.append(visit)

# 수정: 가드 제거
self.visits_log.append(visit)
```

**LLM 통합** (Tier S/A):
```python
def decide_store_llm(agent, candidates):
    prompt = f"""
    고객 프로필:
    - 연령: {agent.age_group}
    - 소득 계층: {agent.income_tier}
    - 선호도: 브랜드 {agent.preferences['brand']:.2f}, 가격 {agent.preferences['price']:.2f}
    
    후보 매장:
    {format_candidates(candidates)}
    
    가장 선호할 매장 1개를 선택하세요.
    """
    response = llm.invoke(prompt)
    return parse_choice(response)
```

#### 6. Brand 매핑 시스템 (IM3-brand-mega-canonical-fix)

**corp_brand_resolver 구현**:
```python
def resolve_brand(company_name, business_type):
    # Step 1: REGEXP_REPLACE로 괄호·공백 정규화
    normalized = re.sub(r'\(주\)|\(株\)', '', company_name).strip()
    
    # Step 2: ftc_brand_franchise ILIKE 매칭
    query = """
    SELECT brand_name, frcs_cnt
    FROM ftc_brand_franchise
    WHERE corpNm ILIKE %s
      AND business_type = %s
      AND yr = 2025
      AND frcs_cnt > 0
    ORDER BY frcs_cnt DESC
    LIMIT 1
    """
    result = db.execute(query, (f'%{normalized}%', business_type))
    
    if result:
        return result[0]['brand_name']
    else:
        return None  # CORP 미등록
```

**다업종 corp 자동 brand 매핑**:
- 예: (주)더본코리아
  - 한식 선택 → **한신포차** (frcsCnt=450, top)
  - 분식 선택 → **본죽** (frcsCnt=380, top)
  - 치킨 선택 → **본가** (frcsCnt=320, top)

**동업종 다brand corp 명시 선택** (2026-05-07):
- Frontend `selectedBrandName` state 추가
- 예: (주)더본코리아 한식 선택 시
  - Dropdown: [한신포차, 새마을식당, 본가]
  - 사용자 명시 선택 → backend는 top frcsCnt auto-override 회피

**corp_brand_resolver dedup** (2026-05-07):
```python
# Step 1: yr=2025 + frcsCnt>0 필터
# Step 2: 표기 변형 통합
normalize_map = {
    'BBQ': '비비큐(BBQ)',
    '비비큐': '비비큐(BBQ)',
    'bhc': 'BHC',
    '교촌': '교촌치킨',
}
```

**GET /corp/operated-industries API**:
```python
@router.get("/corp/operated-industries")
async def get_operated_industries(current_user: User = Depends(get_current_user)):
    company_name = current_user.company_name
    
    # JWT user 자동 추출
    if not company_name:
        return {"industries": []}  # 비회원 graceful degrade
    
    # ftc_brand_franchise에서 해당 corp의 운영 업종 조회
    query = """
    SELECT DISTINCT business_type, brand_name, frcs_cnt
    FROM ftc_brand_franchise
    WHERE corpNm ILIKE %s
      AND yr = 2025
      AND frcs_cnt > 0
    ORDER BY business_type, frcs_cnt DESC
    """
    results = db.execute(query, (f'%{company_name}%',))
    
    # 업종별 top brand 리스트 반환
    industries = {}
    for row in results:
        if row['business_type'] not in industries:
            industries[row['business_type']] = []
        industries[row['business_type']].append({
            'brand_name': row['brand_name'],
            'frcs_cnt': row['frcs_cnt']
        })
    
    return {"industries": industries}
```

**Frontend 통합**:
- 운영 외 업종 disable + line-through
- Disabled 클릭 시 toast: "귀사가 운영하지 않는 업종입니다"

**Target 라벨 bugfix** (2026-05-07):
```python
# 문제: frontend MapSection Target 표시가 authBrand fallback (등록 brand 빽다방)
# 해결: AnalysisOutput schema에 brand_name + business_type 추가 (payload echo)
class AnalysisOutput(BaseModel):
    brand_name: str  # 신규 추가
    business_type: str  # 신규 추가
    ai_recommendation: str
    # ...
```

#### 7. /stores/count-by-dongs 라이브 매장수 Endpoint (2026-05-07)

**API 구현**:
```python
@router.get("/stores/count-by-dongs")
async def count_stores_by_dongs(
    dongs: List[str] = Query(...),
    category: str = Query(...)
):
    # kakao_store에서 동 list × 업종 카테고리 매장 수 집계
    query = """
    SELECT dong_code, COUNT(*) as store_count
    FROM kakao_store
    WHERE dong_code = ANY(%s)
      AND category = %s
    GROUP BY dong_code
    """
    results = db.execute(query, (dongs, KAKAO_CATEGORY_MAP[category]))
    
    return {
        dong: result['store_count']
        for dong, result in zip(dongs, results)
    }
```

**Frontend 통합**:
- ScopeHint 컴포넌트가 `selectedDongs` 변경 시 즉시 호출
- AbortController로 이전 요청 취소 (race condition 방지)
- 로딩 spinner + fetch 실패 시 fallback 표시

**정확도 개선**:
- **Before**: 클라이언트 추정값 (부정확)
- **After**: 서버 SQL 집계 (정확도 100%)

#### 8. business_type_mapping SoT 통합 (IM3-178)

**10종 TypedDict 정의**:
```python
BUSINESS_TYPES = {
    '한식': {
        'sales_code': 'CS100001',
        'kakao_category': '한식',
        'naver_industry': '한식음식점',
        'ftc_keywords': ['한식', '한정식', '백반', '국밥']
    },
    '일식': {
        'sales_code': 'CS100002',
        'kakao_category': '일식',
        'naver_industry': '일식음식점',
        'ftc_keywords': ['일식', '초밥', '라멘', '돈까스']
    },
    # ... 8개 더
}
```

**ftc_keywords DB 정합**:
- FTC 정보공개서 업종명 → 우리 10종 매핑
- 예: '서양식' → 패스트푸드, '제과제빵' → 카페, '피자' → 패스트푸드

**3개 매핑 딕셔너리 단일 소스화**:
```python
# tools.py에서 import
_KAKAO_CATEGORY_MAP = {k: v['kakao_category'] for k, v in BUSINESS_TYPES.items()}
_SALES_CODE_MAP = {k: v['sales_code'] for k, v in BUSINESS_TYPES.items()}
_NAVER_INDUSTRY_MAP = {k: v['naver_industry'] for k, v in BUSINESS_TYPES.items()}
```

#### 9. dong_resolver SoT Helper

**validate_dong_code(strict=True)**:
```python
def validate_dong_code(dong_code: str, strict: bool = False):
    """마포구 16동 dong_code 검증"""
    VALID_DONGS = [
        '11440101', '11440102', '11440103', '11440104', '11440105',
        '11440106', '11440107', '11440108', '11440109', '11440110',
        '11440111', '11440112', '11440113', '11440114', '11440115',
        '11440116'
    ]
    
    if dong_code not in VALID_DONGS:
        if strict:
            raise ValueError(f"Invalid dong_code: {dong_code}")
        return False
    return True
```

**사용처**:
- API 요청 검증 (POST /simulate)
- ETL 파이프라인 데이터 정합성 체크
- Frontend dropdown 옵션 생성

#### 10. 데이터 품질 관리

**Null 비율 모니터링**:
```sql
SELECT 
    column_name,
    COUNT(*) as total,
    COUNT(*) - COUNT(column_name) as null_count,
    ROUND((COUNT(*) - COUNT(column_name))::numeric / COUNT(*) * 100, 2) as null_pct
FROM information_schema.columns
WHERE table_name = 'district_sales'
GROUP BY column_name
HAVING null_pct > 5.0;
```

**이상치 탐지**:
```python
def detect_outliers_iqr(df, column):
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)]
    return outliers
```

**데이터 정합성 체크**:
```python
# FK 무결성
assert all(dong_code in VALID_DONGS for dong_code in df['dong_code'].unique())

# 날짜 범위
assert df['year_quarter'].min() >= '2019Q1'
assert df['year_quarter'].max() <= current_quarter

# 양수 제약
assert (df['sales'] >= 0).all()
```

#### 성과 요약

- **DB 스키마**: 78 ORM, 1,019 컬럼, 32 FK
- **Alembic**: 마이그레이션 체인 복구, 3개 신규 테이블
- **ETL 파이프라인**: 5종 (지하철, 따릉이, ECOS, 핫스팟, 메타)
- **RAG 최적화**: MRR 0.785→0.931, NDCG 0.642→0.776, Hit@10 100%
- **Legal z-score**: FTC 업종별 통계 기반 (한신포차 z=-1.89 'safe')
- **ABM**: 5,000 에이전트, 3-Tier (S/A/B), LLM 통합
- **Brand 매핑**: corp_brand_resolver, 다업종/다brand 대응
- **API 개발**: /corp/operated-industries, /stores/count-by-dongs
- **SoT 통합**: business_type_mapping, dong_resolver

---

