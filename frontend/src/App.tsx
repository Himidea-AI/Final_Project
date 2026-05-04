/**
 * 🚨 [AI 개발 규칙: ROUTE STRUCTURE PROTECTED]
 * ─────────────────────────────────────────────────────────────
 * 1. 이 파일의 <Routes> 구조와 "/" 경로(IntroScene)는 절대 수정/삭제 금지.
 * 2. 신규 대시보드 기능은 오직 "/simulator" 경로 내에서만 수정할 것.
 * 3. 'Cleanup' 명목으로 기존 import나 Route를 제거하지 마시오.
 * ─────────────────────────────────────────────────────────────
 */

/**
 * ═══════════════════════════════════════════════════════
 * SPOTTER — 프랜차이즈 상권분석 시뮬레이터 (Frontend)
 * ═══════════════════════════════════════════════════════
 *
 * [프로젝트 구조]
 *   App.tsx (이 파일)  — 전체 씬(Scene) 관리, 라우팅, 글로벌 헤더, 프리로더
 *   pages/JoinUs/      — 요금제 + 기업 회원가입 (별도 파일 분리)
 *   api/client.ts      — FastAPI 백엔드 통신 (USE_MOCK=true 시 Mock 데이터)
 *   types/index.ts     — API 요청/응답 TypeScript 타입 정의
 *
 * [씬(Scene) 라우팅]
 *   /            → IntroScene       (메인 타이포그래피 메뉴 + 파티클 배경)
 *   /about       → AboutPage        (프로젝트 소개 랜딩)
 *   /joinus      → JoinUsPage       (요금제 선택 + 기업 가입)
 *   /explore     → AccordionGallery (25개 구 아코디언 갤러리)
 *   /simulator   → SimulatorDashboard (시뮬레이션 대시보드)
 *   /contact     → ContactPage      (디지털 명함)
 *
 * [테마 시스템]
 *   - CSS Variables (index.css :root) — 라이트 모드 단일 (v5.0 2026-04-30 다크 폐기)
 *   - System A 배경/구조 (page #FFFFFF / 카드 #FFFFFF / surface slate-100 #F1F5F9 / border slate-300 #CBD5E1 — 2026-05-01 cool gray 전환)
 *   - System B 12색 팔레트 (모든 유의미한 색 — 데이터/상태/액센트/장식 단일 진실)
 *   - 시맨틱 클래스: bg-background, text-foreground, bg-card, text-primary, bg-success/warning/danger, var(--chart-1..4) 등
 *
 * [백엔드 연동]
 *   - api/client.ts의 USE_MOCK = true → Mock 데이터 반환 (프론트 독립 동작)
 *   - USE_MOCK = false로 변경 시 → FastAPI /api/predict, /api/analyze/llm 호출
 *   - SimulatorDashboard.runSim() → simulationStore.startSimulation() (IM3-259: /predict + /analyze/llm 분리 호출, /simulate 제거됨)
 *
 * [팀원 참고]
 *   - A1/B1: api/client.ts의 Mock 응답 형태 = 실제 API 응답과 동일해야 함
 *   - B2: SimResult.chartData 7개 항목 = 에이전트 노드별 점수
 *   - C2: Docker 배포 시 nginx.conf의 /api 프록시가 백엔드를 가리켜야 함
 */

import { useState, useEffect, useRef, useCallback, useId, lazy, Suspense } from 'react';
import {
  Routes,
  Route,
  useNavigate,
  useLocation,
  Outlet,
  Navigate,
  useOutletContext,
} from 'react-router-dom';
import { TransitionContext } from './contexts/TransitionContext';
import JoinUsPage from './pages/JoinUs/JoinUsPage';
import HQCommandCenter from './pages/HQCommandCenter';
import ManagerDetail from './pages/ManagerDetail';
import SimulationHistoryDetail from './pages/SimulationHistoryDetail';
import LoginPage from './pages/LoginPage';
import { AuthProvider, useAuth } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import { ToastProvider, useToast } from './components/Toast';
import type { SimulationOutput } from './types';
import { type SimResult, toSimResultViewModel } from './viewmodels/simResult';
// [H4] TabbedDashboard 직접 import 제거 — /dashboard 라우트로 분리 후 미사용.
// SimulationHistoryDetail 은 여전히 자체 import 로 사용 중 (H7 에서 정리 예정).
import { DashboardHub } from './components/SimulationResult/dashboard/DashboardHub';
import { DashboardConditionDrawer } from './components/SimulationResult/dashboard/DashboardConditionDrawer';
import {
  DetailModal,
  type DetailModalContent,
} from './components/SimulationResult/dashboard/shared/DetailModal';
import DashboardPredictPage from './pages/dashboard/DashboardPredictPage';
import DashboardAnalyzePage from './pages/dashboard/DashboardAnalyzePage';
import DashboardAbmPage from './pages/dashboard/DashboardAbmPage';
import { SimulationFloatingWidget } from './components/simulation/SimulationFloatingWidget';
import { AbmFloatingWidget } from './components/simulation/AbmFloatingWidget';
import { BeforeUnloadGuard } from './components/simulation/BeforeUnloadGuard';
import { ToastHost } from './components/simulation/ToastHost';
import { useCompletionToast } from './hooks/useCompletionToast';
import { useAbmCompletionToast } from './hooks/useAbmCompletionToast';
import { useSimulationStore } from './stores/simulationStore';
import { getLivePopulation } from './api/client';
import { useCombinedSimResult, buildCombinedResult } from './hooks/useCombinedSimResult';
import NetworkBackground from './components/NetworkBackground';
import WaveBackground from './pages/landing/WaveBackground';
import PulsatingDots from './components/ui/PulsatingDots';
// Phase C Round 2 — PDF 묶음 + Dashboard 묶음 추출 (정적 import 유지)

// Phase C Round 1 — 마케팅 페이지 4종 lazy 분리 (App.tsx에서 추출)
const IntroScene = lazy(() => import('./pages/landing/IntroScene'));
const AccordionGallery = lazy(() => import('./pages/landing/AccordionGallery'));
const AboutPage = lazy(() => import('./pages/landing/AboutPage'));
const ContactPage = lazy(() => import('./pages/landing/ContactPage'));

// Phase C Round 3 — 보조 컴포넌트 5종 추출 (GlobalNav 정적 / 나머지 3종 lazy)
import GlobalLimelightNav, { LogoutButton, WelcomeWidget } from './components/GlobalNav';
import type { DrawerKey } from './components/DetailDrawer';
const DetailDrawer = lazy(() => import('./components/DetailDrawer'));
const SpotterAgentWorkflow = lazy(() => import('./components/simulation/SpotterAgentWorkflow'));
const CommandPalette = lazy(() => import('./components/CommandPalette'));

