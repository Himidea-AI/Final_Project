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

import { useState, useEffect, useRef, useCallback, useMemo, lazy, Suspense } from 'react';
import { Routes, Route, useNavigate, useLocation, Outlet, Navigate } from 'react-router-dom';
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
import {
  DetailModal,
  type DetailModalContent,
} from './components/SimulationResult/dashboard/shared/DetailModal';
import DashboardPredictPage from './pages/dashboard/DashboardPredictPage';
import DashboardAnalyzePage from './pages/dashboard/DashboardAnalyzePage';
import DashboardAbmPage from './pages/dashboard/DashboardAbmPage';
import { SaveButton } from './components/SimulationHistory/SaveButton';
import { SaveDialog } from './components/SimulationHistory/SaveDialog';
import { useSaveSimulation } from './hooks/useSaveSimulation';
import { formatDocumentId } from './types/simulationHistory';
import { SimulationFloatingWidget } from './components/simulation/SimulationFloatingWidget';
import { BeforeUnloadGuard } from './components/simulation/BeforeUnloadGuard';
import { ToastHost } from './components/simulation/ToastHost';
import { useCompletionToast } from './hooks/useCompletionToast';
import { useSimulationStore } from './stores/simulationStore';
import { getLivePopulation, type CustomerSegmentRequest } from './api/client';
import { useCustomerSegmentPreview } from './hooks/useCustomerSegmentPreview';
import { useCombinedSimResult, buildCombinedResult } from './hooks/useCombinedSimResult';
import NetworkBackground from './components/NetworkBackground';
// Phase C Round 2 — PDF 묶음 + Dashboard 묶음 추출 (정적 import 유지)
import {
  HiddenPDFTemplate,
  type CannRow,
  type NeighborhoodRow,
} from './components/PDF/HiddenPDFTemplate';
import DashboardPanelView from './components/dashboard/DashboardPanelView';

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
  ChevronDown,
  X,
  Zap,
  Calendar,
  Download,
  FileText,
  Database,
  Store,
  Columns,
  Terminal,
  UserCheck,
  Loader2,
} from 'lucide-react';

import HybridSliderInput from './components/ui/HybridSliderInput';
import { SectionLabel } from './components/ui/SectionLabel';
import { FormField } from './components/ui/FormField';
import { ScopeHint } from './components/ui/ScopeHint';
import { ChipGroup } from './components/ui/ChipGroup';
import { Toggle } from './components/ui/Toggle';
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
   상세 데이터 테이블 — 정렬 가능한 row data (Mock)
   CannRow / NeighborhoodRow 타입은 components/PDF/HiddenPDFTemplate.tsx로 이동.
   ═══════════════════════════════════════════════════════ */

// 정렬용 값 추출 (문자열 컬럼은 그대로, 숫자 컬럼은 파싱)
function extractSortValue(row: Record<string, string>, key: string): number | string {
  const v = row[key];
  if (v === undefined || v === null) return ''; // 다른 뷰의 컬럼 키일 때 안전 fallback
  if (key === 'distance') {
    // "450m" → 450, "1.2km" → 1200
    const num = parseFloat(v);
    return v.endsWith('km') ? num * 1000 : num;
  }
  // "-2.1%", "82%", "87 / 100", "3.5 개월" 모두 parseFloat로 첫 숫자 추출
  if (['impact', 'score', 'closureRate', 'bep'].includes(key)) {
    return parseFloat(v);
  }
  return v; // name, status는 문자열 정렬
}

