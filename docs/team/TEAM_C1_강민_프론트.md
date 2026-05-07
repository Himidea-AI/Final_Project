### C1 — 프론트엔드 (강민)

**담당 영역**: React 애플리케이션 전체 아키텍처, UI/UX 설계, 상태 관리, 데이터 시각화

#### 복합 대시보드 아키텍처 구현 (2026-04~05)
- **12개 라우트 설계 및 구현**: Public (7) + Auth (5) 권한 분리 라우팅
  - IntroScene (랜딩), AboutPage, AccordionGallery (25 자치구 showcase), ContactPage, EnginePage
  - SimulatorDashboard (메인 입력 폼 - 10+ 필드)
  - DashboardHub (3-card 분할: Predict/Analyze/ABM)
  - SimulationHistoryDetail (저장된 시뮬레이션 조회), ManagerDetail (프로파일), HQCommandCenter
- **3-Pipeline 대시보드 통합**:
  - `/predict` (ML 결과 대시보드), `/analyze` (LLM 결과 대시보드), `/abm` (ABM 시뮬레이션 대시보드)
  - 각 파이프라인별 disabled/loading/error state 독립 관리
  - 총 **15+ 탭 컴포넌트** 구현 (Core Tabs + Sub-tabs)

#### 데이터 시각화 시스템 (Recharts 20+ 차트)
- **20개 이상 커스텀 차트 컴포넌트 구현**:
  - ClosureRateHistoryChart (폐업률 추이)
  - CoreDemographicDonut (핵심 인구통계 도넛)
  - CustomerFlowSegmentChart (고객 흐름 세그먼트)
  - BepCumulativeProfitChart (손익분기점 누적 수익)
  - AgentConfidenceRadar (에이전트 신뢰도 레이더)
  - ClosureRiskHeatmap (폐업 위험 히트맵)
  - LegalDistributionBar (법률 리스크 분포)
  - ScenarioForecastChart (시나리오 예측)
  - QuarterlySalesLineChart, CompetitorDensityMap, DemographicBreakdownBar, TimeSeriesTrendChart 등
- **5+ Core Tabs 구조**: AbmTab, DemographicTab, FinancialTab, InsightTab, LegalTab, MarketTab
- **10+ Sub-tab 드릴다운**: 
  - PredictCustomerFlowTab, PredictFinancialSimTab, PredictSalesForecastTab, PredictScenarioSimTab, PredictEmergingDistrictTab
  - AnalyzeAgentInsightTab, AnalyzeAiSummaryTab, AnalyzeLegalRiskTab, AnalyzeCompetitorTab, AnalyzeDemographicTab 등

#### 상태 관리 아키텍처 (Zustand 3-Store)
- **simulationStore** (메인 스토어 - 200+ 라인):
  - Dual-pipeline 대응: **prediction slice** + **analysis slice** 독립 관리
  - **Dual-track save 시스템** (2026-05-07): `savedForeseeId` (ML 결과) + `savedAIId` (LLM 결과) 분리 저장
    - 기존 단일 `savedHistoryId` 충돌 문제 해소
    - Predict tab과 Analyze tab이 독립적으로 save 가능
    - Legacy field backward compatibility 유지
  - **Real-time polling state**: progress, stage, status 실시간 추적
  - Retry helper + error recovery 로직
  - Form params 관리 (10+ 필드 validation)
- **abmStore**: ABM 시뮬레이션 전용 상태 관리
- **toastStore**: 전역 알림 시스템 (success/error/warning/info)

#### 인증 및 세션 관리 시스템 (Auth UX)
- **JWT 통합 인증**:
  - localStorage `spotter_auth = {user, brand, token}` 구조 설계
  - Token expiry 자동 감지 및 재로그인 유도
- **Axios interceptor 패턴**:
  - 모든 API 요청에 `X-Tenant-ID` + `Authorization` Bearer 자동 주입
  - Response interceptor로 401/403 중앙 처리
- **세션 복구 플로우**:
  - 401 감지 → localStorage 청소 → `/login?reason=session_expired&redirect=...` 리다이렉트
  - Boot 시 **zombie state self-heal**: user 있고 token 없으면 자동 청소 (데이터 정합성 보장)
- **권한 기반 라우팅**: Public/Auth/Superadmin 3-tier 접근 제어

#### 비동기 작업 처리 시스템 (Real-time Polling)
- **250ms 폴링 메커니즘**:
  - `/predict/{job_id}/status` — ML 파이프라인 진행률 (동별 progress)
  - `/analyze/llm/{job_id}/status` — LLM 파이프라인 진행률 (노드별 25%/50%/75%/100%)
- **진행률 UI 컴포넌트**:
  - ProgressBar + Stage indicator (Phase 0 → 1 → 2 → 2.5 → 3)
  - 동별 진행 상태 표시 (대기/진행중/완료)
  - Estimated time remaining 계산