import {
  ChevronRight,
  Sliders,
  MapPin,
  Play,
  X,
  Store,
  Terminal,
  UserCheck,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

import HybridSliderInput from './components/ui/HybridSliderInput';
import { SectionLabel } from './components/ui/SectionLabel';
import { FormField } from './components/ui/FormField';
import { ScopeHint } from './components/ui/ScopeHint';
import { ChipGroup } from './components/ui/ChipGroup';
import { Toggle } from './components/ui/Toggle';
import { StoreLocationInput } from './components/ui/StoreLocationInput';
import { ManagerListProvider } from './hooks/useManagerList';

/* ═══════════════════════════════════════════════════════
   DATA
   ═══════════════════════════════════════════════════════ */

const DONG_DATA: Record<string, string[]> = {
  강남구: [
    '신사동',
    '논현1동',
    '논현2동',
    '압구정동',
    '청담동',
    '삼성1동',
    '삼성2동',
    '대치1동',
    '대치2동',
    '대치4동',
    '역삼1동',
    '역삼2동',
    '도곡1동',
    '도곡2동',
    '개포1동',
    '개포2동',
    '개포3동',
    '개포4동',
    '일원본동',
    '일원1동',
    '수서동',
    '세곡동',
  ],
  강동구: [
    '강일동',
    '상일1동',
    '상일2동',
    '명일1동',
    '명일2동',
    '고덕1동',
    '고덕2동',
    '암사1동',
    '암사2동',
    '암사3동',
    '천호1동',
    '천호2동',
    '천호3동',
    '성내1동',
    '성내2동',
    '성내3동',
    '둔촌1동',
    '둔촌2동',
  ],
  강북구: [
    '삼양동',
    '미아동',
    '송중동',
    '송천동',
    '삼각산동',
    '번1동',
    '번2동',
    '번3동',
    '수유1동',
    '수유2동',
    '수유3동',
    '우이동',
    '인수동',
  ],
  강서구: [
    '염창동',
    '등촌1동',
    '등촌2동',
    '등촌3동',
    '화곡1동',
    '화곡2동',
    '화곡3동',
    '화곡4동',
    '화곡6동',
    '화곡8동',
    '가양1동',
    '가양2동',
    '가양3동',
    '발산1동',
    '공항동',
    '방화1동',
    '방화2동',
    '방화3동',
  ],
  관악구: [
    '보라매동',
    '청림동',
    '행운동',
    '낙성대동',
    '중앙동',
    '인헌동',
    '남현동',
    '서원동',
    '신원동',
    '서림동',
    '신사동',
    '신림동',
    '난향동',
    '조원동',
    '대학동',
    '은천동',
    '성현동',
    '청룡동',
    '난곡동',
    '삼성동',
    '미성동',
  ],
  광진구: [
    '중곡1동',
    '중곡2동',
    '중곡3동',
    '중곡4동',
    '능동',
    '구의1동',
    '구의2동',
    '구의3동',
    '광장동',
    '자양1동',
    '자양2동',
    '자양3동',
    '자양4동',
    '화양동',
    '군자동',
  ],
  구로구: [
    '신도림동',
    '구로1동',
    '구로2동',
    '구로3동',
    '구로4동',
    '구로5동',
    '가리봉동',
    '고척1동',
    '고척2동',
    '개봉1동',
    '개봉2동',
    '개봉3동',
    '오류1동',
    '오류2동',
    '항동',
  ],
  금천구: [
    '가산동',
    '독산1동',
    '독산2동',
    '독산3동',
    '독산4동',
    '시흥1동',
    '시흥2동',
    '시흥3동',
    '시흥4동',
    '시흥5동',
  ],
  노원구: [
    '월계1동',
    '월계2동',
    '월계3동',
    '공릉1동',
    '공릉2동',
    '하계1동',
    '하계2동',
    '중계본동',
    '중계1동',
    '중계2동',
    '중계3동',
    '상계1동',
    '상계2동',
    '상계3·4동',
    '상계5동',
    '상계6·7동',
    '상계8동',
    '상계9동',
    '상계10동',
  ],
  도봉구: [
    '쌍문1동',
    '쌍문2동',
    '쌍문3동',
    '쌍문4동',
    '방학1동',
    '방학2동',
    '방학3동',
    '창1동',
    '창2동',
    '창3동',
    '창4동',
    '창5동',
    '도봉1동',
    '도봉2동',
  ],
  동대문구: [
    '용신동',
    '제기동',
    '전농1동',
    '전농2동',
    '답십리1동',
    '답십리2동',
    '장안1동',
    '장안2동',
    '청량리동',
    '회기동',
    '휘경1동',
    '휘경2동',
    '이문1동',
    '이문2동',
  ],
  동작구: [
    '노량진1동',
    '노량진2동',
    '상도1동',
    '상도2동',
    '상도3동',
    '상도4동',
    '흑석동',
    '사당1동',
    '사당2동',
    '사당3동',
    '사당4동',
    '사당5동',
    '대방동',
    '신대방1동',
    '신대방2동',
  ],
  마포구: [
    '공덕동',
    '아현동',
    '도화동',
    '용강동',
    '대흥동',
    '염리동',
    '신수동',
    '서강동',
    '서교동',
    '합정동',
    '망원1동',
    '망원2동',
    '연남동',
    '성산1동',
    '성산2동',
    '상암동',
  ],
  서대문구: [
    '충현동',
    '천연동',
    '북아현동',
    '신촌동',
    '연희동',
    '홍제1동',
    '홍제2동',
    '홍제3동',
    '홍은1동',
    '홍은2동',
    '남가좌1동',
    '남가좌2동',
    '북가좌1동',
    '북가좌2동',
  ],
  서초구: [
    '서초1동',
    '서초2동',
    '서초3동',
    '서초4동',
    '잠원동',
    '반포본동',
    '반포1동',
    '반포2동',
    '반포3동',
    '반포4동',
    '방배본동',
    '방배1동',
    '방배2동',
    '방배3동',
    '방배4동',
    '양재1동',
    '양재2동',
    '내곡동',
  ],
  성동구: [
    '왕십리2동',
    '왕십리도선동',
    '마장동',
    '사근동',
    '행당1동',
    '행당2동',
    '응봉동',
    '금호1가동',
    '금호2·3가동',
    '금호4가동',
    '옥수동',
    '성수1가1동',
    '성수1가2동',
    '성수2가1동',
    '성수2가3동',
    '송정동',
    '용답동',
  ],
  성북구: [
    '성북동',
    '삼선동',
    '동선동',
    '돈암1동',
    '돈암2동',
    '안암동',
    '보문동',
    '정릉1동',
    '정릉2동',
    '정릉3동',
    '정릉4동',
    '길음1동',
    '길음2동',
    '종암동',
    '월곡1동',
    '월곡2동',
    '장위1동',
    '장위2동',
    '장위3동',
    '석관동',
  ],
  송파구: [
    '풍납1동',
    '풍납2동',
    '거여1동',
    '거여2동',
    '마천1동',
    '마천2동',
    '방이1동',
    '방이2동',
    '오륜동',
    '오금동',
    '송파1동',
    '송파2동',
    '석촌동',
    '삼전동',
    '가락본동',
    '가락1동',
    '가락2동',
    '문정1동',
    '문정2동',
    '장지동',
    '위례동',
    '잠실본동',
    '잠실2동',
    '잠실3동',
    '잠실4동',
    '잠실6동',
    '잠실7동',
  ],
  양천구: [
    '목1동',
    '목2동',
    '목3동',
    '목4동',
    '목5동',
    '신월1동',
    '신월2동',
    '신월3동',
    '신월4동',
    '신월5동',
    '신월6동',
    '신월7동',
    '신정1동',
    '신정2동',
    '신정3동',
    '신정4동',
    '신정6동',
    '신정7동',
  ],
  영등포구: [
    '영등포본동',
    '영등포동',
    '여의동',
    '당산1동',
    '당산2동',
    '도림동',
    '문래동',
    '양평1동',
    '양평2동',
    '신길1동',
    '신길3동',
    '신길4동',
    '신길5동',
    '신길6동',
    '신길7동',
    '대림1동',
    '대림2동',
    '대림3동',
  ],
  용산구: [
    '후암동',
    '용산2가동',
    '남영동',
    '청파동',
    '원효로1동',
    '원효로2동',
    '효창동',
    '용문동',
    '한강로동',
    '이촌1동',
    '이촌2동',
    '이태원1동',
    '이태원2동',
    '한남동',
    '서빙고동',
    '보광동',
  ],
  은평구: [
    '녹번동',
    '불광1동',
    '불광2동',
    '갈현1동',
    '갈현2동',
    '구산동',
    '대조동',
    '응암1동',
    '응암2동',
    '응암3동',
    '역촌동',
    '신사1동',
    '신사2동',
    '증산동',
    '수색동',
    '진관동',
  ],
  종로구: [
    '청운효자동',
    '사직동',
    '삼청동',
    '부암동',
    '평창동',
    '무악동',
    '교남동',
    '가회동',
    '종로1·2·3·4가동',
    '종로5·6가동',
    '이화동',
    '혜화동',
    '창신1동',
    '창신2동',
    '창신3동',
    '숭인1동',
    '숭인2동',
  ],
  중구: [
    '소공동',
    '회현동',
    '명동',
    '필동',
    '장충동',
    '광희동',
    '을지로동',
    '신당동',
    '다산동',
    '약수동',
    '청구동',
    '신당5동',
    '동화동',
    '황학동',
    '중림동',
  ],
  중랑구: [
    '면목본동',
    '면목2동',
    '면목3·8동',
    '면목4동',
    '면목5동',
    '면목7동',
    '상봉1동',
    '상봉2동',
    '중화1동',
    '중화2동',
    '묵1동',
    '묵2동',
    '망우본동',
    '망우3동',
    '신내1동',
    '신내2동',
  ],
};

/* ═══════════════════════════════════════════════════════
   BUSINESS TYPE DATA — 시뮬레이터 입력 옵션 (Frontend Mockup)
   ⚠️ 백엔드 연동 전 디자인 전용. SimulationInput 페이로드 확장 합의 필요.
   ⚠️ 표시는 한글 이름만, 실제 PostgreSQL 연동 시 CS코드 매핑 추가 예정
        CS100001 한식음식점 / CS100002 중식음식점 / CS100003 일식음식점 /
        CS100004 양식음식점 / CS100005 제과점 / CS100006 패스트푸드점 /
        CS100007 치킨전문점 / CS100008 분식전문점 / CS100009 호프-간이주점 /
        CS100010 커피-음료
   ═══════════════════════════════════════════════════════ */
const BUSINESS_TYPES = [
  '한식음식점',
  '중식음식점',
  '일식음식점',
  '양식음식점',
  '제과점',
  '패스트푸드점',
  '치킨전문점',
  '분식전문점',
  '호프-간이주점',
  '커피-음료',
];

/**
 * UI 라벨 → 백엔드 _SALES_CODE_MAP 키 변환.
 * backend/src/agents/tools.py의 _SALES_CODE_MAP(CS100001~CS100010)과 1:1 매칭.
 * v12.8에서 누락 5개(중식/일식/양식/패스트푸드/분식) 추가 + 치킨·제과 잘못된 CS코드 교정 완료.
 */
const BUSINESS_TYPE_BACKEND_KEY: Record<string, string> = {
  한식음식점: '한식',
  중식음식점: '중식',
  일식음식점: '일식',
  양식음식점: '양식',
  제과점: '제과점',
  패스트푸드점: '패스트푸드',
  치킨전문점: '치킨',
  분식전문점: '분식',
  '호프-간이주점': '호프',
  '커피-음료': '커피',
};

/** Backend short key → UI 풀 라벨 역매핑. mount 시 store.params.business_type 복원용. */
const FRONTEND_LABEL_FROM_BACKEND_KEY: Record<string, string> = Object.fromEntries(
  Object.entries(BUSINESS_TYPE_BACKEND_KEY).map(([k, v]) => [v, k]),
);

// UI 업종 라벨 → CS 업종 코드 (demographic 연령/성별 분석 업종 필터링용)
const BUSINESS_TYPE_CS_CODE: Record<string, string> = {
  한식음식점: 'CS100001',
  중식음식점: 'CS100002',
  일식음식점: 'CS100003',
  양식음식점: 'CS100004',
  제과점: 'CS100005',
  패스트푸드점: 'CS100006',
  치킨전문점: 'CS100007',
  분식전문점: 'CS100008',
  '호프-간이주점': 'CS100009',
  '커피-음료': 'CS100010',
};

const PRICE_RANGES = [
  { label: '5천원 이하', value: 'under5k' },
  { label: '5천-1만', value: '5to10k' },
  { label: '1-2만', value: '10to20k' },
  { label: '2만 이상', value: 'over20k' },
];

const OPERATING_HOURS_OPTIONS = ['오전', '점심', '저녁', '심야'];

/* ═══════════════════════════════════════════════════════
   DRILL-DOWN DRAWER — DrawerKey 타입은 ./components/DetailDrawer 로 이동 (Phase C Round 3)
   ═══════════════════════════════════════════════════════ */

/* ═══════════════════════════════════════════════════════
   Scene 3: Simulator Dashboard — 시뮬레이션 대시보드
   ═══════════════════════════════════════════════════════
   [상태 플로우]
   idle    → 조건 입력 대기 (좌측 패널: 구/동 드롭다운, 반경, 임대료)
   loading → RUN SIMULATION 클릭 → API 호출 + 로딩 스트리밍 텍스트
   result  → 하이엔드 대시보드 (StatCard, SVG 차트, 레이더, 테이블, AI 인사이트)

   [백엔드 연동 (api/client.ts)]
   runSim() → simulationStore.startSimulation() (IM3-259: runPredict + runAnalyzeLlm 병렬, /simulate 제거)
   응답 → useCombinedSimResult hook 으로 SimulationOutput 호환 합성 → UI 바인딩
   부분 실패 시 retryPrediction/retryAnalysis 로 슬라이스 재시도

   [팀원 참고 — B1/A1]
   SimulationOutput.comparison 배열 → 동별 비교 테이블 데이터
   SimulationOutput.legal_risks 배열 → AI 인사이트 법률 경고
   SimulationOutput.market_report → 7개 항목별 차트 데이터 (backend main.py:308)
*/

/**
 * SimulatorDashboard — 시뮬레이션 분석 결과 대시보드
 * idle → loading(Progress Bar) → result(KPI + 차트 + 테이블)
 * API 실패 시 에러 토스트 + idle 복귀 (mock 폴백 제거됨 — B2 수지니 협의 결과)
 */
function SimulatorDashboard({
  reportState,
  setReportState,
}: {
  reportState: string;
  setReportState: (s: 'idle' | 'loading' | 'result') => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();

  // RUN 버튼 disabled 의 진실 — store.status. reportState='loading' 좀비 회귀 방지
  // (RUN 직후 /dashboard 로 이동하므로 reportState 초기화 동선 없음 → 시뮬 완료 후
  // 사용자가 simulator 로 복귀 시 'loading' 잔존하면 RUN 영구 잠금).
  const storeStatus = useSimulationStore((s) => s.status);

  // Drawer "조건 수정" 진입 시 폼 자동 채움 — store.params 에서 mount 시 1회 capture.
  // useState lazy init 으로 최초 render 만 평가. 이후 사용자가 폼 변경해도 영향 없음.
  // store.params 단위: monthly_rent / initial_capital 은 원 단위 → 만원 단위로 변환.
  const [initParams] = useState(() => useSimulationStore.getState().params);

  const [radius, setRadius] = useState(initParams?.commercial_radius ?? 500);
  // 자사 영업구역 거리(m) — 가맹사업법 제12조의4 정량 룰. 미입력 시 backend 기본 임계값.
  const [territoryRadius, setTerritoryRadius] = useState(initParams?.territory_radius_m ?? 250);
  const [budget, setBudget] = useState(
    initParams?.monthly_rent != null ? Math.round(initParams.monthly_rent / 10000) : 200,
  );
  const [weighted, setWeighted] = useState(initParams?.population_weight ?? false);
  // loadingText/loadingProgress state는 로딩 UI 제거(2026-04-28)와 함께 dead.
  // SimulationFloatingWidget이 store status를 직접 구독해 진행 표시.
  const { showToast } = useToast();
  const { user, brand } = useAuth();
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  // SimResult는 camelCase로 변환된 뷰 모델. IntegratedReport는 snake_case SimulationOutput을 직접 소비하므로 원본도 별도 보존.
  const [rawSimResult, setRawSimResult] = useState<SimulationOutput | null>(null);

  // 마포구 외 다른 자치구 미지원 — useState 트릭 제거하고 const 로 노출.
  // 향후 다른 구 확장 시 useState<GuName>('마포구') + setter 로 복원.
  const selectedGu = '마포구' as const;
  // [UX] 동 선택 1~4개 제한 — 파이프라인 성능 + 레이더 차트 가독성 한계
  const [selectedDongs, setSelectedDongs] = useState<string[]>(() => {
    const stored = initParams?.target_districts;
    if (stored && stored.length > 0) return stored.slice(0, 4);
    return DONG_DATA['마포구'].slice(0, 4);
  });
  const [dongDropdownOpen, setDongDropdownOpen] = useState(false);

  // FTC 업종 중분류 → 프론트 드롭다운 업종명 매핑
  const FTC_TO_FRONTEND_INDUSTRY: Record<string, string> = {
    한식: '한식음식점',
    중식: '중식음식점',
    일식: '일식음식점',
    서양식: '양식음식점',
    제과제빵: '제과점',
    패스트푸드: '패스트푸드점',
    피자: '패스트푸드점',
    치킨: '치킨전문점',
    분식: '분식전문점',
    주점: '호프-간이주점',
    커피: '커피-음료',
    '음료 (커피 외)': '커피-음료',
    '아이스크림/빙수': '커피-음료',
  };
  const defaultBizType =
    (brand?.industry_medium && FTC_TO_FRONTEND_INDUSTRY[brand.industry_medium]) || '커피-음료';
  // initParams.business_type 은 backend short key ("커피") 형식 — frontend 라벨로 역매핑.
  const [businessType, setBusinessType] = useState(
    initParams?.business_type
      ? (FRONTEND_LABEL_FROM_BACKEND_KEY[initParams.business_type] ?? defaultBizType)
      : defaultBizType,
  );
  // 로그인 후 brand 정보가 비동기 로드되면 업종 자동 반영.
  // 단, store.params 에서 이미 복원된 경우 (drawer "조건 수정" 진입) skip — 사용자 의도 보존.
  useEffect(() => {
    if (initParams?.business_type) return;
    if (brand?.industry_medium) {
      const mapped = FTC_TO_FRONTEND_INDUSTRY[brand.industry_medium];
      if (mapped) setBusinessType(mapped);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brand?.industry_medium]);
  const [businessTypeOpen, setBusinessTypeOpen] = useState(false);
  const [storeArea, setStoreArea] = useState(initParams?.store_area ?? 15); // 평
  const [targetPrice, setTargetPrice] = useState(initParams?.target_price_range ?? '5to10k');
  const [operatingHours, setOperatingHours] = useState<string[]>(
    initParams?.operating_hours ?? ['점심', '저녁'],
  );
  const [isWorkflowOpen, setIsWorkflowOpen] = useState(false);
  const [initialCapital, setInitialCapital] = useState(
    initParams?.initial_capital != null ? Math.round(initParams.initial_capital / 10000) : 5000,
  ); // 만원

  // [customer_revenue] 타겟 고객 프로필 — A1 찬영 P1-C 연동. 빈 선택 = 전체 고객
  const [targetAgeGroups, setTargetAgeGroups] = useState<string[]>(
    initParams?.target_age_groups ?? [],
  );
  const [targetGender, setTargetGender] = useState<'male' | 'female' | null>(
    initParams?.target_gender ?? null,
  );
  const [targetTimeSlots, setTargetTimeSlots] = useState<string[]>(
    initParams?.target_time_slots ?? [],
  );
  const [targetDayType, setTargetDayType] = useState<'weekday' | 'weekend' | null>(
    initParams?.target_day_type ?? null,
  );
  const [targetMonthlySales, setTargetMonthlySales] = useState<number | null>(
    initParams?.target_monthly_sales ?? null,
  );

  // 출점 후보지 좌표 — 학교환경위생정화구역(rule_school_zone) 거리 룰 트리거.
  // 미입력 (둘 다 null) 시 backend 가 보수적 caution. 주점(pub) 외 업종은 좌표 영향 없음.
  const [storeLat, setStoreLat] = useState<number | null>(null);
  const [storeLon, setStoreLon] = useState<number | null>(null);
  const handleLocationChange = useCallback((nextLat: number | null, nextLon: number | null) => {
    setStoreLat(nextLat);
    setStoreLon(nextLon);
  }, []);

  // [customer_segment 미리보기] 코드는 dev 머지 시 통합되었으나 hook 파일 부재 + 결과 변수 미사용
  // 으로 제거. 향후 재도입 시 frontend/src/hooks/useCustomerSegmentPreview.ts 와 InsightsGrid 의
  // segment prop 와이어링 함께 복원 필요.

  // [A1] 유동인구 실시간 데이터
  const [popData, setPopData] = useState<any>(null);

  useEffect(() => {
    if (reportState !== 'result') return;
    let cancelled = false;
    const fetchPop = async () => {
      try {
        // 마포 16동 전체 fetch — 비교 모드(winnerDistrict + top3 candidates)에서
        // selectedDongs 외 후보 동의 popData도 매칭 가능하도록. 인자 미지정 시
        // backend(main.py:1071, population_api.py:91)가 16동 자동 반환.
        // 이전엔 getLivePopulation(selectedDongs)로 사용자 선택 동만 fetch해
        // 후보 동들이 dong_details에 빠지고 frontend traffic이 '—' 표시되던 버그.
        const data = await getLivePopulation();
        if (!cancelled) setPopData(data);
      } catch (e) {
        console.error('유동인구 API 실패:', e);
      }
    };
    fetchPop();
    return () => {
      cancelled = true;
    };
  }, [reportState]);

  // [v8.0/v8.1] Drill-down Drawer + 테이블 행 확장 + 정렬 상태
  const [activeDrawer, setActiveDrawer] = useState<DrawerKey>(null);
  const [selectedLegalType, setSelectedLegalType] = useState<string | null>(null);

  const toggleOperatingHour = useCallback((hour: string) => {
    setOperatingHours((prev) =>
      prev.includes(hour) ? prev.filter((h) => h !== hour) : [...prev, hour],
    );
  }, []);

  // [customer_revenue] Set 기반 토글 — 중복 방지. 빈 배열 = 전체 선택 (predict 스펙).
  const toggleTargetAge = useCallback((age: string) => {
    setTargetAgeGroups((prev) =>
      prev.includes(age) ? prev.filter((a) => a !== age) : [...prev, age],
    );
  }, []);
  const toggleTargetTime = useCallback((slot: string) => {
    setTargetTimeSlots((prev) =>
      prev.includes(slot) ? prev.filter((s) => s !== slot) : [...prev, slot],
    );
  }, []);
  // monthly_sales 입력 clamp: 음수/NaN 방어 — 빈 문자열은 null 유지 (전체 비율만 반환)
  const handleMonthlySalesChange = useCallback((raw: string) => {
    if (raw.trim() === '') {
      setTargetMonthlySales(null);
      return;
    }
    const n = Number(raw.replace(/[^0-9]/g, ''));
    if (!Number.isFinite(n) || n < 0) {
      setTargetMonthlySales(null);
      return;
    }
    setTargetMonthlySales(n);
  }, []);

  // 결과 화면 진입 시 스크롤을 맨 위로 리셋 (리포트 최상단부터 보이도록)
  const dashboardRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (reportState === 'result' && dashboardRef.current) {
      dashboardRef.current.scrollTop = 0;
    }
  }, [reportState]);

  // [R2] 마운트 시 store 에서 복원 — legacy 호환만 유지 (rawSimResult/simResult 로컬 state).
  // simulator 페이지는 input 전용 — result 상태 transition 안 함 (/dashboard 라우트가 담당).
  // 옛 dashboard JSX 제거(commit edfd4d7) 후속: setReportState('result') 호출 제거 →
  // /dashboard 에서 BACK 시 빈 outline 박스만 보이던 회귀 차단.
  useEffect(() => {
    const s = useSimulationStore.getState();
    const combined = buildCombinedResult(
      s.prediction.data,
      s.analysis.data,
      s.params?.target_district ?? undefined,
    );
    if (s.status === 'done' && combined) {
      setRawSimResult(combined);
      setSimResult(toSimResultViewModel(combined));
    }
    // mount 1회만
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // [H4] 옛 popstate 가로채기 effect 제거 — Hub Redesign 으로 시뮬 완료 시 navigate('/dashboard')
  // 가 react-router history 를 정상 관리. pushState 와 navigate replace 가 race 되어 카드 hub 가
  // 잠깐 떴다가 popstate listener 가 dismissResult 호출 → /simulator 로 복귀 → 옛 화면 표시.
  // /dashboard 에서 뒤로가기 시 react-router 가 자연스럽게 /simulator 로 이동 (popstate 가로채기 불필요).

  // [H4] 시뮬 완료 시 /dashboard 로 자동 이동 — TabbedDashboard 직접 렌더 대신 라우트 분리.
  // navigatedForResultRef: 동일 result 인스턴스에 대해 한 번만 navigate. 사용자가 /dashboard
  // 에서 뒤로가기 → /simulator 복귀 시 mount-restore 가 다시 rawSimResult 를 채워도 재navigate 안 함.
  // 새 시뮬 완료 시 setRawSimResult(simRes) 로 reference 가 바뀌면 ref 비교 실패 → navigate 재발동.
  // location.state.intent === 'edit' (DashboardConditionDrawer 의 "조건 수정" 버튼) → auto-redirect
  // skip. 사용자가 명시적으로 simulator 로 들어왔으니 다시 dashboard 로 튕기지 않음.
  const navigatedForResultRef = useRef<SimulationOutput | null>(null);
  useEffect(() => {
    const intent = (location.state as { intent?: string } | null)?.intent;
    if (intent === 'edit') return;
    if (rawSimResult && navigatedForResultRef.current !== rawSimResult) {
      navigatedForResultRef.current = rawSimResult;
      navigate('/dashboard', { replace: true });
    }
  }, [rawSimResult, navigate, location.state]);

  const MAX_DONGS = 4;

  const toggleDong = useCallback(
    (dong: string) => {
      // setState updater 함수는 순수해야 함. side effect (showToast) 를 안에 두면
      // React 18 StrictMode/concurrent mode 가 updater 를 여러 번 호출할 때
      // toast 가 여러 번 떠 "무한 에러 메시지" 처럼 보임.
      // → flag 로 의도 기록, setSelectedDongs 호출 후 외부에서 showToast 한 번만.
      let hitLimit = false;
      setSelectedDongs((prev) => {
        if (prev.includes(dong)) {
          if (prev.length <= 1) return prev; // 최소 1개
          return prev.filter((d) => d !== dong);
        }
        if (prev.length >= MAX_DONGS) {
          hitLimit = true;
          return prev;
        }
        return [...prev, dong];
      });
      if (hitLimit) {
        showToast('info', `동은 최대 ${MAX_DONGS}개까지 선택할 수 있습니다.`);
      }
    },
    [showToast],
  );

  // [UX] "전체" 버튼 → "최대 4개 채우기" 토글로 의미 변경.
  // 4개 이미 선택 상태면 첫 1개만 남기고 해제 (all selected 의미 유지).
  const toggleAllDongs = useCallback(() => {
    const all = DONG_DATA[selectedGu];
    if (selectedDongs.length >= MAX_DONGS) {
      setSelectedDongs([all[0]]);
    } else {
      setSelectedDongs(all.slice(0, MAX_DONGS));
    }
  }, [selectedGu, selectedDongs]);

  const runSim = useCallback(async () => {
    // [C-2] 입력 검증 — 명확한 에러 메시지
    if (!selectedDongs || selectedDongs.length === 0) {
      showToast('error', '분석할 행정동을 먼저 선택해주세요.');
      return;
    }
    if (!user?.company_name) {
      showToast('error', '로그인된 브랜드 정보가 없습니다. 다시 로그인해주세요.');
      return;
    }
    setReportState('loading');
    // [C1 연동] 백엔드 SimulationInput 전 필드 전송.
    // business_type: UI 한글 라벨 → _SALES_CODE_MAP 키로 변환.
    // brand_name: 브랜드 자동매핑 결과 우선, 없으면 company_name 폴백.
    // lat/lon: 출점 후보지 좌표 (학교환경위생정화구역 거리 룰 트리거). 미입력 시 backend caution.
    const payload = {
      business_type: BUSINESS_TYPE_BACKEND_KEY[businessType] || businessType,
      brand_name: brand?.brand_name || user?.company_name || '',
      target_district: selectedDongs[0] || '서교동',
      target_districts: selectedDongs.length > 0 ? selectedDongs : ['서교동'],
      existing_stores: [],
      monthly_rent: budget * 10000, // 만원 → 원
      scenarios: [],
      store_area: storeArea,
      target_price_range: targetPrice,
      operating_hours: operatingHours,
      initial_capital: initialCapital * 10000,
      commercial_radius: radius,
      territory_radius_m: territoryRadius,
      population_weight: weighted,
      industry_filter: BUSINESS_TYPE_CS_CODE[businessType] ?? null,
      // 출점 후보지 좌표 — pub 업종 학교환경위생정화구역 거리 룰. 미입력 시 backend caution.
      lat: storeLat,
      lon: storeLon,
      // [customer_revenue] target_* 5 필드. 미선택은 null/빈배열 = 전체 고객.
      target_age_groups: targetAgeGroups,
      target_gender: targetGender,
      target_time_slots: targetTimeSlots,
      target_day_type: targetDayType,
      target_monthly_sales: targetMonthlySales,
    };

    // 새 플로우 (2026-05-02): RUN 즉시 /dashboard 진입 → DashboardRunningPlaceholder 의
    // 슬라이스별 elapsed UI 노출. ML 또는 AI 한 슬라이스라도 done 되는 즉시 buildCombinedResult
    // 가 truthy 반환 → Hub 의 3 카드 표시 (미완료 슬라이스는 grayscale loading state).
    // 기존: await startSimulation 으로 predict 완료까지 /simulator 에서 대기. dead.
    void useSimulationStore.getState().startSimulation(payload);
    navigate('/dashboard');
  }, [
    setReportState,
    navigate,
    selectedDongs,
    budget,
    businessType,
    user?.company_name,
    brand?.brand_name, // brand_name 폴백 — 로그아웃 후 재로그인 시 새 brand 반영
    storeArea,
    targetPrice,
    operatingHours,
    initialCapital,
    radius,
    weighted,
    showToast,
    targetAgeGroups,
    targetGender,
    targetTimeSlots,
    targetDayType,
    targetMonthlySales,
    storeLat,
    storeLon,
  ]);

  // 로딩 UI 제거(2026-04-28)와 함께 store progress/stage 미러 useEffect도 dead → 제거.
  // SimulationFloatingWidget이 store를 직접 구독해 진행 상태 표시.

  // Light theme tokens (semantic, dark-mode hex retired)
  const textSecondary = 'text-muted-foreground';

  return (
    <div
      ref={dashboardRef}
      className="fixed inset-x-0 top-20 bottom-0 z-10 bg-card overflow-y-auto custom-scrollbar"
    >
      {/* Top bar — 페이지 타이틀(좌) + RUN 버튼(우).
          wrapper fixed top-20 = nav 80px 아래에서 시작 (nav 영역 침범 차단).
          mt-8 = wrapper 안에서 추가 32px 갭. sticky top-0 = wrapper 스크롤 시 wrapper 상단에 flush. */}
      <div className="sticky top-0 z-30 flex items-center justify-between px-8 py-4 mt-8 bg-card/90 backdrop-blur-xl">
        <h1 className="text-2xl md:text-3xl font-black text-foreground tracking-tight">
          SIMULATION SETUP
        </h1>
        <button
          onClick={runSim}
          disabled={storeStatus === 'running'}
          className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-bold text-sm tracking-wider transition-all duration-200 ${
            storeStatus === 'running'
              ? 'opacity-50 cursor-not-allowed bg-muted text-muted-foreground'
              : 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 hover:scale-[1.02] active:scale-[0.98]'
          }`}
        >
          <Play size={16} fill="currentColor" />
          RUN SIMULATION
        </button>
      </div>

      {/* Dashboard body — cockpit grid layout (좌 7 / 우 5 row 1, full-width row 2 / row 3).
          ScopeHint 를 row 사이 full-width 띠로 분리 → 핵심파라미터 키 축소되어 운영조건과 자연 매칭.
          default items-stretch 로 row 1 의 두 박스 키 같게 유지. */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-8 max-w-[1650px] mx-auto">
        {/* ─────── 핵심 파라미터 카드 — Cell row1·col5 (lg:order-2 로 시각 우측) ─────── */}
        <div className="lg:col-span-5 lg:order-2 box-glass rounded-2xl p-6 transition-all duration-700">
          <SectionLabel icon={MapPin} title="핵심 파라미터" sub="Core Parameters · 필수 항목" />
          {/* 단일 컬럼 flow — 내부 박스 wrapper 3개 제거 (강조용 bg-card+border-primary+shadow-xl 중첩 외피).
              box-glass 표면 위에 FormField 들 직접 배치. 균등 space-y-5 로 시각 리듬. */}
          <div className="space-y-5">
            {/* 분석 대상 — 구(고정) + 행정동(드롭다운) */}
            <FormField label="분석 대상" icon={MapPin}>
              <div className="space-y-2">
                {/* 구 — 고정 (explore에서 선택된 구, 변경 불가) */}
                <div className="px-3 h-10 rounded-lg border border-border bg-card flex items-center justify-between">
                  <span className="text-sm text-foreground">{selectedGu}</span>
                  <span className="text-[0.625rem] text-muted-foreground uppercase tracking-wider opacity-70">
                    선택됨
                  </span>
                </div>

                {/* 행정동 선택 드롭다운 */}
                <div className="relative">
                  <button
                    onClick={() => {
                      setDongDropdownOpen(!dongDropdownOpen);
                      setBusinessTypeOpen(false);
                    }}
                    className="w-full flex items-center justify-between px-3 h-10 rounded-lg border border-border bg-card text-sm text-foreground hover:border-primary/50 transition-colors"
                  >
                    <span className="truncate">
                      {selectedDongs.length}/{MAX_DONGS}개 동 선택됨
                    </span>
                    <ChevronRight
                      size={14}
                      className={`text-muted-foreground transition-transform duration-200 shrink-0 ${
                        dongDropdownOpen ? 'rotate-90' : ''
                      }`}
                    />
                  </button>
                  {dongDropdownOpen && (
                    <div
                      className="absolute z-50 mt-1 w-full max-h-52 overflow-y-auto rounded-lg border border-border bg-card shadow-2xl custom-scrollbar"
                      style={{ overscrollBehavior: 'contain' }}
                    >
                      <button
                        onClick={toggleAllDongs}
                        className="w-full text-left px-3 py-2 text-xs font-medium border-b border-border transition-colors text-primary hover:bg-primary/10"
                      >
                        {selectedDongs.length >= MAX_DONGS
                          ? `전체 해제 (1개만 유지)`
                          : `최대 ${MAX_DONGS}개 채우기`}
                      </button>
                      {DONG_DATA[selectedGu].map((dong) => {
                        const checked = selectedDongs.includes(dong);
                        return (
                          <button
                            key={dong}
                            onClick={() => toggleDong(dong)}
                            className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                              checked
                                ? 'text-foreground hover:bg-muted'
                                : 'text-muted-foreground/60 hover:bg-muted hover:text-muted-foreground'
                            }`}
                          >
                            <div
                              className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                                checked
                                  ? 'bg-primary border-primary'
                                  : 'border-border bg-transparent'
                              }`}
                            >
                              {checked && (
                                <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                                  <path
                                    d="M1.5 4L3 5.5L6.5 2"
                                    stroke="white"
                                    strokeWidth="1.5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              )}
                            </div>
                            {dong}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </FormField>

            {/* 업종 */}
            <FormField label="업종" icon={Store}>
              <div className="relative">
                <button
                  onClick={() => {
                    setBusinessTypeOpen(!businessTypeOpen);
                    setDongDropdownOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-3 h-10 rounded-lg border border-border bg-card text-sm text-foreground hover:border-primary/50 transition-colors"
                >
                  <span>{businessType}</span>
                  <ChevronRight
                    size={14}
                    className={`text-muted-foreground transition-transform duration-200 ${
                      businessTypeOpen ? 'rotate-90' : ''
                    }`}
                  />
                </button>
                {businessTypeOpen && (
                  <div className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto rounded-lg border border-border bg-card shadow-2xl custom-scrollbar">
                    {BUSINESS_TYPES.map((type) => (
                      <button
                        key={type}
                        onClick={() => {
                          setBusinessType(type);
                          setBusinessTypeOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                          type === businessType
                            ? 'text-primary bg-primary/10'
                            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                        }`}
                      >
                        {type}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </FormField>

            {/* 유동인구 가중치 */}
            <FormField
              label="유동인구 가중치"
              info="ON: KT 통신 유동인구 데이터를 매출 예측에 반영. 카페/음식점은 ON 권장"
            >
              <div className="flex items-center justify-between bg-card border border-border rounded-lg px-4 h-10">
                <span className="text-xs text-muted-foreground">
                  {weighted ? '활성화' : '비활성화'}
                </span>
                <Toggle on={weighted} onChange={setWeighted} ariaLabel="유동인구 가중치" />
              </div>
            </FormField>
          </div>
          {/* (ScopeHint 는 row 2 full-width 띠로 이동됨 — 박스 키 균형 위해 2026-05-01) */}
        </div>

        {/* RUN 버튼은 상단 sticky 헤더 우측으로 이관됨 (2026-05-01) */}

        {/* ─────── ScopeHint 띠 — Cell row2 col-12 (lg:order-3).
            핵심파라미터 박스 안에서 분리되어 row 사이 full-width 시각 띠로 동적 피드백 노출. ─────── */}
        <div className="lg:col-span-12 lg:order-3">
          <ScopeHint selectedDongCount={selectedDongs.length} />
        </div>

        {/* ─────── 섹션 2: 운영 조건 — Cell row1·col7. p-5 + gap-3 으로 row 1 height 정상화 ─────── */}
        <div className="lg:col-span-7 lg:order-1 box-glass rounded-2xl p-5 transition-all duration-700">
          <SectionLabel icon={Sliders} title="운영 조건" sub="Operating Constraints · 입지·재무" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
            {/* 1. 상권 반경 */}
            <HybridSliderInput
              label="상권 반경"
              value={radius}
              onChange={setRadius}
              min={100}
              max={1500}
              step={50}
              unit="m"
              infoText="분석 대상 반경. 카페는 300~500m, 음식점은 500~1000m 권장"
              className="mb-0"
            />

            {/* 1-2. 자사 영업구역 거리 — 가맹사업법 제12조의4 정량 룰 */}
            <HybridSliderInput
              label="자사 영업구역"
              value={territoryRadius}
              onChange={setTerritoryRadius}
              min={100}
              max={1000}
              step={50}
              unit="m"
              infoText="자사 브랜드 인접 출점 표준 거리 (정보공개서·가맹계약서 기준). 메가커피 250m / 빽다방 350m / 이디야 500m 등"
              className="mb-0"
            />

            {/* 2. 임대료 예산 */}
            <HybridSliderInput
              label="임대료 예산"
              value={budget}
              onChange={setBudget}
              min={50}
              max={1000}
              step={10}
              unit="만원"
              infoText="월 임대료 예산. 마포구 평균 1층 기준 200~400만원"
              className="mb-0"
            />

            {/* 3. 매장 면적 */}
            <HybridSliderInput
              label="매장 면적"
              value={storeArea}
              onChange={setStoreArea}
              min={5}
              max={100}
              step={1}
              unit="평"
              infoText="공간 기반 수익성(평당 매출) 계산에 사용됩니다."
              className="mb-0"
            />

            {/* 4. 초기 자본금 */}
            <HybridSliderInput
              label="초기 자본금"
              value={initialCapital}
              onChange={setInitialCapital}
              min={1000}
              max={50000}
              step={100}
              unit="만원"
              infoText="권리금/보증금 제외, 인테리어 및 초기 운영비 기준입니다."
              minLabel="1천만"
              className="mb-0"
            />

            {/* 5. 목표 객단가 — col-span-1 (P3: 박스 wrap) */}
            <FormField label="목표 객단가" hint="단일 선택">
              <ChipGroup
                options={PRICE_RANGES.map((r) => ({ v: r.value, l: r.label }))}
                value={targetPrice}
                onChange={setTargetPrice}
                cols={2}
              />
            </FormField>

            {/* 6. 주 타겟 시간대 — boxed FormField */}
            <FormField label="주 타겟 시간대" hint="복수 선택">
              <ChipGroup
                multi
                options={OPERATING_HOURS_OPTIONS.map((h) => ({ v: h, l: h }))}
                value={operatingHours}
                onChange={toggleOperatingHour}
                cols={4}
              />
            </FormField>

            {/* 7. 출점 후보지 좌표 (선택) — 학교환경위생정화구역 거리 룰 트리거.
                미입력 시 backend rule_school_zone 이 보수적 caution 처리. 주점에서만 차단 영향. */}
            <div className="md:col-span-2">
              <FormField
                label="출점 후보지 좌표"
                icon={MapPin}
                hint="선택 사항"
                info="주점(pub)일 때 학교환경위생정화구역 200m 이내 여부를 체크합니다. 미입력 시 보수적 caution."
              >
                <StoreLocationInput lat={storeLat} lon={storeLon} onChange={handleLocationChange} />
              </FormField>
            </div>

            {/* 유동인구 가중치 토글은 섹션 1(핵심 파라미터)의 업종 박스 아래로 이관 —
                    좌측 분석 대상 박스 높이 매칭 + 공백 회피(2026-04-28). */}
          </div>
          <p
            className={`text-[0.625rem] mt-3 ${textSecondary} opacity-50 italic pt-2 border-t border-border`}
          >
            * 권리금/보증금 제외, 인테리어·초기 운영비 기준
          </p>
        </div>

        {/* ─────── 섹션 3: 타겟 페르소나 — Cell row3 full-width (lg:col-span-12 lg:order-4).
            row 2 우측 col-5 자리(RUN 버튼 이관 후 빈 공간)를 없애고 full-width 로 시원하게. ─────── */}
        <div className="lg:col-span-12 lg:order-4 box-glass rounded-2xl p-6 transition-all duration-700">
          <SectionLabel icon={UserCheck} title="타겟 고객" sub="Target Audience · 페르소나" />
          <div>
            <div className="flex items-baseline justify-end mb-3">
              <span className="text-[0.625rem] text-muted-foreground opacity-60">
                미선택 시 전체 고객 기준
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* 연령대 — 복수 선택 */}
              <FormField label="연령대" hint="복수 선택">
                <ChipGroup
                  multi
                  options={[
                    { v: '10대', l: '10대' },
                    { v: '20대', l: '20대' },
                    { v: '30대', l: '30대' },
                    { v: '40대', l: '40대' },
                    { v: '50대', l: '50대' },
                    { v: '60대이상', l: '60대+' },
                  ]}
                  value={targetAgeGroups}
                  onChange={toggleTargetAge}
                  cols={3}
                />
              </FormField>

              {/* 성별 — 단일 선택 (null = 전체) */}
              <FormField label="성별" hint="단일 선택">
                <ChipGroup
                  options={
                    [
                      { v: null, l: '전체' },
                      { v: 'male', l: '남성' },
                      { v: 'female', l: '여성' },
                    ] as const
                  }
                  value={targetGender}
                  onChange={setTargetGender}
                  cols={3}
                />
              </FormField>

              {/* 방문 시간대 — 복수 선택 */}
              <FormField label="방문 시간대" hint="복수 선택">
                <ChipGroup
                  multi
                  options={[
                    { v: 'time_00_06', l: '심야' },
                    { v: 'time_06_11', l: '오전' },
                    { v: 'time_11_14', l: '점심' },
                    { v: 'time_14_17', l: '오후' },
                    { v: 'time_17_21', l: '저녁' },
                    { v: 'time_21_24', l: '야간' },
                  ]}
                  value={targetTimeSlots}
                  onChange={toggleTargetTime}
                  cols={3}
                />
              </FormField>

              {/* 요일 — 단일 선택 */}
              <FormField label="요일" hint="단일 선택">
                <ChipGroup
                  options={
                    [
                      { v: null, l: '전체' },
                      { v: 'weekday', l: '평일' },
                      { v: 'weekend', l: '주말' },
                    ] as const
                  }
                  value={targetDayType}
                  onChange={setTargetDayType}
                  cols={3}
                />
              </FormField>
            </div>

            {/* 예상 월매출 — full-width */}
            <div className="mt-4">
              <FormField label="예상 월매출" hint="선택 사항">
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="예: 23150000 (원)"
                  value={
                    targetMonthlySales != null ? targetMonthlySales.toLocaleString('ko-KR') : ''
                  }
                  onChange={(e) => handleMonthlySalesChange(e.target.value)}
                  className="w-full h-10 px-3 rounded-lg text-xs font-mono tabular-nums bg-card border border-border text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/15 focus:outline-none transition-colors"
                />
                <p className="mt-1.5 text-[11px] text-muted-foreground/70">
                  입력 시 세그먼트 매출 금액 계산 (미입력 시 비율만 표시)
                </p>
              </FormField>
            </div>
          </div>
        </div>
        {/* /타겟 페르소나 카드 끝 */}

        {/* 옛 Visualization wrapper 제거 (commit edfd4d7 옛 dashboard 제거 후속).
            결과 화면은 /dashboard 라우트가 담당 — simulator 페이지는 input 전용. */}
      </div>

      {/* ==========================================
          AI Agent Workflow Drawer
          ========================================== */}
      <>
        <div
          className={`fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm transition-opacity duration-500 ${isWorkflowOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
          onClick={() => setIsWorkflowOpen(false)}
        />
        <div
          className={`fixed top-0 right-0 w-full md:w-[600px] h-full bg-card border-l border-border z-[101] shadow-2xl flex flex-col transition-transform duration-[800ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${isWorkflowOpen ? 'translate-x-0' : 'translate-x-full'}`}
        >
          <div className="flex justify-between items-center p-6 border-b border-border bg-card">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                <Terminal className="w-4 h-4 text-primary" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-foreground tracking-tight">
                  LangGraph Execution Log
                </h2>
                <p className="text-[0.625rem] text-muted-foreground font-mono mt-0.5">
                  MULTI-AGENT PIPELINE
                </p>
              </div>
            </div>
            <button
              onClick={() => setIsWorkflowOpen(false)}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-border rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-6 bg-muted custom-scrollbar">
            {/* drawer 닫혀있으면 unmount — lazy chunk fetch 지연 + 내부 setTimeout 3개가
                보이지 않을 때 시작되는 것을 방지 (code-review #4) */}
            {isWorkflowOpen && (
              <Suspense fallback={null}>
                <SpotterAgentWorkflow />
              </Suspense>
            )}
          </div>
        </div>
      </>

      {/* [v8.0] Drill-down Drawer — KPI/차트 클릭 시 우측에서 슬라이드 인 */}
      <Suspense fallback={null}>
        <DetailDrawer
          isOpen={!!activeDrawer}
          onClose={() => {
            setActiveDrawer(null);
            setSelectedLegalType(null);
          }}
          drawerKey={activeDrawer}
          popData={popData}
          analysisMetrics={simResult?.analysis_metrics}
          legalRisks={simResult?.legalRisks}
          selectedLegalType={selectedLegalType}
        />
      </Suspense>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Phase C Round 3 — 5개 보조 컴포넌트 추출 완료:
   - GlobalNav (LogoutButton + GlobalLimelightNav) → ./components/GlobalNav
   - DetailDrawer → ./components/DetailDrawer (lazy)
   - SpotterAgentWorkflow → ./components/simulation/SpotterAgentWorkflow (lazy)
   - CommandPalette → ./components/CommandPalette (lazy)
   - TransitionContext + useTransition → ./contexts/TransitionContext
   ═══════════════════════════════════════════════════════ */

/* ═══════════════════════════════════════════════════════
   App — Root (전체 앱 진입점)
   ═══════════════════════════════════════════════════════
   [글로벌 상태]
   - isTransitioning: 씬 전환 시 800ms 암전 오버레이
   - isAppLoaded: 프리로더 완료 여부
   (다크 토글은 v5.0 폐기 — 라이트 단일)

   [글로벌 헤더]
   - 인트로 제외 모든 씬에 공통 표시
   - 좌: 로고+BACK / 우: GlobalLimelightNav
   - ※ AccordionGallery는 자체 3열 헤더를 사용 (중앙 인디케이터 포함)

   [프리로더]
   - 앱 최초 진입 시 3초간 5축 자이로스코프 홀로그램
   - 100% → warp-out 트랜지션 → main-scene-in → isAppLoaded=true → DOM 제거
*/

/** 현재 경로 → scene 이름 매핑 */
function pathToScene(
  pathname: string,
): 'intro' | 'about' | 'joinus' | 'accordion' | 'simulator' | 'contact' | 'hq' | 'login' {
  if (pathname === '/about') return 'about';
  if (pathname === '/joinus') return 'joinus';
  if (pathname === '/explore') return 'accordion';
  if (pathname === '/simulator') return 'simulator';
  if (pathname.startsWith('/dashboard')) return 'simulator';
  if (pathname === '/contact') return 'contact';
  if (pathname === '/hq') return 'hq';
  if (pathname === '/login') return 'login';
  return 'intro';
}

/**
 * DashboardOutlet — `/dashboard` nested route 의 layout shell.
 * - simResult / brandName / businessType / savedHistoryId 를 store + auth 로부터 읽어
 *   <Outlet context={...}> 로 자식 라우트(Hub/Predict/Analyze/Abm)에 전달.
 * - simResult 가 없으면 /simulator 로 redirect (시뮬 미실행 시 직접 진입 차단).
 * - DetailModal 도 여기서 host (자식 라우트가 openModal 로 띄우는 모달).
 */
/** 시뮬 진행중 + 데이터 미도착 상태에서 dashboard shell 안에 표시할 로딩 placeholder.
 *  IM3-259 분리 호출 — /predict (ML 예측) 와 /analyze/llm (AI 분석) 두 슬라이스의
 *  실측 progress 를 wave 차오름 + % 로 시각화. backend polling 기반 (가짜 시간 추정 0). */
function DashboardRunningPlaceholder() {
  const predStatus = useSimulationStore((s) => s.prediction.status);
  const anaStatus = useSimulationStore((s) => s.analysis.status);
  const predProgress = useSimulationStore((s) => s.prediction.progress);
  const anaProgress = useSimulationStore((s) => s.analysis.progress);

  return (
    <div className="relative flex h-full min-h-[60vh] flex-col items-center justify-center gap-6 overflow-hidden px-6">
      {/* IntroScene 과 동일 시각 언어 — Deep Blue 가로지르는 wave 캔버스. 마우스 호버 시 진폭 ↑.
          z-0 absolute, 본문 콘텐츠는 자연 stacking 으로 위에 떠있음. pointer-events-none 이라
          박스 인터랙션 무방해. */}
      <WaveBackground />

      <div className="relative z-10 flex items-center gap-3 text-lg font-semibold text-foreground">
        <span>시뮬레이션 진행 중</span>
        <PulsatingDots />
      </div>
      {/* 가로 배치 — sm 이상에서 두 박스 좌우 나란히. 모바일 (sm 미만) 에선 세로 fallback. */}
      <div className="relative z-10 flex w-full max-w-4xl flex-col gap-4 sm:flex-row">
        <SliceProgressRow
          status={predStatus}
          label="ML 예측"
          sublabel="매출 / 폐업률 (TCN + LightGBM)"
          progressRatio={predProgress}
        />
        <SliceProgressRow
          status={anaStatus}
          label="AI 분석"
          sublabel="멀티 에이전트 종합 판단 (LLM)"
          progressRatio={anaProgress}
        />
      </div>
      <p className="relative z-10 max-w-md text-center text-xs text-muted-foreground leading-relaxed">
        두 분석은 독립적으로 실행되며, 도착하는 대로 화면이 갱신됩니다.
      </p>
    </div>
  );
}

/** 박스 안 액체 wave animation — 3-layer wave + gradient body + surface sheen.
 *  fillHeight 가 progressRatio 따라 연속 차오름 → "물이 차오르는" 메타포.
 *  done 시: calm full fill + 1회 shimmer sweep. */
function HorizontalWaveBackground({
  status,
  progressRatio,
}: {
  status: 'idle' | 'running' | 'done' | 'error';
  progressRatio: number;
}) {
  // SVG defs id 충돌 방지 — 동일 페이지에 여러 박스가 있을 때 path id 유일성 확보.
  const uid = useId().replace(/:/g, '_');
  const deepId = `wave-deep-${uid}`;
  const midId = `wave-mid-${uid}`;
  const surfId = `wave-surf-${uid}`;

  // fillHeight = 표시 % 와 정확히 일치 — progressRatio * 100 직결.
  // running 중엔 hook 의 0.96 cap 으로 자연스럽게 max 96% (done 직전), done 시 100% 점프 + shimmer.
  // 시작 직후 (ratio≈0) wave 0% 인 게 정직 — 박스 border/icon 으로 running 인식 충분.
  const fillHeight = status === 'done' ? 100 : status === 'running' ? progressRatio * 100 : 0;

  // 진행률 클수록 표면 wave 잔잔해짐 — running 끝나갈 때 calm 전이 시각 신호.
  const surfaceOpacity = status === 'done' ? 0 : Math.max(0.5, 1 - progressRatio * 0.55);
  const showSurfaceWave = status === 'running';
  const isDone = status === 'done';

  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl"
      aria-hidden="true"
    >
      <div
        className="absolute bottom-0 left-0 right-0"
        style={{
          height: `${fillHeight}%`,
          // cubic-bezier(0.22,1,0.36,1) = ease-out-quart — 차오름 끝에서 부드럽게 정착.
          transition: 'height 600ms cubic-bezier(0.22,1,0.36,1)',
        }}
      >
        {/* Body — vertical gradient: 표면 옅음 → 바닥 진함 (수심 깊이감) */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(180deg, color-mix(in srgb, var(--primary) 7%, transparent) 0%, color-mix(in srgb, var(--primary) 18%, transparent) 60%, color-mix(in srgb, var(--primary) 26%, transparent) 100%)',
          }}
        />

        {/* Surface highlight — 수면 sheen (가운데 밝고 양 끝 fade) */}
        <div
          className="absolute left-0 right-0 top-0 h-px"
          style={{
            background:
              'linear-gradient(90deg, transparent 0%, color-mix(in srgb, var(--primary) 50%, transparent) 50%, transparent 100%)',
          }}
        />

        {/* Done shimmer — 완료 순간 1회 sweep highlight (퀄리티 폴리시) */}
        {isDone && (
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div
              className="absolute -inset-y-2 -left-1/3 w-1/3"
              style={{
                animation: 'water-shimmer 1.4s ease-out 1 forwards',
                background:
                  'linear-gradient(100deg, transparent 0%, color-mix(in srgb, white 38%, transparent) 50%, transparent 100%)',
              }}
            />
          </div>
        )}

        {/* Surface waves — 3 layer (deep slow / mid / surface fast) — running 시만.
            preserveAspectRatio=none 로 박스 너비에 stretch, 다른 phase·dur 로 swell. */}
        {showSurfaceWave && (
          <svg
            className="absolute -top-4 left-0 right-0 h-8 w-full"
            viewBox="0 0 1200 32"
            preserveAspectRatio="none"
            style={{
              opacity: surfaceOpacity,
              transition: 'opacity 700ms ease-out',
            }}
          >
            <defs>
              {/* Deep — 큰 진폭, 느린 layer (수심 깊은 너울) */}
              <path id={deepId} d="M0,16 Q200,4 400,16 T800,16 T1200,16 L1200,32 L0,32 Z" />
              {/* Mid — 중간 진폭/속도 */}
              <path id={midId} d="M0,18 Q150,9 300,18 T600,18 T900,18 T1200,18 L1200,32 L0,32 Z" />
              {/* Surface — 잔물결, 빠른 phase */}
              <path
                id={surfId}
                d="M0,22 Q100,15 200,22 T400,22 T600,22 T800,22 T1000,22 T1200,22 L1200,32 L0,32 Z"
              />
            </defs>

            {/* Deep — 14s 느린 너울, opacity 16% */}
            <use
              href={`#${deepId}`}
              x="-1200"
              fill="color-mix(in srgb, var(--primary) 16%, transparent)"
            >
              <animateTransform
                attributeName="transform"
                type="translate"
                from="0 0"
                to="1200 0"
                dur="14s"
                repeatCount="indefinite"
              />
            </use>
            <use href={`#${deepId}`} fill="color-mix(in srgb, var(--primary) 16%, transparent)">
              <animateTransform
                attributeName="transform"
                type="translate"
                from="0 0"
                to="1200 0"
                dur="14s"
                repeatCount="indefinite"
              />
            </use>

            {/* Mid — 9s, opacity 24% (가장 진한 layer — 시각 anchor) */}
            <use
              href={`#${midId}`}
              x="-1200"
              fill="color-mix(in srgb, var(--primary) 24%, transparent)"
            >
              <animateTransform
                attributeName="transform"
                type="translate"
                from="0 0"
                to="1200 0"
                dur="9s"
                repeatCount="indefinite"
              />
            </use>
            <use href={`#${midId}`} fill="color-mix(in srgb, var(--primary) 24%, transparent)">
              <animateTransform
                attributeName="transform"
                type="translate"
                from="0 0"
                to="1200 0"
                dur="9s"
                repeatCount="indefinite"
              />
            </use>

            {/* Surface — 5s 빠른 잔물결, opacity 12% */}
            <use
              href={`#${surfId}`}
              x="-1200"
              fill="color-mix(in srgb, var(--primary) 12%, transparent)"
            >
              <animateTransform
                attributeName="transform"
                type="translate"
                from="0 0"
                to="1200 0"
                dur="5s"
                repeatCount="indefinite"
              />
            </use>
            <use href={`#${surfId}`} fill="color-mix(in srgb, var(--primary) 12%, transparent)">
              <animateTransform
                attributeName="transform"
                type="translate"
                from="0 0"
                to="1200 0"
                dur="5s"
                repeatCount="indefinite"
              />
            </use>
          </svg>
        )}
      </div>
    </div>
  );
}