function sortRows<T extends Record<string, string>>(
  rows: T[],
  key: string | null,
  dir: 'asc' | 'desc',
): T[] {
  if (!key) return rows;
  return [...rows].sort((a, b) => {
    const av = extractSortValue(a, key);
    const bv = extractSortValue(b, key);
    if (av < bv) return dir === 'asc' ? -1 : 1;
    if (av > bv) return dir === 'asc' ? 1 : -1;
    return 0;
  });
}

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
  const [radius, setRadius] = useState(500);
  const [budget, setBudget] = useState(200);
  const [weighted, setWeighted] = useState(false);
  // loadingText/loadingProgress state는 로딩 UI 제거(2026-04-28)와 함께 dead.
  // SimulationFloatingWidget이 store status를 직접 구독해 진행 표시.
  const { showToast } = useToast();
  const { user, brand } = useAuth();
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  // SimResult는 camelCase로 변환된 뷰 모델. IntegratedReport는 snake_case SimulationOutput을 직접 소비하므로 원본도 별도 보존.
  const [rawSimResult, setRawSimResult] = useState<SimulationOutput | null>(null);

  // [R4] saveDialogOpen 은 UI-only 로컬. savedHistoryId 는 [R1] store 에서 파생.
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const savedHistoryId = useSimulationStore((s) => s.savedHistoryId);
  const setSavedHistoryId = useSimulationStore((s) => s.setSavedHistoryId);
  const saveSim = useSaveSimulation();
  const [isDownloadOpen, setIsDownloadOpen] = useState(false);
  // 마포구 외 다른 자치구 미지원 — useState 트릭 제거하고 const 로 노출.
  // 향후 다른 구 확장 시 useState<GuName>('마포구') + setter 로 복원.
  const selectedGu = '마포구' as const;
  // [UX] 동 선택 1~4개 제한 — 파이프라인 성능 + 레이더 차트 가독성 한계
  const [selectedDongs, setSelectedDongs] = useState<string[]>(() =>
    DONG_DATA['마포구'].slice(0, 4),
  );
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
  const [businessType, setBusinessType] = useState(defaultBizType);
  // 로그인 후 brand 정보가 비동기 로드되면 업종 자동 반영
  useEffect(() => {
    if (brand?.industry_medium) {
      const mapped = FTC_TO_FRONTEND_INDUSTRY[brand.industry_medium];
      if (mapped) setBusinessType(mapped);
    }
  }, [brand?.industry_medium]);
  const [businessTypeOpen, setBusinessTypeOpen] = useState(false);
  const [storeArea, setStoreArea] = useState(15); // 평
  const [targetPrice, setTargetPrice] = useState('5to10k');
  const [operatingHours, setOperatingHours] = useState<string[]>(['점심', '저녁']);
  const [isWorkflowOpen, setIsWorkflowOpen] = useState(false);
  const [isSplitMode, setIsSplitMode] = useState(false);
  const [initialCapital, setInitialCapital] = useState(5000); // 만원

  // [customer_revenue] 타겟 고객 프로필 — A1 찬영 P1-C 연동. 빈 선택 = 전체 고객
  const [targetAgeGroups, setTargetAgeGroups] = useState<string[]>([]);
  const [targetGender, setTargetGender] = useState<'male' | 'female' | null>(null);
  const [targetTimeSlots, setTargetTimeSlots] = useState<string[]>([]);
  const [targetDayType, setTargetDayType] = useState<'weekday' | 'weekend' | null>(null);
  const [targetMonthlySales, setTargetMonthlySales] = useState<number | null>(null);

  // [customer_segment 미리보기] 좌측 패널 입력 변경 시 ~100ms MLP 호출.
  // /predict + /analyze/llm (멀티에이전트 파이프라인)와 무관 — RUN 누르기 전 즉시 피드백.
  const previewReq = useMemo<CustomerSegmentRequest | null>(() => {
    if (!selectedDongs[0]) return null;
    return {
      target_district: selectedDongs[0],
      business_type: BUSINESS_TYPE_BACKEND_KEY[businessType] || businessType,
      target_age_groups: targetAgeGroups,
      target_gender: targetGender,
      target_time_slots: targetTimeSlots,
      target_day_type: targetDayType,
      target_monthly_sales: targetMonthlySales,
    };
  }, [
    // selectedDongs 배열 reference 대신 [0]만 — 새 배열 reference로 setState 시 useMemo 재계산 회피
    selectedDongs[0],
    businessType,
    targetAgeGroups,
    targetGender,
    targetTimeSlots,
    targetDayType,
    targetMonthlySales,
  ]);
  const {
    data: previewSegment,
    isLoading: isPreviewLoading,
    error: previewError,
  } = useCustomerSegmentPreview(previewReq);

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
  // sortKey/sortDir 은 dead 분기 제거(2026-04-30) 후 setter 가 호출되지 않아
  // 사실상 정적 상수가 되었으나, sortRows() 시그니처 호환을 위해 유지.
  // PDF/Excel 내보내기는 입력 순서대로 출력됨.
  const sortKey: string | null = null;
  const sortDir: 'asc' | 'desc' = 'asc';

  // 정렬된 행 데이터 — 가맹점 간섭도는 competitor_intel.samples 실데이터 우선
  // Pancras 2013 거리 감쇠: (1 - 0.281)^(1/1.609) ≈ 0.813 per km
  // base_rate는 업종별 차등 (backend commercial_intelligence.py와 동기화).
  // allCompetitorLocations 우선 사용 (winner+top3 전체 동), fallback은 winner 단일 동
  const _competitorSamples: any[] = simResult?.allCompetitorLocations?.length
    ? simResult.allCompetitorLocations.map((s) => ({
        place_name: s.place_name || s.brand_name,
        distance_m: s.distance_m ?? 0,
        is_franchise: s.is_franchise,
        source_dong: s.source_dong,
      }))
    : (simResult?.competitorIntel?.competition_500m?.samples ?? []);

  const dynamicCannRows: CannRow[] = _competitorSamples.length
    ? _competitorSamples.slice(0, 12).map((s) => {
        const dist = s.distance_m;
        // Industry base rates mirror backend commercial_intelligence.py:estimate_cannibalization
        const INDUSTRY_BASE: Record<string, number> = {
          cafe: 0.25,
          coffee: 0.25,
          chicken: 0.1,
          burger: 0.2,
          korean: 0.15,
        };
        const btKey = (BUSINESS_TYPE_BACKEND_KEY[businessType] || businessType || '').toLowerCase();
        // 한국어 업종명을 영어 키로 매핑 (커피/카페→coffee, 치킨→chicken, 햄버거→burger, 한식→korean)
        const industryKey =
          btKey.includes('커피') || btKey.includes('카페') || btKey === 'coffee' || btKey === 'cafe'
            ? 'coffee'
            : btKey.includes('치킨') || btKey === 'chicken'
              ? 'chicken'
              : btKey.includes('햄버거') || btKey.includes('패스트푸드') || btKey === 'burger'
                ? 'burger'
                : btKey.includes('한식') || btKey === 'korean'
                  ? 'korean'
                  : '';
        const baseRate = INDUSTRY_BASE[industryKey] ?? 0.2;
        const impactPct = -baseRate * Math.pow(0.813, dist / 1000) * 100;
        const status = dist < 300 ? 'Danger' : dist < 800 ? 'Caution' : 'Safe';
        return {
          name: s.place_name || '경쟁업체',
          distance: dist >= 1000 ? `${(dist / 1000).toFixed(1)}km` : `${Math.round(dist)}m`,
          impact: `${impactPct.toFixed(1)}%`,
          status,
        };
      })
    : [];
  const sortedCannRows = sortRows(dynamicCannRows, sortKey, sortDir);

  // 행정동은 district_rankings 실응답 우선, 없으면 빈 배열 (mock 제거)
  const dynamicNeighborhoodRows: NeighborhoodRow[] = simResult?.districtRankings?.length
    ? simResult.districtRankings.slice(0, 16).map((r) => ({
        name: r.district || '-',
        score: typeof r.score === 'number' ? String(Math.round(r.score)) : '—',
        closureRate:
          typeof r.closure_rate === 'number' ? `${Math.round(r.closure_rate * 100)}%` : '—',
        // 2026-04-27: DistrictRanking은 bep_quarters(분기 단위)로 마이그레이션됨
        bep: typeof r.bep_quarters === 'number' ? `${r.bep_quarters}분기` : '—',
      }))
    : [];
  const sortedNeighborhoodRows = sortRows(dynamicNeighborhoodRows, sortKey, sortDir);

  // 오늘 날짜 (리포트 생성 시점)
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  const dd = String(today.getDate()).padStart(2, '0');
  const reportMonthLabel = `${yyyy}. ${mm}.`;
  const reportFullDate = `${yyyy}.${mm}.${dd}`;

  // [v12.0] PDF/Excel 다운로드용 ref + 로딩 상태
  const pdfTemplateRef = useRef<HTMLDivElement>(null);
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
  const [isGeneratingExcel, setIsGeneratingExcel] = useState(false);

  const handleDownloadPDF = useCallback(async () => {
    if (!pdfTemplateRef.current) return;
    setIsDownloadOpen(false);
    setIsGeneratingPDF(true);

    try {
      const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
        import('jspdf'),
        import('html2canvas'),
      ]);

      const template = pdfTemplateRef.current;
      const pages = Array.from(template.children) as HTMLElement[];

      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();

      for (let i = 0; i < pages.length; i++) {
        const canvas = await html2canvas(pages[i], {
          scale: 2,
          useCORS: true,
          backgroundColor: '#ffffff',
          logging: false,
        });
        const imgData = canvas.toDataURL('image/png');
        if (i > 0) pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
      }

      const dateStr = reportFullDate.replace(/\./g, '');
      const districtName = selectedDongs[0] || '연남동';
      pdf.save(`SPOTTER_마포구_${districtName}_${dateStr}.pdf`);
      showToast('success', 'PDF 리포트 생성이 완료되었습니다.');
    } catch (error) {
      console.error('PDF Generation Failed:', error);
      showToast('error', 'PDF 생성 중 오류가 발생했습니다.');
    } finally {
      setIsGeneratingPDF(false);
    }
  }, [reportFullDate, selectedDongs, showToast]);

  const handleDownloadExcel = useCallback(async () => {
    setIsDownloadOpen(false);
    setIsGeneratingExcel(true);

    try {
      const XLSX = await import('xlsx');
      const districtName = selectedDongs[0] || '연남동';

      const wb = XLSX.utils.book_new();

      // Sheet 1: 요약
      const summary: (string | number)[][] = [
        ['SPOTTER · AI Franchise Intelligence Report'],
        [],
        ['분석 대상', `마포구 ${districtName}`],
        ['생성 일시', reportFullDate],
        ['Document ID', formatDocumentId(savedHistoryId)],
        [],
        ['KPI 요약'],
        ['지표', '값', '트렌드'],
        // §3.7 — 데이터 없을 때 임의 default 금지. mock 트렌드/등급 모두 '—'로 통일.
        [
          '예상 월 매출 (추정)',
          simResult?.revenue != null
            ? `₩ ${(simResult.revenue * 10000).toLocaleString()}`
            : '데이터 없음',
          '—',
        ],
        [
          '상권 종합 매력도',
          simResult?.score != null ? `${simResult.score} / 100` : '데이터 없음',
          '—',
        ],
        [
          '일일 유동인구',
          popData?.daily_average ? `${popData.daily_average.toLocaleString()} 명` : '데이터 없음',
          popData?.date ?? '—',
        ],
        [
          '카니발리제이션 위험',
          simResult?.riskLevel != null ? simResult.riskLevel : '데이터 없음',
          '—',
        ],
        [],
        ['7 Core Metrics (레이더 차트)'],
        ['항목', '점수'],
        ...(simResult?.chartData ?? []).map((d) => [d.label, d.value]),
      ];
      const ws1 = XLSX.utils.aoa_to_sheet(summary);
      ws1['!cols'] = [{ wch: 25 }, { wch: 25 }, { wch: 15 }];
      XLSX.utils.book_append_sheet(wb, ws1, '요약');

      // Sheet 2: 가맹점 간섭도 (실데이터만. 없으면 헤더만 출력)
      const cannRowsForExport = sortedCannRows;
      const cann: (string | number)[][] = [
        ['가맹점명', '거리', '예상 매출 하락', '상태'],
        ...cannRowsForExport.map((r) => [r.name, r.distance, r.impact, r.status]),
      ];
      const ws2 = XLSX.utils.aoa_to_sheet(cann);
      ws2['!cols'] = [{ wch: 20 }, { wch: 12 }, { wch: 15 }, { wch: 12 }];
      XLSX.utils.book_append_sheet(wb, ws2, '가맹점 간섭도');

      // Sheet 3: 행정동 비교 (실데이터만. 없으면 헤더만 출력)
      const neighborhoodRowsForExport = sortedNeighborhoodRows;
      const neighborhoods: (string | number)[][] = [
        ['행정동', 'AI 점수', '폐업률', '예상 BEP'],
        ...neighborhoodRowsForExport.map((r) => [r.name, r.score, r.closureRate, r.bep]),
      ];
      const ws3 = XLSX.utils.aoa_to_sheet(neighborhoods);
      ws3['!cols'] = [{ wch: 15 }, { wch: 12 }, { wch: 12 }, { wch: 15 }];
      XLSX.utils.book_append_sheet(wb, ws3, '행정동 비교');

      // Sheet 4: AI 인사이트
      const insights: (string | number)[][] = [
        ['SPOTTER AI 인사이트 — LangGraph Multi-Agent'],
        [],
        ['Severity', 'Title', 'Description'],
        [
          'ADVISORY',
          '저녁 시간대 매출 집중형',
          '18시 이후 유동인구가 급증. 야간 메뉴 강화를 권장합니다.',
        ],
        [
          'CRITICAL',
          '법률 리스크 경고 (Legal Node)',
          simResult?.recommendation ||
            '상가임대차보호법 위반 사례 존재 권역. 최근 3년 평균 임대료 인상률이 5%를 초과하여 계약 갱신 시 법적 분쟁 리스크가 감지되었습니다.',
        ],
        [
          'OPPORTUNITY',
          '2030 여성 타겟 구역',
          'SNS 친화적 인테리어 도입 시 수익 창출 확률 34% 증가.',
        ],
      ];
      const ws4 = XLSX.utils.aoa_to_sheet(insights);
      ws4['!cols'] = [{ wch: 12 }, { wch: 30 }, { wch: 60 }];
      XLSX.utils.book_append_sheet(wb, ws4, 'AI 인사이트');

      const dateStr = reportFullDate.replace(/\./g, '');
      XLSX.writeFile(wb, `SPOTTER_마포구_${districtName}_${dateStr}.xlsx`);
      showToast('success', 'Excel 데이터가 다운로드되었습니다.');
    } catch (error) {
      console.error('Excel Generation Failed:', error);
      showToast('error', 'Excel 생성 중 오류가 발생했습니다.');
    } finally {
      setIsGeneratingExcel(false);
    }
  }, [
    reportFullDate,
    selectedDongs,
    simResult,
    showToast,
    popData,
    sortedCannRows,
    sortedNeighborhoodRows,
    savedHistoryId, // line 1114에서 formatDocumentId(savedHistoryId) 사용 — 시뮬 저장 직후 stale closure 방지
  ]);

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

  // [R2] 마운트 시 store 에서 복원 — 다른 페이지로 나갔다가 /simulator 복귀 시 결과 유지.
  // buildCombinedResult 로 prediction + analysis 슬라이스를 합성. 로컬 state 가 비어있으면 toSimResultViewModel 로 재현.
  useEffect(() => {
    const s = useSimulationStore.getState();
    const combined = buildCombinedResult(
      s.prediction.data,
      s.analysis.data,
      s.params?.target_district ?? undefined,
    );
    if (reportState === 'idle' && s.status === 'done' && combined) {
      setRawSimResult(combined);
      setSimResult(toSimResultViewModel(combined));
      setReportState('result');
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
  const navigatedForResultRef = useRef<SimulationOutput | null>(null);
  useEffect(() => {
    if (!isSplitMode && rawSimResult && navigatedForResultRef.current !== rawSimResult) {
      navigatedForResultRef.current = rawSimResult;
      navigate('/dashboard', { replace: true });
    }
  }, [rawSimResult, isSplitMode, navigate]);

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
    try {
      // [C1 연동] 백엔드 SimulationInput 9개 필드 전부 전송
      // business_type: UI 한글 라벨 → _SALES_CODE_MAP 키로 변환
      // brand_name: 브랜드 자동매핑(auth 로그인 시 ftc_brand_franchise 조회) 결과 우선,
      //            없으면 company_name 폴백 (경쟁 분석 _resolve_industry 매핑률 향상)
      // TODO(existing_stores): 매장 관리 UI 추가 시 실제 데이터 연동 (현재는 빈 배열)
      const payload = {
        business_type: BUSINESS_TYPE_BACKEND_KEY[businessType] || businessType,
        brand_name: brand?.brand_name || user?.company_name || '',
        target_district: selectedDongs[0] || '서교동',
        target_districts: selectedDongs.length > 0 ? selectedDongs : ['서교동'],
        existing_stores: [],
        monthly_rent: budget * 10000, // 만원 → 원
        scenarios: [],
        // 신규 7 필드
        store_area: storeArea,
        target_price_range: targetPrice,
        operating_hours: operatingHours,
        initial_capital: initialCapital * 10000,
        commercial_radius: radius,
        population_weight: weighted,
        industry_filter: BUSINESS_TYPE_CS_CODE[businessType] ?? null,
        // [customer_revenue] A1 찬영 P1-C — target_* 5필드. 선택 안 한 경우 null/빈배열 = 전체 고객.
        target_age_groups: targetAgeGroups,
        target_gender: targetGender,
        target_time_slots: targetTimeSlots,
        target_day_type: targetDayType,
        target_monthly_sales: targetMonthlySales,
      };

      // [IM3-205] fetch를 simulationStore로 위임 — 페이지 이동해도 fetch가 끊기지 않음
      // [IM3-259] /predict + /analyze/llm 독립 비동기 호출. predict 완료 즉시 대시보드 진입, analyze 는 백그라운드 완료 후 자동 갱신.
      await useSimulationStore.getState().startSimulation(payload);
      const storeState = useSimulationStore.getState();
      const simRes = buildCombinedResult(
        storeState.prediction.data,
        storeState.analysis.data,
        storeState.params?.target_district ?? undefined,
      );
      // prediction 슬라이스만 done 이면 대시보드 진입 허용.
      // analysis 는 백그라운드에서 계속 실행 — DashboardOutlet 이 store 구독으로 자동 갱신.
      if (storeState.prediction.status !== 'done' || !simRes) {
        throw new Error(storeState.error ?? 'Simulation failed');
      }
      // [R1] Zustand store.result 가 Single Source of Truth.
      // 아래 setRawSimResult/setSimResult 는 마운트 복원 로직과 동일 함수 사용.
      setRawSimResult(simRes);
      setSimResult(toSimResultViewModel(simRes));
      saveSim.reset(); // SaveDialog 에러 메시지 초기화 (store.savedHistoryId 는 startSimulation 에서 이미 null 리셋됨)
      setReportState('result');
    } catch (err) {
      console.error('Simulation failed:', err);
      // [B2 수지니 요청] smart mock fallback 제거 — 성공/실패 구분 명확화.
      // 타임아웃(600s) 또는 LangGraph 실패 시 입력 패널로 복귀 + 재시도 유도 토스트.
      setRawSimResult(null);
      setSimResult(null);
      setReportState('idle');
      const msg =
        err instanceof Error && err.message
          ? `시뮬레이션 실패: ${err.message.slice(0, 80)} — RUN SIMULATION 을 다시 눌러 재시도해주세요.`
          : '시뮬레이션 실패 — RUN SIMULATION 을 다시 눌러 재시도해주세요.';
      showToast('error', msg);
    }
  }, [
    setReportState,
    selectedDongs,
    budget,
    businessType,
    user?.company_name,
    brand?.brand_name, // line 1322 brand_name 폴백 — 로그아웃 후 재로그인 시 새 brand 반영
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
    saveSim, // line 1359 saveSim.reset() 호출 — useSaveSimulation 인스턴스 변경 추적
  ]);

  // 로딩 UI 제거(2026-04-28)와 함께 store progress/stage 미러 useEffect도 dead → 제거.
  // SimulationFloatingWidget이 store를 직접 구독해 진행 상태 표시.

  // Light theme tokens (semantic, dark-mode hex retired)
  const textSecondary = 'text-muted-foreground';

  return (
    <div
      ref={dashboardRef}
      className="relative z-10 h-full w-full bg-card overflow-y-auto custom-scrollbar"
    >
      {/* Top bar — 페이지 타이틀(좌) + RUN 버튼(우).
          mt-28 = 초기 위치는 App 헤더(80px)와 32px 갭.
          sticky top-20 = 스크롤 시 App 헤더 바닥에 flush 로 붙음 → 갭 사이 컨텐츠 비침 차단.
          (top-28 로 갭 유지하면 갭 사이로 스크롤되는 컨텐츠가 비치는 이슈) */}
      <div
        className={`sticky top-20 z-30 flex items-center justify-between px-8 py-4 mt-28 bg-card/90 backdrop-blur-xl ${
          reportState === 'result' ? 'hidden' : ''
        }`}
      >
        <h1 className="text-2xl md:text-3xl font-black text-foreground tracking-tight">
          SIMULATION SETUP
        </h1>
        <button
          onClick={runSim}
          disabled={reportState === 'loading'}
          className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-bold text-sm tracking-wider transition-all duration-200 ${
            reportState === 'loading'
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
        <div
          className={`lg:col-span-5 lg:order-2 box-glass rounded-2xl p-6 transition-all duration-700 ${reportState === 'result' ? 'hidden' : ''}`}
        >
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
                    <div className="absolute z-50 mt-1 w-full max-h-52 overflow-y-auto rounded-lg border border-border bg-card shadow-2xl custom-scrollbar">
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
        <div
          className={`lg:col-span-12 lg:order-3 ${reportState === 'result' ? 'hidden' : ''}`}
        >
          <ScopeHint selectedDongCount={selectedDongs.length} />
        </div>

        {/* ─────── 섹션 2: 운영 조건 — Cell row1·col7. p-5 + gap-3 으로 row 1 height 정상화 ─────── */}
        <div
          className={`lg:col-span-7 lg:order-1 box-glass rounded-2xl p-5 transition-all duration-700 ${reportState === 'result' ? 'hidden' : ''}`}
        >
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
        <div
          className={`lg:col-span-12 lg:order-4 box-glass rounded-2xl p-6 transition-all duration-700 ${reportState === 'result' ? 'hidden' : ''}`}
        >
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

            {/* [customer_segment 미리보기] RUN 누르기 전 ~100ms MLP 결과 표시 */}
            {previewSegment && (
              <div className="mt-4 px-4 py-3 rounded-lg border border-primary/30 bg-primary/5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[0.625rem] font-black text-primary uppercase tracking-widest">
                    실시간 미리보기 · {(previewSegment.segment_ratio * 100).toFixed(1)}% 기여
                  </span>
                  {isPreviewLoading && <Loader2 size={12} className="animate-spin text-primary" />}
                </div>
                <p className="text-[0.6875rem] text-foreground leading-relaxed">
                  {previewSegment.profile_summary}
                </p>
                {previewSegment.segment_sales != null && (
                  <p className="text-[0.625rem] text-muted-foreground tabular-nums">
                    세그먼트 매출 추정: ₩{previewSegment.segment_sales.toLocaleString('ko-KR')}
                  </p>
                )}
                <p className="text-[0.5625rem] text-muted-foreground italic">
                  * 동·업종 단위 MLP 추정 — RUN SIMULATION 후 종합 결과로 검증
                </p>
              </div>
            )}
            {previewError && !isPreviewLoading && (
              <div className="mt-4 px-4 py-2 rounded-lg border border-danger/30 bg-danger/10 text-[0.6875rem] text-danger">
                미리보기 실패: {previewError}
              </div>
            )}
          </div>
        </div>
        {/* /타겟 페르소나 카드 끝 */}

        {/* Right panel wrapper — col-span-12 풀폭. RUN SIMULATION 박스(아래)가 이 wrapper의
            자식이므로 wrapper 자체에 hidden을 걸면 안 됨. 내부 Visualization 박스만 result 시
            노출 + RUN 박스는 자체 className으로 result 시 hidden(line 3939). */}
        <div className="lg:col-span-12 flex flex-col gap-6">
          {/* Right panel — Visualization (result 시에만 표시. idle/loading 시 hidden) */}
          <div
            className={`flex-1 rounded-2xl border p-6 min-h-[500px] transition-all duration-700 bg-card border-border shadow-sm ${reportState !== 'result' ? 'hidden' : ''}`}
          >
            {/* idle UI(블러 대시보드 실루엣 + 3-step 가이드) 제거 — 좌측 옵션 패널이
                풀폭으로 노출되어 가이드 역할 자체가 의미 없어짐(2026-04-28). */}

            {/* loading UI(가짜 progress + ETA + 단계 ticker) 제거 — §3.7 거짓 신호 +
                좌측 옵션 패널 풀폭 가독성 ↑. 백그라운드 진행은 SimulationFloatingWidget 담당.
                결과 도착 시 runSim 함수가 setReportState('result')로 자동 전환. */}

            {reportState === 'result' && (
              <div className="absolute inset-0 z-40 bg-card text-foreground font-sans p-4 md:p-6 pt-24 md:pt-28 overflow-y-auto custom-scrollbar flex flex-col animate-[fadeSlideIn_0.8s_ease-out]">
                <div className="max-w-[1920px] w-full mx-auto flex flex-col gap-4 xl:px-10 2xl:px-16 transition-all duration-500 pb-12">
                  {/* Header & Nav */}
                  <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-4 shrink-0">
                    <div>
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <Zap className="w-5 h-5 text-primary" />
                        <h1 className="text-2xl md:text-3xl font-black tracking-tight text-foreground">
                          상권 분석 리포트
                        </h1>
                        {simResult?.winnerDistrict && (
                          <span className="ml-2 px-2.5 py-0.5 bg-primary/10 border border-primary/40 rounded-full text-[0.625rem] font-bold text-primary uppercase tracking-wider">
                            AI 추천 1위 · {simResult.winnerDistrict}
                          </span>
                        )}
                        {simResult?.vacancyApplied === false && (
                          <span
                            className="ml-2 px-2.5 py-0.5 bg-warning/10 border border-warning/40 rounded-full text-[0.625rem] font-bold text-warning uppercase tracking-wider"
                            title="공실 DB 로드 실패 — 랭킹에 공실 페널티 미반영"
                          >
                            공실 미반영
                          </span>
                        )}
                      </div>
                      <p className="text-muted-foreground text-sm">
                        서울특별시 마포구 {selectedDongs[0] || '연남동'} 일대 시뮬레이션 결과
                        {simResult?.topCandidates && simResult.topCandidates.length > 0 && (
                          <span className="ml-2 text-muted-foreground">
                            · Top 3: {simResult.topCandidates.join(', ')}
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => setIsSplitMode(!isSplitMode)}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[0.6875rem] font-bold transition-all duration-300 border ${
                          isSplitMode
                            ? 'bg-warning text-warning-foreground border-warning shadow-[0_0_15px_rgba(245,158,11,0.4)]'
                            : 'bg-card text-muted-foreground border-border hover:text-foreground hover:bg-muted'
                        }`}
                      >
                        {isSplitMode ? (
                          <X className="w-3.5 h-3.5" />
                        ) : (
                          <Columns className="w-3.5 h-3.5" />
                        )}
                        {isSplitMode ? '비교 모드 종료' : 'VS 비교 모드'}
                      </button>
                      <button
                        onClick={() => showToast('info', '과거 데이터 조회 기능은 준비 중입니다.')}
                        className="flex items-center gap-2 px-3 py-1.5 border border-border bg-card hover:bg-muted rounded-md text-xs font-medium transition-colors"
                      >
                        <Calendar className="w-3.5 h-3.5 text-muted-foreground" />{' '}
                        {reportMonthLabel}
                      </button>
                      {/* [시뮬 이력 저장] — 저장 성공 시 Document ID가 정식 번호로 격상됨 */}
                      {rawSimResult && (
                        <SaveButton
                          onClick={() => setSaveDialogOpen(true)}
                          saved={savedHistoryId != null}
                          label={
                            savedHistoryId != null
                              ? `저장됨 · ${formatDocumentId(savedHistoryId)}`
                              : undefined
                          }
                        />
                      )}
                      <div className="relative">
                        <button
                          onClick={() => setIsDownloadOpen(!isDownloadOpen)}
                          disabled={isGeneratingPDF || isGeneratingExcel}
                          className="flex items-center gap-2 px-3 py-2 bg-transparent border border-primary/60 text-primary hover:bg-primary/10 hover:border-primary rounded-lg text-[0.6875rem] font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <Download className="w-3.5 h-3.5" />
                          {isGeneratingPDF || isGeneratingExcel ? '생성 중...' : '다운로드'}
                          <ChevronDown className="w-3 h-3 ml-0.5 opacity-70" />
                        </button>
                        {isDownloadOpen && !isGeneratingPDF && !isGeneratingExcel && (
                          <>
                            <div
                              className="fixed inset-0 z-40"
                              onClick={() => setIsDownloadOpen(false)}
                            />
                            <div className="absolute right-0 mt-2 w-48 bg-card border border-border rounded-lg shadow-2xl py-1.5 z-50 flex flex-col gap-0.5">
                              <button
                                onClick={handleDownloadPDF}
                                className="w-full text-left px-3 py-2 text-xs text-foreground hover:bg-muted flex items-center gap-2 transition-colors group"
                              >
                                <FileText className="w-3.5 h-3.5 text-primary group-hover:scale-110 transition-transform" />{' '}
                                PDF 리포트{' '}
                                <span className="text-[0.625rem] text-muted-foreground ml-auto">
                                  보고용
                                </span>
                              </button>
                              <button
                                onClick={handleDownloadExcel}
                                className="w-full text-left px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted flex items-center gap-2 transition-colors group"
                              >
                                <Database className="w-3.5 h-3.5 text-primary group-hover:scale-110 transition-transform" />{' '}
                                Raw Data{' '}
                                <span className="text-[0.625rem] text-muted-foreground ml-auto">
                                  XLSX
                                </span>
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Split Mode: 최대 4패널 비교 뷰 (선택 동 수에 맞춰 동적) */}
                  {isSplitMode &&
                    (() => {
                      const panelDongs = selectedDongs.slice(0, 4);
                      const panelCount = panelDongs.length;
                      const gridClass =
                        panelCount <= 1
                          ? 'grid-cols-1'
                          : panelCount === 2
                            ? 'grid-cols-1 2xl:grid-cols-2'
                            : panelCount === 3
                              ? 'grid-cols-1 xl:grid-cols-3'
                              : 'grid-cols-1 xl:grid-cols-2 2xl:grid-cols-4';
                      const panelColors = [
                        'text-chart-1',
                        'text-chart-2',
                        'text-chart-3',
                        'text-chart-4',
                      ];

                      return (
                        <div className={`grid ${gridClass} gap-4 relative`}>
                          {panelDongs.map((dong, idx) => (
                            <DashboardPanelView
                              key={dong}
                              districtName={`마포구 ${dong}`}
                              isVariantB={idx > 0}
                              popData={popData}
                              dongName={dong}
                              accentOverride={panelColors[idx]}
                              panelIndex={idx}
                              simResult={simResult}
                            />
                          ))}
                        </div>
                      );
                    })()}

                  {/* [H4] 시뮬 완료 시 /dashboard 로 자동 이동 — useEffect 가 navigate 처리.
                      교체 직후 한 프레임 동안만 노출되는 placeholder. */}
                  {!isSplitMode && rawSimResult && (
                    <div className="flex items-center justify-center p-8 text-muted-foreground">
                      분석 결과로 이동 중...
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* RUN 버튼은 우5 패널의 핵심 파라미터 카드 밑으로 이동됨 (라인 ~1678 부근) */}
        </div>
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

      {/* 시뮬 이력 저장 다이얼로그 */}
      <SaveDialog
        open={saveDialogOpen}
        onClose={() => {
          setSaveDialogOpen(false);
          saveSim.reset();
        }}
        meta={{
          brandName: user?.company_name || simResult?.recommendation?.slice(0, 20) || '브랜드',
          district: selectedDongs[0] || '연남동',
          managerName: user?.contact_name || user?.email || '매니저',
        }}
        isSaving={saveSim.isSaving}
        errorMessage={saveSim.error}
        onConfirm={async (clientName) => {
          if (!rawSimResult) return;
          const compIntel = rawSimResult.competitor_intel as
            | Record<string, unknown>
            | null
            | undefined;
          const signalRaw = compIntel?.['market_entry_signal'];
          const signal =
            signalRaw === 'green' || signalRaw === 'yellow' || signalRaw === 'red'
              ? signalRaw
              : null;
          const verdictSummary =
            rawSimResult.ai_recommendation?.split(/[.!?。]/)[0]?.slice(0, 200) ??
            rawSimResult.analysis_report?.slice(0, 200) ??
            null;

          const res = await saveSim.save({
            client_name: clientName,
            district: selectedDongs[0] || '연남동',
            brand_name: brand?.brand_name || user?.company_name || '브랜드 미지정',
            business_type: businessType,
            scenario: null, // Phase 1: scenario 입력 UI 아직 없음
            simulation_result: rawSimResult,
            ai_verdict_summary: verdictSummary,
            market_entry_signal: signal,
          });
          if (res) {
            setSavedHistoryId(res.id);
            setSaveDialogOpen(false);
            showToast(
              'success',
              `${clientName} 고객님 시뮬 이력이 저장되었습니다. (${formatDocumentId(res.id)})`,
            );
          }
        }}
      />

      {/* [v12.0] Hidden A4 PDF Template — html2canvas 캡처용 (화면 밖) */}
      <HiddenPDFTemplate
        ref={pdfTemplateRef}
        districtFull={`마포구 ${rawSimResult?.winner_district || selectedDongs[0] || '연남동'}`}
        stats={(() => {
          const qp = rawSimResult?.quarterly_projection ?? [];
          const q1Rev = qp[0]?.revenue;
          const monthly = typeof q1Rev === 'number' ? Math.round(q1Rev / 3) : null;
          const growthTrend = (() => {
            if (qp.length < 2) return '';
            const a = qp[0]?.revenue ?? 0;
            const b = qp[1]?.revenue ?? 0;
            if (!a) return '';
            const g = ((b - a) / a) * 100;
            return `${g >= 0 ? '+' : ''}${g.toFixed(1)}% (Q2/Q1)`;
          })();
          const ci = rawSimResult?.competitor_intel as Record<string, any> | null | undefined;
          const cannImpact = ci?.cannibalization?.estimated_revenue_impact_pct;
          const cannSig = ci?.market_entry_signal;
          return [
            {
              title: '예상 월 매출 (추정)',
              value: monthly != null ? `₩ ${monthly.toLocaleString('ko-KR')}` : '—',
              trend: growthTrend,
            },
            {
              title: '상권 종합 매력도',
              value: simResult?.score != null ? `${Math.round(simResult.score)} / 100` : '—',
              trend: '',
            },
            {
              title: '일일 유동인구',
              value: popData?.daily_average ? `${popData.daily_average.toLocaleString()} 명` : '—',
              trend: popData?.date ? `기준 ${popData.date}` : '',
            },
            {
              title: '카니발리제이션 영향',
              value: typeof cannImpact === 'number' ? `${(cannImpact * 100).toFixed(1)}%` : '—',
              trend: typeof cannSig === 'string' ? cannSig : '',
            },
          ];
        })()}
        cannibalizationRows={sortedCannRows}
        neighborhoodRows={sortedNeighborhoodRows}
        insights={(() => {
          // 실데이터 기반 동적 조립 — 없으면 빈 배열 → PDF 페이지 4 empty state
          const items: {
            severity: 'critical' | 'advisory' | 'opportunity';
            title: string;
            desc: string;
          }[] = [];
          if (!rawSimResult) return items;

          // critical: 고위험 법률 1건
          const dangerRisk = (rawSimResult.legal_risks ?? []).find((r) => {
            const lvl = String(r.risk_level).toLowerCase();
            return lvl === 'high' || lvl === 'danger';
          });
          if (dangerRisk) {
            items.push({
              severity: 'critical',
              title: `법률 리스크: ${dangerRisk.type || '미분류'}`,
              desc:
                dangerRisk.detail ||
                dangerRisk.recommendation ||
                '해당 법률 위반 가능성이 감지되었습니다. drawer 에서 조문·체크리스트를 확인하세요.',
            });
          }

          // advisory: 피크 소비 시간대 (demographic_report.peak_consumption_hours)
          const demo = rawSimResult.demographic_report;
          const peak = demo?.peak_consumption_hours?.[0];
          if (peak) {
            items.push({
              severity: 'advisory',
              title: `피크 소비 시간대: ${peak}`,
              desc: `유동인구가 ${peak}에 집중. 해당 시간대 메뉴 및 인력 운영 최적화 권장.`,
            });
          }

          // opportunity: competitor_intel.key_opportunities 최상위 1건, 없으면 core_demographic 기반
          const ci = rawSimResult.competitor_intel as Record<string, any> | null | undefined;
          const firstOpp = ci?.key_opportunities?.[0];
          if (typeof firstOpp === 'string' && firstOpp.length > 0) {
            items.push({
              severity: 'opportunity',
              title: '경쟁 인텔 기회 요소',
              desc: firstOpp,
            });
          } else if (demo?.core_demographic) {
            const match = demo.brand_target_match_score;
            items.push({
              severity: 'opportunity',
              title: `핵심 소비층: ${demo.core_demographic.age} ${demo.core_demographic.gender}`,
              desc: `해당 타겟이 주 소비층입니다. 브랜드 매칭 점수 ${match != null ? Math.round(match) + '/100' : '—'}. ${demo.match_rationale ?? ''}`.trim(),
            });
          }

          return items;
        })()}
        reportDate={reportFullDate}
        savedHistoryId={savedHistoryId}
        customerSegment={rawSimResult?.customer_segment ?? null}
      />
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
function DashboardOutlet() {
  const simResult = useCombinedSimResult();
  const savedHistoryId = useSimulationStore((s) => s.savedHistoryId);
  const { user, brand } = useAuth();
  const brandName = user?.company_name || brand?.brand_name || '';
  const businessType: string | null = null;

  const [modalContent, setModalContent] = useState<DetailModalContent | null>(null);
  const openModal = (content: DetailModalContent) => setModalContent(content);

  if (!simResult) return <Navigate to="/simulator" replace />;

  return (
    <div
      data-dashboard-scroll
      className="relative h-screen overflow-y-scroll custom-scrollbar bg-background pb-16 text-foreground"
      style={{ overscrollBehaviorY: 'contain' }}
    >
      <Outlet context={{ simResult, brandName, businessType, savedHistoryId, openModal }} />
      <DetailModal modalContent={modalContent} onClose={() => setModalContent(null)} />
    </div>
  );
}

/** Hub index 라우트 — DashboardOutlet 의 simResult 를 store 에서 다시 읽어 DashboardHub 렌더.
 *  DashboardOutlet 의 null guard 가 이미 통과한 시점에서만 마운트되므로 simResult 는 항상 non-null. */
function DashboardHubRouteElement() {
  const simResult = useCombinedSimResult();
  const savedHistoryId = useSimulationStore((s) => s.savedHistoryId);
  const { user, brand } = useAuth();
  if (!simResult) return <Navigate to="/simulator" replace />;
  return (
    <DashboardHub
      simResult={simResult}
      brandName={user?.company_name || brand?.brand_name || ''}
      savedHistoryId={savedHistoryId}
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
                  {/* 저장된 시뮬 이력 재현 — 본인 이력만 조회 가능 (백엔드 권한 검증) */}
                  <Route
                    path="/dashboard/history/:id"
                    element={
                      <ProtectedRoute>
                        <SimulationHistoryDetail />
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
        </ToastProvider>
      </ManagerListProvider>
    </AuthProvider>
  );
}