- **AbortController 패턴**: 컴포넌트 unmount 시 진행중인 polling 요청 자동 취소 (메모리 누수 방지)
- **Error retry 로직**: 네트워크 실패 시 exponential backoff 재시도 (최대 3회)

#### 인터랙티브 지도 시스템 (Leaflet + react-leaflet)
- **마포구 16동 경계 시각화**:
  - GeoJSON 폴리곤 렌더링
  - 동별 hover/click 이벤트 처리
  - Selected state 하이라이트
- **동적 마커 시스템**:
  - 시뮬레이션 결과 기반 위치 마킹
  - 공실 좌표 시각화 (spot 점수 기반 색상 그라데이션)
  - Cluster 마커 (밀집 지역 자동 그룹화)
- **지도 컨트롤**: 
  - Zoom in/out, 중심 재설정
  - Layer toggle (경쟁사 마커 on/off)
  - Fullscreen mode

#### 테마 및 디자인 시스템 (2026-05)
- **Light/Dark mode 전역 토글**:
  - Tailwind CSS dark: prefix 활용
  - localStorage 테마 저장 (사용자 선호도 유지)
  - 시스템 테마 감지 (prefers-color-scheme)
- **Deep Blue palette 디자인**:
  - 9 페르소나 PNG 매핑 (사용자 유형별 아이콘)
  - 4-tier categorical palette (Primary/Secondary/Accent/Neutral)
  - Semantic color tokens (success/warning/error/info)
- **Tailwind CSS 커스터마이징**:
  - PostCSS 기반 유틸리티 우선 스타일링
  - Custom spacing/typography scale
  - Responsive breakpoints (sm/md/lg/xl/2xl)
- **Framer Motion 애니메이션**:
  - 페이지 전환 fade/slide 효과
  - 카드 hover/click 애니메이션
  - Loading skeleton 애니메이션

#### 파일 내보내기 시스템
- **PDF 생성 기능**:
  - jsPDF + html2canvas 통합
  - 대시보드 전체 → PDF 변환 (A4 multi-page)
  - 차트 SVG → Canvas 변환 후 고해상도 임베딩
- **Excel 내보내기**:
  - xlsx 라이브러리로 시뮬레이션 결과 스프레드시트화
  - 동별 데이터, 차트 데이터, 분석 결과 별도 시트 생성
  - 셀 포맷팅 (통화, 퍼센트, 날짜)
- **마크다운 렌더링**:
  - react-markdown으로 AI 분석 결과 표시
  - Code block syntax highlighting
  - Table, List, Bold/Italic 지원

#### 폼 검증 및 UX 최적화
- **복합 입력 폼 (SimulatorDashboard)**:
  - 10+ 필드 실시간 검증 (동 선택, 업종, 예산, 면적, 타겟 등)
  - 필드 간 의존성 처리 (업종 선택 시 브랜드 필터링)
  - Error 메시지 위치 최적화 (필드 하단 inline 표시)
- **브랜드 선택 UI**:
  - 운영 외 업종 disable + line-through 스타일
  - Disabled 필드 클릭 시 toast 설명 ("귀사가 운영하지 않는 업종입니다")
  - 다업종 corp 대응: 업종 선택 시 해당 업종 브랜드만 노출
- **ScopeHint 실시간 매장수**:
  - selectedDongs 변경 시 `/stores/count-by-dongs` API 즉시 호출
  - AbortController로 이전 요청 취소 (race condition 방지)
  - 로딩 spinner + fetch 실패 시 fallback 표시
- **IndicatorGrid 정합성**:
  - Chip 컴포넌트로 지표 표시 (색상 coded)
  - 단위 표시 일관성 (%, 원, 명, 개)
- **시나리오 v2 재구조화**:
  - 동적 마포구 선택 (1~4동 동시 시뮬레이션)
  - What-if 시나리오 UI (임대료 ±20%, 경쟁 진입 등)
  - 비교 모드 (Base vs Scenario side-by-side)

#### 반응형 디자인 및 접근성
- **모바일 최적화**:
  - Breakpoint별 레이아웃 조정 (sm: 640px, md: 768px, lg: 1024px)
  - Touch-friendly 버튼 크기 (최소 44px)
  - Drawer menu (모바일 네비게이션)
- **접근성 (a11y)**:
  - Semantic HTML (header/nav/main/footer)
  - ARIA labels (screen reader 지원)
  - Keyboard navigation (Tab, Enter, Esc)
  - Focus visible styles

#### 성과 요약
- **총 컴포넌트 수**: 100+ (페이지 12개 + 차트 20+ + 탭 15+ + 공통 컴포넌트 50+)
- **상태 관리**: Zustand 3 stores, 10+ slices
- **API 통합**: 15+ endpoints (polling, CRUD, export)
- **테마 시스템**: Light/Dark mode, 4-tier palette
- **애니메이션**: Framer Motion 30+ 컴포넌트
- **반응형**: 5 breakpoints 대응
- **Export**: PDF + Excel 멀티포맷

---