/** (b) 옵션 — 단계 사이 시간 보간. 진짜 progressRatio 가 변화 없는 동안 STAGE_DURATION_SEC
 *  가정으로 다음 step(25%p) 직전(headroom 1%p)까지 천천히 climb. 새 신호 도착 시 즉시 점프.
 *  ⚠️ 가짜 시간 추정 — 실측 (a 정통) 과 다름. "단계 멈춤" UX 회피용 절충 (2026-05-03 사용자 결정).
 *  cap = ceil(real * 4) / 4 - headroom 으로 다음 stage 절대 못 넘게 강제. */
const STAGE_DURATION_SEC = 50;
const STEP_HEADROOM = 0.01;

function useInterpolatedProgress(
  realProgress: number,
  status: 'idle' | 'running' | 'done' | 'error',
): number {
  const [display, setDisplay] = useState(realProgress);
  const lastReal = useRef({ value: realProgress, at: Date.now() });

  // realProgress 변화 시 즉시 점프 + 보간 시작점 갱신.
  useEffect(() => {
    if (realProgress !== lastReal.current.value) {
      lastReal.current = { value: realProgress, at: Date.now() };
      setDisplay(realProgress);
    }
  }, [realProgress]);

  // 시간 보간 timer — running 중에만. 250ms 마다 보간값 재계산.
  useEffect(() => {
    if (status !== 'running') return;
    const id = setInterval(() => {
      const { value: real, at } = lastReal.current;
      const elapsed = (Date.now() - at) / 1000;
      const interpolated = real + (elapsed / STAGE_DURATION_SEC) * 0.25;
      // 다음 0.25 배수 직전 - headroom — real=0 일 때 cap 음수 회귀(-1%) 차단 위해
      // floor(real*4)+1 로 항상 real 보다 큰 다음 quarter 보장.
      const nextQuarter = (Math.floor(real * 4) + 1) / 4;
      const cap = Math.min(1.0, nextQuarter - STEP_HEADROOM);
      // real 미만 역행 + cap 초과 둘 다 차단.
      setDisplay(Math.max(real, Math.min(interpolated, cap)));
    }, 250);
    return () => clearInterval(id);
  }, [status]);

  // done/error/idle 전이 시 real 값 즉시 반영 (cap 해제).
  useEffect(() => {
    if (status !== 'running') setDisplay(realProgress);
  }, [status, realProgress]);

  return display;
}

