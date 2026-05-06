# 2026-05-06 — 슈퍼어드민 brand picker (P1, 진행중)

## 증상 / 요구

슈퍼어드민이 모든 가맹본부의 brand 를 자유롭게 선택해 시뮬 가능해야 함.
일반 master/manager 는 회원가입 시 매핑된 corp 의 brand 만 시뮬 가능.

현재 슈퍼어드민 (`role=superadmin`) 은 `simulation_ai`/`simulation_foresee` 의 **저장된 이력만** 조회 가능.
시뮬 신규 실행 시 brand picker 가 없어 자기 corp(`SPOTTER Admin`)의 brand 만 사용 가능 → 사실상 불가.

## 진단 환경

- 브랜치: `IM3-superadmin-brand-picker` (worktree, origin/dev base)
- 기준 commit: `c8e730dc` (origin/dev HEAD)
- DB: ftc_brand_franchise (~16K brand) + biz_brand_mapping (회원가입 본부 brand)

## 해결 — Backend `/admin/brands`

### 신규 라우트 (이번 PR)

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/admin/brands/industries` | 시뮬 가능 10종 메타 (label, cs_code) | superadmin |
| GET | `/admin/brands` | brand picker 목록 | superadmin |

`/admin/brands` 쿼리 파라미터:
- `q`: brand_name / corp_name 부분 일치 (ILIKE)
- `industry`: canonical key (한식·커피 등) — `BUSINESS_TYPE_MAPPING.keys()` 만 허용
- `page` / `size`: 페이징 (기본 1 / 50, 최대 200)

응답:
```json
{
  "total": 14571,
  "page": 1,
  "size": 50,
  "supported_industries": [{"key": "한식", "label": "한식음식점", "cs_code": "CS100001"}, ...],
  "items": [
    {
      "brand_name": "메가커피",
      "corp_name": "(주)앤하우스",
      "biz_number": null,
      "business_type": "커피",
      "cs_code": "CS100010",
      "industry_medium": "커피",
      "franchise_count": 3325,
      "avg_sales": 30000,
      "source": "ftc"
    }
  ]
}
```

### 데이터 소스 통합

`ftc_brand_franchise` (FTC 정보공개서) + `biz_brand_mapping` (회원가입 매핑) UNION:
- FTC: `brandNm`, `corpNm`, `indutyMlsfcNm`, `frcsCnt`, `avrgSlsAmt` — biz_number 없음
- biz_brand_mapping: `brand_name`, `company_name`, `biz_number`, `industry_medium` — biz_number 있음
- DISTINCT ON (brand_name, corp_name) 으로 중복 제거 (biz_brand_mapping 우선)

### 시뮬 가능 업종 필터링

`backend/src/config/business_type_mapping.py` 의 `BUSINESS_TYPE_MAPPING` 단일 source:
- 10종: 한식·중식·일식·양식·제과·패스트푸드·치킨·분식·호프·커피
- CS100001 ~ CS100010
- `ftc_keywords` 로 FTC `indutyMlsfcNm` 매칭 (예: 양식 → "서양식", 패스트푸드 → "피자" 흡수)

기타외식·편의점 등은 시뮬 흐름 미지원 → 응답에서 제외.

## 미해결 (다음 단계)

### 1. WIP 머지 후 superadmin bypass 필요

`IM3-263-ai-summary-layout` 브랜치 commit `66b874e7` 의 `_validate_and_resolve_brand` 함수가 dev 머지되면:
- master/manager: 운영 외 업종 차단됨 (정상)
- **superadmin: 차단되면 안 됨** — 모든 업종 자유

**필요 패치** (해당 PR 머지 후 follow-up):

```python
# backend/src/main.py
def _validate_and_resolve_brand(input_data, current_user=None):
    # superadmin: corp 검증·brand override 우회
    if current_user and current_user.role == "superadmin":
        return
    biz_number = input_data.biz_number or _resolve_user_biz_number(current_user)
    ...
```

3줄 추가. `corp_brand_resolver.get_corp_industries` 도 superadmin 시 `industries=None` 반환.

### 2. Frontend brand picker UI (다음 PR)

- `AuthContext.role === "superadmin"` 감지
- 시뮬 입력 폼에 brand picker 모달 (typeahead 검색)
- 선택 → `biz_number` + `brand_name` + `business_type` 자동 채움
- 매출 프리뷰: `franchise_count`, `avg_sales` 표시

### 3. 알려진 한계

- 동일 brand 가 FTC 여러 yr 또는 다른 source 에서 corp_name 미세하게 다르면 중복 노출 가능 (예: "(주)앤하우스" vs "앤하우스(주)")
- 응답 items 의 Python post-filter 가 SQL filter 와 불일치 → 페이지당 items 수 < size 가능. total 도 SQL 기준이라 페이지 수 계산 시 오차.
- 후속 개선: `_resolve_business_type` 로직을 SQL CASE 식 또는 캐시 컬럼으로 이전.

## 영향 매트릭스

| 영역 | 변경 |
|------|------|
| backend/src/api/admin_brands.py | 신규 라우터 |
| backend/src/main.py | router 등록 4줄 |
| tests/test_admin_brands.py | 15 케이스 신규 |
| frontend | 미변경 (다음 PR) |

## 검증

- ruff check / format: clean
- pytest: 15/15 PASS
- E2E (real DB): 14,571 brand 노출, 커피 6,850, 검색 정상

## 책임 영역

- A1 (찬영): `backend/src/api/`, services/ — 본 PR 범위
- 다음 단계 superadmin bypass: 본인 영역 내 (services + main.py)
- 프론트 brand picker: B1·B2 영역 (별도 협의)

## 참고

- 슈퍼어드민 role 도입: `33afb1aa feat(auth): superadmin role`
- corp_brand_resolver WIP: `66b874e7 feat(corp): 사업자번호 기반 운영 업종 dropdown 자동 차단` (IM3-263)
- 단일 source mapping: `backend/src/config/business_type_mapping.py`
- 이전 ultrareview: `docs/issues/2026-05-05-codebase-ultrareview.md`
