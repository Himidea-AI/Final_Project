# Issues — 발견된 버그·미스매치·결함 기록

본 디렉토리는 운영 중 발견된 버그, 데이터 mismatch, schema drift, 노드 fail 등 **재현 가능한 결함**을 문서화합니다.

## 파일 네이밍

```
YYYY-MM-DD-<짧은-슬러그>.md
```

## 권장 문서 구조

각 issue 파일은 다음 섹션을 포함:

1. **증상** — 사용자/개발자가 본 현상
2. **진단 환경** — 브랜치/commit/버전, 인프라 검증 결과
3. **응답·로그 본문** — 진단에 사용된 raw 자료
4. **원인 분석** — 코드 라인 단위 추적
5. **영향 매트릭스** — 어떤 화면/탭/노드가 영향받는지
6. **우선순위별 수정안** — 작업량·효과·담당
7. **책임 영역** — AGENTS.md 기준 누가 fix할 영역인지
8. **검증 절차** — fix 후 어떻게 통과 확인하는지
9. **참고 자료** — 관련 PR, 다른 문서, plan, spec 링크

## 현재 등록된 issue

| 파일 | 우선순위 | 상태 | 담당 |
|---|---|---|---|
| [`2026-04-28-summary-tab-empty-cards.md`](./2026-04-28-summary-tab-empty-cards.md) | 🔴 High | 미해결 | B1·B2·C1 (A1 영역 외) |
| [`2026-04-28-end-to-end-data-flow-gaps.md`](./2026-04-28-end-to-end-data-flow-gaps.md) | 🔴 High (24건 drift) | 미해결 | B1·B2·C1 (P0 4건은 main.py + state.py + synthesis_node + SummaryTab) |
| [`2026-05-05-codebase-ultrareview.md`](./2026-05-05-codebase-ultrareview.md) | 🔴 Critical (P0 2건 + P1 24건 + P2 다수) | 미해결 | A1 일부 (services/SQL, DB 네이밍) + 타 팀원 (agents/simulation/frontend/infra) |

## 관련 디렉토리

- `docs/architecture/` — API 계약 + 아키텍처 문서
- `docs/abm-simulation/` — ABM 시뮬레이션 모델 리포트
- `docs/sales-imputation/` — 매출 결측 역추적 프로젝트
- `docs/superpowers/specs/` — 설계 문서 (구현 전 정의)
- `docs/superpowers/plans/` — 구현 계획서
- `docs/retrospective/` — 일/주 회고