function SliceProgressRow({
  status,
  label,
  sublabel,
  progressRatio,
}: {
  status: 'idle' | 'running' | 'done' | 'error';
  label: string;
  sublabel: string;
  /** Real progress 0~1 — backend polling 으로 store 에 누적된 슬라이스 진행률. */
  progressRatio: number;
}) {
  // (b) 시간 보간 적용 — display 는 wave fillHeight + % 표시 둘 다 같은 값.
  const display = useInterpolatedProgress(progressRatio, status);
  const Icon = status === 'done' ? CheckCircle2 : status === 'error' ? AlertCircle : Loader2;
  const iconColor =
    status === 'done'
      ? 'text-success'
      : status === 'error'
        ? 'text-danger'
        : status === 'running'
          ? 'text-primary'
          : 'text-muted-foreground';
  const stateLabel =
    status === 'done' ? '완료' : status === 'error' ? '실패' : status === 'idle' ? '대기' : null;
  const stateLabelColor =
    status === 'done'
      ? 'text-success'
      : status === 'error'
        ? 'text-danger'
        : 'text-muted-foreground';
  const isRunning = status === 'running';

  // running 시 % — display(보간된 값) 사용. wave fillHeight 와 1:1 일치 유지.
  const progressPct = isRunning ? Math.round(display * 100) : null;

  return (
    <div className="relative flex min-h-[200px] min-w-0 flex-1 flex-col items-center justify-center gap-3 overflow-hidden rounded-2xl border border-border bg-card p-6 text-center transition-colors duration-500">
      <HorizontalWaveBackground status={status} progressRatio={display} />
      <Icon
        className={`relative h-7 w-7 shrink-0 ${iconColor} ${isRunning ? 'animate-spin' : ''}`}
      />
      <div className="relative">
        <div className="text-base font-bold text-foreground">{label}</div>
        <div className="mt-1 text-xs text-muted-foreground">{sublabel}</div>
      </div>
      {isRunning && progressPct !== null ? (
        // stage 라벨 표시 제거 — ML(한글) / AI(영문 노드명) 비대칭 + cluttered.
        // % + 차오름 wave 가 충분한 진행 신호. backend 의 stage 는 store 에 진단용으로만 보존.
        <div className="relative flex items-baseline gap-1 tabular-nums">
          <span className="text-2xl font-black text-primary">{progressPct}</span>
          <span className="text-base font-black text-primary">%</span>
        </div>
      ) : stateLabel ? (
        <div className={`relative text-sm font-bold ${stateLabelColor}`}>{stateLabel}</div>
      ) : null}
    </div>
  );
}

function DashboardOutlet() {
  const simResult = useCombinedSimResult();
  const savedHistoryId = useSimulationStore((s) => s.savedHistoryId);
  const status = useSimulationStore((s) => s.status);
  const params = useSimulationStore((s) => s.params);
  const { user, brand } = useAuth();
  const brandName = user?.company_name || brand?.brand_name || '';
  const businessType: string | null = null;

  const [modalContent, setModalContent] = useState<DetailModalContent | null>(null);
  const openModal = (content: DetailModalContent) => setModalContent(content);

  const [conditionDrawerOpen, setConditionDrawerOpen] = useState(false);

  // FloatingWidget 의 "시뮬레이터로 이동" 으로 시뮬 진행중에도 진입 가능하도록 변경.
  // 결과 없음 + 시뮬 미실행 → /simulator 로 복귀 (직접 URL 접근 차단).
  if (!simResult && status !== 'running') return <Navigate to="/simulator" replace />;

  return (
    <div
      data-dashboard-scroll
      className="fixed inset-x-0 top-20 bottom-0 overflow-y-scroll custom-scrollbar bg-background pb-16 text-foreground"
      style={{ overscrollBehaviorY: 'contain' }}
    >
      {simResult ? (
        <Outlet
          context={{
            simResult,
            brandName,
            businessType,
            savedHistoryId,
            openModal,
            openConditionDrawer: () => setConditionDrawerOpen(true),
          }}
        />
      ) : (
        <DashboardRunningPlaceholder />
      )}
      <DetailModal modalContent={modalContent} onClose={() => setModalContent(null)} />
      <DashboardConditionDrawer
        open={conditionDrawerOpen}
        onClose={() => setConditionDrawerOpen(false)}
        params={params}
        brandFallback={brandName}
      />
    </div>
  );
}

/** Hub index 라우트 — DashboardOutlet 의 simResult 를 store 에서 다시 읽어 DashboardHub 렌더.
 *  진행중 무 데이터 상태에서는 DashboardOutlet 이 placeholder 를 직접 렌더하므로 여기엔 도달하지 않음. */
function DashboardHubRouteElement() {
  const simResult = useCombinedSimResult();
  const savedHistoryId = useSimulationStore((s) => s.savedHistoryId);
  const status = useSimulationStore((s) => s.status);
  const { user, brand } = useAuth();
  const ctx = useOutletContext<{ openConditionDrawer?: () => void }>();
  if (!simResult) {
    if (status === 'running') return <DashboardRunningPlaceholder />;
    return <Navigate to="/simulator" replace />;
  }
  return (
    <DashboardHub
      simResult={simResult}
      brandName={user?.company_name || brand?.brand_name || ''}
      savedHistoryId={savedHistoryId}
      onShowConditions={ctx?.openConditionDrawer}
    />
  );
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const scene = pathToScene(location.pathname);

  const [isTransitioning, setIsTransitioning] = useState(false);
  const [reportState, setReportState] = useState<'idle' | 'loading' | 'result'>('idle');

  // Simulation background tracking (IM3-205): store가 페이지 이동과 독립적으로
  // 시뮬레이션 상태를 보유. useCompletionToast는 running→done/error 전이 감지.
  useCompletionToast();
  useAbmCompletionToast();

  // FloatingWidget 의 dismiss(X) 가 store.status='idle' 로 만들 때 reportState 도 동기화.
  // 동기화 안 하면 reportState 가 'result' 로 남아 옛 비교모드 dashboard (dead 1,800줄) 가 노출됨.
  const storeStatus = useSimulationStore((s) => s.status);
  useEffect(() => {
    if (storeStatus === 'idle' && reportState !== 'idle') {
      setReportState('idle');
    }
  }, [storeStatus, reportState]);

  const [hoveredDistrictIdx, setHoveredDistrictIdx] = useState<number | null>(null);

  // 페이지 전환 시 모든 스크롤 컨테이너를 최상단으로 리셋
  useEffect(() => {
    window.scrollTo(0, 0);
    document.querySelectorAll("[class*='overflow-y']").forEach((el) => {
      el.scrollTop = 0;
    });
  }, [location.pathname]);

  // Command Palette (Cmd+K / Ctrl+K)
  const [isCommandOpen, setIsCommandOpen] = useState(false);
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandOpen((prev) => !prev);
      }
      if (e.key === 'Escape') setIsCommandOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Preloader — sessionStorage 플래그로 한 탭 세션당 1회만 재생 (새로고침 시 스킵)
  const [loadProgress, setLoadProgress] = useState(100);
  const [isAppLoaded, setIsAppLoaded] = useState(() => {
    if (typeof window === 'undefined') return false;
    return sessionStorage.getItem('spotter_booted') === '1';
  });
  const [loadLogs, setLoadLogs] = useState<string[]>([]);

  useEffect(() => {
    if (isAppLoaded) return; // 이미 부팅된 세션이면 프리로더 스킵
    setLoadProgress(0);
    setLoadLogs(['[SYSTEM] KERNEL BOOT SEQUENCE INITIATED...']);
    const duration = 3000;
    const interval = 30;
    const steps = duration / interval;
    let currentStep = 0;

    const timer = setInterval(() => {
      currentStep++;
      const p = Math.min(100, Math.floor((currentStep / steps) * 100));
      setLoadProgress(p);

      if (p === 15) setLoadLogs((prev) => [...prev, '[API] ESTABLISHING 3D SPATIAL CONNECTION...']);
      if (p === 35) setLoadLogs((prev) => [...prev, '[ENGINE] AGGREGATING FRANCHISE DATA...']);
      if (p === 60) setLoadLogs((prev) => [...prev, '[DATA] CALCULATING RISK ALGORITHMS...']);
      if (p === 85) setLoadLogs((prev) => [...prev, '[UI] RENDERING HOLOGRAM DASHBOARD...']);
      if (p === 100) setLoadLogs((prev) => [...prev, '[SYSTEM] SPOTTER ENGINE ONLINE.']);

      if (currentStep >= steps) {
        clearInterval(timer);
        setTimeout(() => {
          setIsAppLoaded(true);
          try {
            sessionStorage.setItem('spotter_booted', '1');
          } catch {
            /* private mode — silent fail */
          }
        }, 1700);
      }
    }, interval);

    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** 암전 트랜지션 + 라우팅 */
  const transitionTo = useCallback(
    (next: 'intro' | 'about' | 'joinus' | 'accordion' | 'simulator' | 'contact' | 'login') => {
      setIsTransitioning(true);
      setTimeout(() => {
        const pathMap: Record<string, string> = {
          intro: '/',
          about: '/about',
          joinus: '/joinus',
          login: '/login',
          hq: '/hq',
          accordion: '/explore',
          simulator: '/simulator',
          contact: '/contact',
        };
        const path = pathMap[next] || '/';
        // simulator 진입 = 새 시뮬 시작 의도. store 비우고 mount-restore (App.tsx:1297)
        // 가 reportState='result' 강제하지 않도록 → input UI 정상 표시.
        // dismissResult 는 status가 done/error 일 때만 동작 (running 중 호출은 no-op).
        if (next === 'simulator') {
          useSimulationStore.getState().dismissResult();
        }
        navigate(path);
        setTimeout(() => setIsTransitioning(false), 100);
      }, 800);
    },
    [navigate],
  );

  /** 경로 기반 암전 전환 — 하위 컴포넌트에서 useTransition()으로 사용 */
  const navigateWithTransition = useCallback(
    (path: string) => {
      setIsTransitioning(true);
      setTimeout(() => {
        navigate(path);
        setReportState('idle');
        setTimeout(() => setIsTransitioning(false), 100);
      }, 800);
    },
    [navigate],
  );

  return (
    <AuthProvider>
      <ManagerListProvider>
        <ToastProvider>
          <TransitionContext.Provider value={navigateWithTransition}>
            <div
              className="w-screen h-screen overflow-hidden select-none bg-background text-foreground"
              style={{
                animation: isAppLoaded
                  ? 'none'
                  : 'main-scene-in 1.5s cubic-bezier(0.19, 1, 0.22, 1) 0.5s forwards',
              }}
            >
              {/* Film Grain Noise Overlay */}
              <div
                className="pointer-events-none fixed inset-0 z-[9998] opacity-[0.04] mix-blend-screen"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
                }}
              />

              {/* Particle background */}
              <NetworkBackground isTransitioning={isTransitioning} scene={scene} theme="dark" />

              {/* Route-based scenes */}
              <Suspense fallback={null}>
                <Routes>
                  <Route
                    path="/"
                    element={
                      <IntroScene
                        onAboutClick={() => transitionTo('about')}
                        onLoginClick={() => transitionTo('login')}
                        onSimulatorClick={() => transitionTo('accordion')}
                        onContactClick={() => transitionTo('contact')}
                      />
                    }
                  />
                  <Route
                    path="/about"
                    element={<AboutPage onBack={() => transitionTo('intro')} />}
                  />
                  <Route
                    path="/joinus"
                    element={<JoinUsPage onBack={() => transitionTo('intro')} />}
                  />
                  <Route
                    path="/explore"
                    element={
                      <AccordionGallery
                        hoveredIdx={hoveredDistrictIdx}
                        setHoveredIdx={setHoveredDistrictIdx}
                        onMapoClick={() => transitionTo('simulator')}
                      />
                    }
                  />
                  <Route
                    path="/contact"
                    element={<ContactPage onBack={() => transitionTo('intro')} />}
                  />
                  <Route
                    path="/simulator"
                    element={
                      <ProtectedRoute>
                        <SimulatorDashboard
                          reportState={reportState}
                          setReportState={setReportState}
                        />
                      </ProtectedRoute>
                    }
                  />
                  {/* /dashboard nested route — 시뮬 완료 후 진입.
                      DashboardOutlet 이 store.result null guard + DetailModal host. */}
                  <Route
                    path="/dashboard"
                    element={
                      <ProtectedRoute>
                        <DashboardOutlet />
                      </ProtectedRoute>
                    }
                  >
                    <Route index element={<DashboardHubRouteElement />} />
                    <Route path="predict" element={<DashboardPredictPage />} />
                    <Route path="analyze" element={<DashboardAnalyzePage />} />
                    <Route path="abm" element={<DashboardAbmPage />} />
                  </Route>
                  <Route
                    path="/hq"
                    element={
                      <ProtectedRoute>
                        <HQCommandCenter />
                      </ProtectedRoute>
                    }
                  />
                  {/* ManagerDetail — 본인 또는 master 접근 가능 (내부 분기). Phase 1: self-view 중심 */}
                  <Route
                    path="/hq/managers/:id"
                    element={
                      <ProtectedRoute>
                        <ManagerDetail />
                      </ProtectedRoute>
                    }
                  />
                  {/* 저장된 시뮬 이력 재현 — 본인 이력만 조회 가능 (백엔드 권한 검증).
                      legacy /dashboard/history/:id (기존 simulation_history) — 3-card hub 진입.
                      신규 /dashboard/foresee/:id (simulation_foresee) — PredictGroup 직접 진입.
                      신규 /dashboard/ai/:id (simulation_ai) — AnalyzeGroup 직접 진입. */}
                  <Route
                    path="/dashboard/history/:id"
                    element={
                      <ProtectedRoute>
                        <SimulationHistoryDetail />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/dashboard/foresee/:id"
                    element={
                      <ProtectedRoute>
                        <SimulationHistoryDetail kind="foresee" />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/dashboard/ai/:id"
                    element={
                      <ProtectedRoute>
                        <SimulationHistoryDetail kind="ai" />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/login"
                    element={<LoginPage onLogoClick={() => transitionTo('intro')} />}
                  />
                </Routes>
              </Suspense>

              {/* IM3-205: 시뮬레이션 백그라운드 추적 — 라우팅 바깥에 마운트 */}
              <SimulationFloatingWidget />
              <AbmFloatingWidget />
              <BeforeUnloadGuard />
              <ToastHost />

              {/* Global header — all scenes except intro */}
              {scene !== 'intro' && scene !== 'login' && !isTransitioning && (
                <header className="fixed top-0 left-0 w-full h-20 border-b border-border flex items-center px-8 md:px-16 justify-between bg-card/90 backdrop-blur-md z-50 transition-colors duration-500">
                  <div className="flex items-center gap-4">
                    <button
                      onClick={() => transitionTo('intro')}
                      className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity duration-300"
                    >
                      <img src="/logo.svg" alt="SPOTTER" className="h-5 w-auto" />
                      <span className="text-sm font-bold tracking-wider text-foreground">
                        SPOTTER
                      </span>
                    </button>
                    <span className="text-border">/</span>
                    <button
                      onClick={() => {
                        // 1. 시뮬레이터 result 상태 → history.back() 호출 → popstate 리스너가 idle로 복귀
                        //    (브라우저 뒤로가기와 동일한 코드 경로 → 히스토리 정합성 유지)
                        if (scene === 'simulator' && reportState === 'result') {
                          window.history.back();
                          return;
                        }
                        // 2. react-router 페이지(/dashboard/*, /hq, /hq/*) → 직전 페이지로 복귀
                        //    SimulationHistoryDetail 같은 페이지에서 BACK 시 intro로 튕기던 버그 fix
                        if (
                          location.pathname.startsWith('/dashboard/') ||
                          location.pathname === '/hq' ||
                          location.pathname.startsWith('/hq/')
                        ) {
                          navigate(-1);
                          return;
                        }
                        // 3. scene-based fallback (intro/accordion/login)
                        transitionTo(scene === 'simulator' ? 'accordion' : 'intro');
                      }}
                      className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors duration-300"
                    >
                      <ChevronRight size={14} className="rotate-180" />
                      BACK
                    </button>
                  </div>
                  {/* Center — 환영 메시지 (로그인 시) */}
                  <WelcomeWidget />
                  <div className="flex items-center gap-4 md:gap-6">
                    <GlobalLimelightNav />
                    <LogoutButton />
                  </div>
                </header>
              )}

              {/* Command Palette (Cmd+K / Ctrl+K) */}
              <Suspense fallback={null}>
                <CommandPalette
                  isOpen={isCommandOpen}
                  onClose={() => setIsCommandOpen(false)}
                  onNavigate={(target) => {
                    setIsCommandOpen(false);
                    transitionTo(target as any);
                  }}
                />
              </Suspense>

              {/* Transition overlay */}
              <div
                className={`fixed inset-0 z-50 bg-black pointer-events-none transition-opacity duration-[800ms] ${
                  isTransitioning ? 'opacity-100' : 'opacity-0'
                }`}
              />

              {/* 3D Hologram Preloader */}
              {!isAppLoaded && (
                <div
                  className="absolute inset-0 z-[99999] bg-card flex flex-col items-center justify-center"
                  style={{
                    animation:
                      loadProgress === 100
                        ? 'warp-out 1.2s cubic-bezier(0.19, 1, 0.22, 1) 0.5s forwards'
                        : 'none',
                  }}
                >
                  {/* Noise */}
                  <div
                    className="absolute inset-0 opacity-[0.05] mix-blend-screen pointer-events-none"
                    style={{
                      backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
                    }}
                  />

                  {/* 3D Multi-Axis Core */}
                  <div className="scene-3d relative w-[300px] h-[300px] md:w-[500px] md:h-[500px] flex items-center justify-center mt-[-10vh]">
                    <div className="hologram-wrapper absolute w-full h-full flex items-center justify-center">
                      {/* Base core glow */}
                      <div className="absolute w-[40%] h-[40%] rounded-full bg-primary/20 blur-[40px]" />

                      {/* Ring 1 */}
                      <svg
                        viewBox="0 0 200 200"
                        className="absolute w-[100%] h-[100%] opacity-40"
                        style={{
                          transform: 'rotateX(70deg) rotateY(10deg) rotateZ(0deg)',
                          animation: 'gyro-1 12s linear infinite',
                        }}
                      >
                        <circle
                          cx="100"
                          cy="100"
                          r="95"
                          fill="none"
                          stroke="var(--primary)"
                          strokeWidth="0.5"
                          strokeDasharray="2 6"
                        />
                        <circle
                          cx="100"
                          cy="100"
                          r="90"
                          fill="none"
                          stroke="var(--primary)"
                          strokeWidth="2"
                          strokeDasharray="10 40 30 20"
                        />
                      </svg>

                      {/* Ring 2 */}
                      <svg
                        viewBox="0 0 200 200"
                        className="absolute w-[85%] h-[85%] opacity-60"
                        style={{
                          transform: 'rotateX(50deg) rotateY(60deg) rotateZ(0deg)',
                          animation: 'gyro-2 9s linear infinite',
                        }}
                      >
                        <circle
                          cx="100"
                          cy="100"
                          r="85"
                          fill="none"
                          stroke="var(--primary)"
                          strokeWidth="3"
                          strokeDasharray="60 30 10 30"
                          strokeLinecap="round"
                        />
                        <circle cx="100" cy="15" r="5" fill="var(--primary)" />
                      </svg>

                      {/* Ring 3 */}
                      <svg
                        viewBox="0 0 200 200"
                        className="absolute w-[70%] h-[70%] opacity-70"
                        style={{
                          transform: 'rotateX(50deg) rotateY(-60deg) rotateZ(0deg)',
                          animation: 'gyro-3 15s linear infinite',
                        }}
                      >
                        <circle
                          cx="100"
                          cy="100"
                          r="75"
                          fill="none"
                          stroke="var(--primary)"
                          strokeWidth="1"
                          strokeDasharray="4 8"
                        />
                        <circle
                          cx="100"
                          cy="100"
                          r="70"
                          fill="none"
                          stroke="var(--primary)"
                          strokeWidth="1.5"
                          strokeDasharray="40 80"
                        />
                      </svg>

                      {/* Ring 4 */}
                      <svg
                        viewBox="0 0 200 200"
                        className="absolute w-[95%] h-[95%] opacity-80"
                        style={{
                          transform: 'rotateX(20deg) rotateY(80deg) rotateZ(0deg)',
                          animation: 'gyro-4 6s linear infinite',
                        }}
                      >
                        <circle
                          cx="100"
                          cy="100"
                          r="88"
                          fill="none"
                          stroke="var(--primary)"
                          strokeWidth="1"
                          style={{ filter: 'drop-shadow(0 0 8px var(--primary))' }}
                        />
                        <circle cx="100" cy="12" r="3" fill="#ffffff" />
                        <circle cx="100" cy="188" r="3" fill="#ffffff" />
                      </svg>

                      {/* Ring 5 */}
                      <svg
                        viewBox="0 0 200 200"
                        className="absolute w-[115%] h-[115%] opacity-30"
                        style={{
                          transform: 'rotateX(80deg) rotateY(-30deg) rotateZ(0deg)',
                          animation: 'gyro-5 20s linear infinite',
                        }}
                      >
                        <circle
                          cx="100"
                          cy="100"
                          r="98"
                          fill="none"
                          stroke="var(--primary)"
                          strokeWidth="1"
                          strokeDasharray="4 16"
                        />
                        <circle
                          cx="100"
                          cy="100"
                          r="94"
                          fill="none"
                          stroke="var(--primary)"
                          strokeWidth="0.5"
                        />
                      </svg>

                      {/* Center percentage */}
                      <div
                        className="absolute flex flex-col items-center justify-center pointer-events-none"
                        style={{ animation: 'energy-pulse 2s ease-in-out infinite' }}
                      >
                        <span className="font-black font-mono tabular-nums text-6xl md:text-8xl text-primary tracking-tighter leading-none">
                          {loadProgress}
                          <span className="text-3xl md:text-4xl text-primary/60 ml-1">%</span>
                        </span>
                        <span className="font-mono text-[0.625rem] md:text-xs text-primary/80 tracking-[0.3em] mt-2">
                          SYNCING...
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Terminal logs */}
                  <div className="absolute bottom-10 left-10 md:bottom-16 md:left-16 font-mono text-[0.625rem] md:text-xs text-muted-foreground max-w-md">
                    <div className="flex flex-col gap-1.5">
                      {loadLogs.map((log, idx) => (
                        <div
                          key={idx}
                          className={idx === loadLogs.length - 1 ? 'text-primary font-bold' : ''}
                        >
                          {log}
                        </div>
                      ))}
                    </div>
                    <div className="w-2 h-3 bg-primary mt-2 animate-pulse" />
                  </div>
                </div>
              )}
            </div>
          </TransitionContext.Provider>
          <SimulationFloatingWidget />
          <AbmFloatingWidget />
        </ToastProvider>
      </ManagerListProvider>
    </AuthProvider>
  );
}
