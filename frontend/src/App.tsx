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
 *   - System A 배경/구조 6색 (warm-white #FAF9F5 / 카드 #FFFFFF / cream #F8F7E8 등 중립 인프라)
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
import { useAbmStore } from './stores/abmStore';
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
  const [popLoading, setPopLoading] = useState(false);

  // [ABM] 행동 시뮬레이션 — useAbmStore (zustand+persist+AbortController) 로 이관.
  // 새로고침/탭 이동/dashboardMode 토글에도 in-flight 시뮬 결과를 잃지 않음.
  const abmResult = useAbmStore((s) => s.result);
  const abmStatus = useAbmStore((s) => s.status);
  const abmError = useAbmStore((s) => s.error);
  const abmFocusSpot = useAbmStore((s) => s.focusSpot);
  const startAbm = useAbmStore((s) => s.startAbm);
  const dismissAbmResult = useAbmStore((s) => s.dismissResult);
  const setAbmFocusSpot = useAbmStore((s) => s.setFocusSpot);
  const resumeAbmPolling = useAbmStore((s) => s.resumePollingIfNeeded);
  const abmLoading = abmStatus === 'running';

  // mount 시 persist 복원된 running jobId 가 있으면 polling 재개.
  useEffect(() => {
    resumeAbmPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

                  {/* Single Mode: 기존 (legacy) 대시보드 — 사실상 dead code.
                    · viewMode 는 line 828 에서 'integrated' 로 고정 → 'legacy' 절대 true 아님.
                    · 2026-04-30 fix: `|| !rawSimResult` 제거. hydration 중 일시 null 일 때
                      이 블록이 렌더되어 H7 후 삭제됐어야 할 옛 디자인이 새로고침/홈 이동 후
                      다시 노출되던 회귀 버그(약 1,800줄 옛 JSX) 해소.
                    · 옛 JSX 블록 자체 (line 2222~) 는 별도 cycle 에서 완전 제거 예정. */}
                  {!isSplitMode && viewMode === 'legacy' && (
                    <>
                      {/* [C1 신규] AI Verdict 신호등 배너 — signal + 한 줄 판단
                        · map 뷰에서는 숨김 (AI 에이전트 맵 화면 간결성)
                        · data 뷰에서는 기본 접힘 → 한 줄평만, 클릭 시 전체 설명 펼침 */}
                      {(() => {
                        if (dashboardMode !== 'data') return null;

                        // LLM이 출력한 영어 리스크 용어를 한국어로 치환
                        const localizeRiskTerms = (text: string) =>
                          text
                            .replace(/'caution'/g, "'주의'")
                            .replace(/'safe'/g, "'안전'")
                            .replace(/'danger'/g, "'위험'")
                            .replace(/'green'/g, "'진입 권장'")
                            .replace(/'yellow'/g, "'조건부 진입'")
                            .replace(/'red'/g, "'진입 비권장'")
                            .replace(/\bcaution\b/g, '주의 단계')
                            .replace(/\bdanger\b/g, '위험 단계')
                            .replace(/\bsparse\b/g, '희박')
                            .replace(/\bsaturated\b/g, '포화')
                            .replace(/\bEXCELLENT\b/g, '탁월')
                            .replace(/\bGOOD\b/g, '우수')
                            .replace(/\bNORMAL\b/g, '보통')
                            .replace(/\bRISKY\b/g, '주의');

                        const rawRec = simResult?.recommendation;
                        const rec = rawRec ? localizeRiskTerms(rawRec) : rawRec;
                        const legalRisk = simResult?.overallLegalRisk;
                        const ciSignal = simResult?.competitorIntel?.market_entry_signal;
                        // signal 없고 recommendation도 없으면 렌더 안 함
                        if (!rec && !legalRisk && !ciSignal) return null;

                        // signal: competitor_intel 우선, 없으면 overall_legal_risk 매핑.
                        // 신호가 어느 쪽에서도 없으면 null → 중립 렌더.
                        let signal: 'green' | 'yellow' | 'red' | null = null;
                        if (ciSignal === 'green' || ciSignal === 'yellow' || ciSignal === 'red') {
                          signal = ciSignal;
                        } else if (legalRisk === 'safe') signal = 'green';
                        else if (legalRisk === 'danger') signal = 'red';
                        else if (legalRisk === 'caution') signal = 'yellow';

                        const sigCfg: Record<
                          'green' | 'yellow' | 'red',
                          {
                            icon: JSX.Element;
                            label: string;
                            border: string;
                            badge: string;
                            iconBg: string;
                          }
                        > = {
                          green: {
                            icon: <CheckCircle2 className="h-6 w-6 text-emerald-400" />,
                            // [I-7] colorblind 대응 — 영문 GREEN → 한글 '안전'
                            label: '안전',
                            border: 'border-emerald-500/30',
                            badge: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40',
                            iconBg: 'bg-emerald-500/10 ring-1 ring-emerald-500/30',
                          },
                          yellow: {
                            icon: <AlertTriangle className="h-6 w-6 text-amber-400" />,
                            // [I-7] colorblind 대응 — 영문 YELLOW → 한글 '주의'
                            label: '주의',
                            border: 'border-amber-500/30',
                            badge: 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40',
                            iconBg: 'bg-amber-500/10 ring-1 ring-amber-500/30',
                          },
                          red: {
                            icon: <ShieldAlert className="h-6 w-6 text-rose-400" />,
                            // [I-7] colorblind 대응 — 영문 RED → 한글 '위험'
                            label: '위험',
                            border: 'border-rose-500/30',
                            badge: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40',
                            iconBg: 'bg-rose-500/10 ring-1 ring-rose-500/30',
                          },
                        };
                        const cfg = signal ? sigCfg[signal] : null;

                        // headline: rec의 첫 문장 or 첫 60자 + '…'
                        let oneLiner = '';
                        if (rec) {
                          // 한글/영문 문장 끝 문자 매칭 (trailing whitespace 없이도 OK)
                          const firstSentence = rec.match(/^(.+?[.!?。])(?:\s|$)/);
                          if (firstSentence && firstSentence[1].length <= 80) {
                            oneLiner = firstSentence[1].trim();
                          } else {
                            oneLiner = rec.length > 60 ? rec.slice(0, 60).trim() + '…' : rec;
                          }
                        }
                        // rec이 oneLiner로 시작하면 꼬리만 표시 (중복 렌더 방지)
                        const tailOfRec =
                          rec && oneLiner && rec.startsWith(oneLiner)
                            ? rec.slice(oneLiner.length).trim()
                            : rec;

                        const borderCls = cfg ? cfg.border : 'border-[#3a3633]';

                        return (
                          <div
                            className={`mb-2 overflow-hidden rounded-xl border ${borderCls} bg-[#2c2825] p-5 shadow-xl`}
                          >
                            <div className="flex items-start gap-4">
                              {cfg && (
                                <div
                                  className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl ${cfg.iconBg}`}
                                >
                                  {cfg.icon}
                                </div>
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <h3 className="text-sm font-semibold uppercase tracking-widest text-[#9ca3af]">
                                    AI VERDICT
                                  </h3>
                                  {cfg && (
                                    <span
                                      className={`rounded-full px-2 py-0.5 text-xs font-bold ${cfg.badge}`}
                                    >
                                      {cfg.label}
                                    </span>
                                  )}
                                </div>
                                {oneLiner && (
                                  <p className="mt-2 text-base font-semibold leading-snug text-[#e2e8f0]">
                                    {oneLiner}
                                  </p>
                                )}
                                {tailOfRec && tailOfRec !== oneLiner && (
                                  <details className="mt-2 group">
                                    <summary className="cursor-pointer text-xs text-cyan-400 hover:text-cyan-300 font-mono select-none">
                                      상세보기
                                    </summary>
                                    <p className="mt-2 text-sm leading-relaxed text-[#e2e8f0]">
                                      {tailOfRec}
                                    </p>
                                  </details>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })()}

                      {/* Main Dashboard Body — dashboardMode 토글 (data | map | abm) */}
                      {dashboardMode === 'data' ? (
                        <div className="flex flex-col gap-4 h-full animate-in fade-in duration-500">
                          {/* 4 Stats Cards — data 뷰에서만 표시 */}
                          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
                            {/* §3.7 — 데이터 없을 때 임의 default 금지. mock trend/등급/인구 모두 '—'. */}
                            <StatCard
                              onClick={() => setActiveDrawer('revenue')}
                              title="예상 월 총매출"
                              value={
                                simResult?.revenue != null
                                  ? `₩ ${(simResult.revenue * 10000).toLocaleString()}`
                                  : '—'
                              }
                              trend="—"
                              trendUp={true}
                              icon={<BarChart3 />}
                              sparkline="M 0 20 Q 10 5, 20 15 T 40 10 T 60 25 T 80 5 T 100 0"
                              subtitle={
                                simResult?.netProfit != null
                                  ? `순이익 ${simResult.netProfit}만원`
                                  : undefined
                              }
                            />
                            <StatCard
                              onClick={() => setActiveDrawer('attractiveness')}
                              title="상권 종합 매력도"
                              value={simResult?.score != null ? `${simResult.score} / 100` : '—'}
                              trend="—"
                              trendUp={true}
                              icon={<Crosshair />}
                              sparkline="M 0 25 Q 15 20, 30 10 T 60 15 T 80 5 T 100 0"
                            />
                            <StatCard
                              onClick={() => setActiveDrawer('traffic')}
                              title="일일 유동인구"
                              value={
                                popData?.daily_average
                                  ? `${popData.daily_average.toLocaleString()} 명`
                                  : popLoading
                                    ? '로딩중...'
                                    : '—'
                              }
                              trend={
                                popData?.change_pct !== undefined
                                  ? `${popData.change_pct > 0 ? '+' : ''}${popData.change_pct}%`
                                  : '—'
                              }
                              trendUp={popData?.change_pct ? popData.change_pct > 0 : false}
                              icon={<Users />}
                              sparkline="M 0 5 Q 15 10, 30 20 T 60 15 T 80 25 T 100 30"
                              subtitle={popData?.date ?? ''}
                            />
                            <StatCard
                              onClick={() => setActiveDrawer('cannibalization')}
                              title="카니발리제이션 위험"
                              value={simResult?.riskLevel != null ? simResult.riskLevel : '—'}
                              trend="—"
                              trendUp={true}
                              icon={<AlertTriangle className="text-indigo-400" />}
                              sparkline="M 0 30 Q 20 25, 40 28 T 80 25 T 100 30"
                            />
                          </div>

                          {/* Charts / Table / Radar / Insights */}
                          <div className="flex-1 flex flex-col lg:flex-row gap-4 min-h-0">
                            {/* Left Column */}
                            <div className="lg:flex-[2] flex flex-col gap-4">
                              {/* Chart */}
                              <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 pb-10 shadow-xl flex flex-col h-[320px]">
                                <div className="flex justify-between items-end mb-4">
                                  <div>
                                    <h2 className="text-sm font-bold text-white">
                                      {chartView === 'daily'
                                        ? '시간대별 유동인구 및 매출 (24H)'
                                        : 'LSTM 12개월 매출 추이 예측 (12M)'}
                                    </h2>
                                    <p className="text-[0.6875rem] text-[#9ca3af]">
                                      {chartView === 'daily'
                                        ? '경쟁점 데이터 및 배후세대 동선 분석 기준'
                                        : 'AI 엔진을 통한 향후 1년간의 매출 예측값'}
                                    </p>
                                  </div>
                                  <div className="flex bg-[#1e1b18] rounded-md border border-[#3a3633] p-0.5">
                                    <button
                                      onClick={() => setChartView('daily')}
                                      className={`px-3 py-1 text-[0.625rem] font-bold rounded transition-colors ${chartView === 'daily' ? 'bg-[#3a3633] text-indigo-400' : 'text-[#9ca3af] hover:text-white'}`}
                                    >
                                      24H 분석
                                    </button>
                                    <button
                                      onClick={() => setChartView('monthly')}
                                      className={`px-3 py-1 text-[0.625rem] font-bold rounded transition-colors ${chartView === 'monthly' ? 'bg-[#3a3633] text-indigo-400' : 'text-[#9ca3af] hover:text-white'}`}
                                    >
                                      12M 예측
                                    </button>
                                  </div>
                                </div>
                                <div
                                  onClick={() => setActiveDrawer('traffic')}
                                  className="flex-1 relative w-full cursor-pointer group/chart hover:bg-[#818cf8]/[0.03] rounded-lg transition-colors min-h-0"
                                >
                                  {/* empty state — 24H 시간대 분석은 백엔드 미구현, 12M 예측은 quarterly_projection 없을 때 */}
                                  {(chartView === 'daily' ||
                                    (chartView === 'monthly' && monthlyChartData.length === 0)) && (
                                    <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg border border-dashed border-[#3a3633] bg-[#1e1b18]/60 backdrop-blur-[2px]">
                                      <div className="text-center max-w-xs px-4">
                                        <div className="mx-auto mb-2 h-6 w-6 animate-pulse rounded-full bg-[#3a3633]" />
                                        <div className="text-xs font-semibold text-[#e2e8f0]">
                                          구현 예정
                                        </div>
                                        <div className="mt-1 text-[0.625rem] text-[#9ca3af] leading-relaxed">
                                          {chartView === 'daily'
                                            ? '시간대별 매출·유동인구 API 연동 대기 중'
                                            : '분기 매출 예측 — 시뮬레이션 완료 후 표시됩니다'}
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                  <motion.div
                                    key={`chart-reveal-${chartView}`}
                                    initial={{ clipPath: 'inset(0 100% 0 0)' }}
                                    animate={{ clipPath: 'inset(0 0 0 0)' }}
                                    transition={{ duration: 1.4, ease: 'linear' }}
                                    className="w-full h-full"
                                  >
                                    <ResponsiveContainer width="100%" height="100%">
                                      <AreaChart
                                        data={chartView === 'daily' ? [] : monthlyChartData}
                                        margin={{ top: 10, right: 15, left: -20, bottom: 0 }}
                                      >
                                        <defs>
                                          <linearGradient
                                            id="rcRevenueGradient"
                                            x1="0"
                                            y1="0"
                                            x2="0"
                                            y2="1"
                                          >
                                            <stop
                                              offset="0%"
                                              stopColor="#818cf8"
                                              stopOpacity={0.5}
                                            />
                                            <stop
                                              offset="100%"
                                              stopColor="#818cf8"
                                              stopOpacity={0}
                                            />
                                          </linearGradient>
                                          <linearGradient
                                            id="rcTrafficGradient"
                                            x1="0"
                                            y1="0"
                                            x2="0"
                                            y2="1"
                                          >
                                            <stop
                                              offset="0%"
                                              stopColor="#9ca3af"
                                              stopOpacity={0.2}
                                            />
                                            <stop
                                              offset="100%"
                                              stopColor="#9ca3af"
                                              stopOpacity={0}
                                            />
                                          </linearGradient>
                                        </defs>
                                        <XAxis
                                          dataKey="time"
                                          type="number"
                                          domain={['dataMin', 'dataMax']}
                                          scale={chartView === 'daily' ? 'time' : 'linear'}
                                          tickFormatter={(t: number) => {
                                            if (chartView === 'daily') {
                                              const d = new Date(t);
                                              return `${String(d.getHours() % 24).padStart(2, '0')}:00`;
                                            }
                                            // 분기 모드: quarterlyProjection 있으면 "1Q..4Q", 없으면 (mock) "1월..12월"
                                            return simResult?.quarterlyProjection?.length
                                              ? `${t}Q`
                                              : `${new Date(t).getMonth() + 1}월`;
                                          }}
                                          stroke="#9ca3af"
                                          fontSize={10}
                                          tickLine={false}
                                          axisLine={false}
                                          tick={{ fill: '#d1d5db' }}
                                        />
                                        <RechartsTooltipWrapper
                                          content={<RechartsDarkTooltip chartMode={chartView} />}
                                          cursor={{
                                            stroke: '#818cf8',
                                            strokeWidth: 1,
                                            strokeDasharray: '4 4',
                                          }}
                                        />
                                        <Area
                                          type="monotone"
                                          dataKey="traffic"
                                          stroke="#d1d5db"
                                          strokeWidth={2}
                                          fill="url(#rcTrafficGradient)"
                                          isAnimationActive={false}
                                        />
                                        <Area
                                          type="monotone"
                                          dataKey="revenue"
                                          stroke="#818cf8"
                                          strokeWidth={3}
                                          fill="url(#rcRevenueGradient)"
                                          isAnimationActive={false}
                                        />
                                        {/* 분기 모드 + 실응답에 confidence_upper 있을 때 신뢰 상한선 점선 */}
                                        {chartView === 'monthly' &&
                                          simResult?.quarterlyProjection?.length && (
                                            <Area
                                              type="monotone"
                                              dataKey="confidence_upper"
                                              stroke="#818cf8"
                                              strokeWidth={1}
                                              strokeDasharray="3 3"
                                              fill="none"
                                              isAnimationActive={false}
                                            />
                                          )}
                                      </AreaChart>
                                    </ResponsiveContainer>
                                  </motion.div>
                                </div>
                              </div>

                              {/* 분기별 매출 예측 차트 (TCN 모델 출력) — quarterly_projection 있을 때만 렌더링 */}
                              {simResult?.quarterlyProjection &&
                                simResult.quarterlyProjection.length > 0 && (
                                  <div className="mt-6">
                                    <h3 className="text-lg font-semibold mb-3">분기별 예상 매출</h3>
                                    <QuarterlyProjectionChart
                                      series={[
                                        {
                                          district:
                                            simResult.winnerDistrict ??
                                            rawSimResult?.target_district ??
                                            '단일',
                                          projection: simResult.quarterlyProjection,
                                        },
                                      ]}
                                      winnerDistrict={simResult.winnerDistrict}
                                    />
                                  </div>
                                )}

                              {/* SHAP 피처 기여도 차트 — shapResult 있을 때만 렌더링 */}
                              {simResult?.shapResult && (
                                <div className="mt-6">
                                  <h3 className="text-lg font-semibold mb-3">
                                    매출 기여 피처 분석 (SHAP)
                                  </h3>
                                  <ShapChart data={simResult.shapResult} />
                                </div>
                              )}

                              {/* [C1 신규] 향후 12개월 전망 카드 (trend_forecaster) */}
                              {(() => {
                                const tf = simResult?.trendForecast;
                                if (!tf) return null;
                                const score = tf.forecast?.score;
                                const direction = tf.forecast?.direction;
                                const confidence = tf.forecast?.confidence;
                                const narrative = tf.forecast?.narrative;
                                const industryDir = tf.industry_trend?.direction;
                                const changeIxLabel = tf.change_ix?.change_ix_label;
                                // 최소 데이터도 없으면 렌더 안 함
                                if (
                                  score == null &&
                                  !direction &&
                                  !narrative &&
                                  !industryDir &&
                                  !changeIxLabel
                                ) {
                                  return null;
                                }
                                const directionCfg: Record<string, { label: string; cls: string }> =
                                  {
                                    strong_growth: {
                                      label: '↑↑ STRONG GROWTH',
                                      cls: 'bg-emerald-500/30 text-emerald-200 ring-1 ring-emerald-400/60',
                                    },
                                    growth: {
                                      label: '↑ GROWTH',
                                      cls: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40',
                                    },
                                    stable: {
                                      label: '→ STABLE',
                                      cls: 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40',
                                    },
                                    decline: {
                                      label: '↓ DECLINE',
                                      cls: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40',
                                    },
                                    strong_decline: {
                                      label: '↓↓ STRONG DECLINE',
                                      cls: 'bg-rose-500/30 text-rose-200 ring-1 ring-rose-400/60',
                                    },
                                  };
                                const dirBadge = direction
                                  ? (directionCfg[direction] ?? {
                                      label: direction,
                                      cls: 'bg-slate-500/20 text-slate-300 ring-1 ring-slate-500/40',
                                    })
                                  : null;
                                const industryDirLabel =
                                  industryDir === 'up'
                                    ? '↑ 상승'
                                    : industryDir === 'down'
                                      ? '↓ 하락'
                                      : industryDir === 'flat'
                                        ? '→ 보합'
                                        : 'N/A';
                                return (
                                  <div className="mt-6 rounded-xl border border-[#3a3633] bg-[#2c2825] p-5 shadow-xl">
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-2">
                                        <TrendingUp className="h-4 w-4 text-[#818cf8]" />
                                        <h3 className="text-sm font-semibold uppercase tracking-widest text-[#9ca3af]">
                                          향후 12개월 전망
                                        </h3>
                                      </div>
                                      {confidence && (
                                        <span className="text-xs text-[#9ca3af]">
                                          신뢰도: {confidence}
                                        </span>
                                      )}
                                    </div>

                                    {(score != null || dirBadge) && (
                                      <div className="mt-3 flex items-baseline gap-3 flex-wrap">
                                        {score != null && (
                                          <>
                                            <span className="text-4xl font-bold font-mono tabular-nums text-[#e2e8f0]">
                                              {Math.round(score)}
                                            </span>
                                            <span className="text-sm text-[#9ca3af]">/100</span>
                                          </>
                                        )}
                                        {dirBadge && (
                                          <span
                                            className={`rounded-full px-2 py-0.5 text-xs font-bold ${dirBadge.cls}`}
                                          >
                                            {dirBadge.label}
                                          </span>
                                        )}
                                      </div>
                                    )}

                                    <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                                      <div className="rounded-lg bg-[#1e1b18]/50 p-3">
                                        <div className="text-[#9ca3af]">업종 트렌드</div>
                                        <div className="mt-1 font-semibold text-[#e2e8f0]">
                                          {industryDirLabel}
                                        </div>
                                      </div>
                                      <div className="rounded-lg bg-[#1e1b18]/50 p-3">
                                        <div className="text-[#9ca3af]">상권 분류</div>
                                        <div className="mt-1 font-semibold text-[#e2e8f0]">
                                          {changeIxLabel ?? 'N/A'}
                                        </div>
                                      </div>
                                    </div>

                                    {narrative && (
                                      <p className="mt-4 text-sm leading-relaxed text-[#e2e8f0]">
                                        {narrative}
                                      </p>
                                    )}
                                  </div>
                                );
                              })()}

                              {/* [C1 신규] 경쟁 + 잠식 분석 풀 카드 (competitor_intel) */}
                              {(() => {
                                const ci = simResult?.competitorIntel;
                                if (!ci) return null;
                                const comp = ci.competition_500m;
                                const cann = ci.cannibalization;
                                const signal = ci.market_entry_signal;
                                const diff = ci.differentiation_position;
                                const opps = ci.key_opportunities ?? [];
                                const risks = ci.key_risks ?? [];
                                const actions = ci.recommended_actions ?? [];
                                const narrative = ci.narrative;
                                // 최소 콘텐츠 없으면 렌더 안 함
                                if (
                                  !comp &&
                                  !cann &&
                                  !signal &&
                                  !diff &&
                                  opps.length === 0 &&
                                  risks.length === 0 &&
                                  actions.length === 0 &&
                                  !narrative
                                ) {
                                  return null;
                                }
                                const sigBadgeCfg: Record<string, { cls: string; label: string }> =
                                  {
                                    green: {
                                      cls: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/50',
                                      label: '진입 권장',
                                    },
                                    yellow: {
                                      cls: 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/50',
                                      label: '조건부',
                                    },
                                    red: {
                                      cls: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/50',
                                      label: '비권장',
                                    },
                                  };
                                const sigBadge = signal ? sigBadgeCfg[signal] : null;
                                const cannImpactPct =
                                  typeof cann?.estimated_revenue_impact_pct === 'number'
                                    ? (cann.estimated_revenue_impact_pct * 100).toFixed(1)
                                    : null;
                                const SATURATION_KO: Record<string, string> = {
                                  sparse: '희박 (0~2개)',
                                  low: '낮음 (3~5개)',
                                  medium: '보통 (6~10개)',
                                  high: '높음 (11~20개)',
                                  saturated: '포화 (21개+)',
                                };
                                const satKo = comp?.saturation_level
                                  ? (SATURATION_KO[comp.saturation_level] ?? comp.saturation_level)
                                  : 'N/A';
                                return (
                                  <div className="rounded-xl border border-[#3a3633] bg-[#2c2825] p-5 shadow-xl">
                                    <div className="flex items-center justify-between flex-wrap gap-2">
                                      <div className="flex items-center gap-2">
                                        <Crosshair className="h-4 w-4 text-[#818cf8]" />
                                        <h3 className="text-sm font-semibold uppercase tracking-widest text-[#9ca3af]">
                                          경쟁 + 잠식 분석
                                        </h3>
                                      </div>
                                      {sigBadge && (
                                        <span
                                          className={`rounded-full px-3 py-1 text-xs font-bold uppercase ${sigBadge.cls}`}
                                        >
                                          {sigBadge.label}
                                        </span>
                                      )}
                                    </div>

                                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
                                      <div className="rounded-lg bg-[#1e1b18]/50 p-3">
                                        <div className="text-xs text-[#9ca3af]">500m 경쟁 밀도</div>
                                        <div className="mt-1 text-base font-semibold text-[#e2e8f0]">
                                          {satKo}
                                        </div>
                                        <div className="text-xs text-slate-500">
                                          총 {comp?.total_competitors ?? 0}개 매장
                                        </div>
                                      </div>
                                      <div className="rounded-lg bg-[#1e1b18]/50 p-3">
                                        <div className="text-xs text-[#9ca3af]">자기잠식 영향</div>
                                        <div className="mt-1 text-lg font-semibold text-rose-300">
                                          {cannImpactPct != null
                                            ? `매출 ${cannImpactPct}% 감소`
                                            : 'N/A'}
                                        </div>
                                        <div className="text-xs text-slate-500">
                                          500m 내 동일 브랜드 기준
                                        </div>
                                      </div>
                                      <div className="rounded-lg bg-[#1e1b18]/50 p-3">
                                        <div className="text-xs text-[#9ca3af]">
                                          프랜차이즈 / 개인점
                                        </div>
                                        <div className="mt-1 text-lg font-semibold text-[#e2e8f0]">
                                          {comp?.franchise_count ?? 0}개 /{' '}
                                          {comp?.independent_count ?? 0}개
                                        </div>
                                        <div className="text-xs text-slate-500">
                                          체인 브랜드 / 로컬 매장
                                        </div>
                                      </div>
                                    </div>

                                    {diff && (
                                      <div className="mt-4 rounded-lg bg-[#818cf8]/10 p-3 ring-1 ring-[#818cf8]/30">
                                        <div className="text-xs uppercase tracking-wider text-[#a5b4fc]">
                                          차별화 포지션
                                        </div>
                                        <p className="mt-1 text-sm text-[#e2e8f0]">{diff}</p>
                                      </div>
                                    )}

                                    {(opps.length > 0 || risks.length > 0) && (
                                      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                                        {opps.length > 0 && (
                                          <div>
                                            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-400">
                                              <Lightbulb className="h-4 w-4 text-emerald-400" />
                                              <span>기회</span>
                                            </div>
                                            <ul className="mt-2 space-y-1">
                                              {opps.map((o, i) => (
                                                <li key={i} className="text-xs text-[#e2e8f0]">
                                                  • {o}
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                        {risks.length > 0 && (
                                          <div>
                                            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-rose-400">
                                              <AlertTriangle className="h-4 w-4 text-rose-400" />
                                              <span>리스크</span>
                                            </div>
                                            <ul className="mt-2 space-y-1">
                                              {risks.map((r, i) => (
                                                <li key={i} className="text-xs text-[#e2e8f0]">
                                                  • {r}
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                      </div>
                                    )}

                                    {actions.length > 0 && (
                                      <div className="mt-4 rounded-lg bg-amber-500/10 p-3 ring-1 ring-amber-500/30">
                                        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-amber-400">
                                          <ClipboardList className="h-4 w-4 text-amber-400" />
                                          <span>추천 액션</span>
                                        </div>
                                        <ul className="mt-2 space-y-1">
                                          {actions.map((a, i) => (
                                            <li key={i} className="text-xs text-[#e2e8f0]">
                                              <span className="font-bold text-amber-300">
                                                {i + 1}.
                                              </span>{' '}
                                              {a}
                                            </li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}

                                    {narrative && (
                                      <p className="mt-4 text-xs leading-relaxed text-[#9ca3af]">
                                        {narrative}
                                      </p>
                                    )}
                                  </div>
                                );
                              })()}

                              {/* Table */}
                              <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl shadow-xl flex flex-col">
                                <div className="p-5 border-b border-[#3a3633] flex justify-between items-center">
                                  <h2 className="text-sm font-bold text-white flex items-center gap-2">
                                    상세 데이터 테이블
                                    <span className="hidden md:inline-block px-1.5 py-0.5 bg-[#3a3633] text-[#9ca3af] text-[0.5625rem] rounded uppercase font-mono">
                                      {tableDensity} view
                                    </span>
                                  </h2>
                                  <div className="flex items-center gap-3">
                                    {/* 밀도 조절 */}
                                    <div className="hidden sm:flex bg-[#1e1b18] rounded-md border border-[#3a3633] p-0.5">
                                      <button
                                        onClick={() => setTableDensity('comfortable')}
                                        title="넓게 보기"
                                        className={`p-1 rounded transition-colors ${tableDensity === 'comfortable' ? 'bg-[#3a3633] text-[#818cf8]' : 'text-[#9ca3af] hover:text-white'}`}
                                      >
                                        <Rows3 className="w-3.5 h-3.5" />
                                      </button>
                                      <button
                                        onClick={() => setTableDensity('standard')}
                                        title="보통"
                                        className={`p-1 rounded transition-colors ${tableDensity === 'standard' ? 'bg-[#3a3633] text-[#818cf8]' : 'text-[#9ca3af] hover:text-white'}`}
                                      >
                                        <AlignJustify className="w-3.5 h-3.5" />
                                      </button>
                                      <button
                                        onClick={() => setTableDensity('compact')}
                                        title="좁게 보기"
                                        className={`p-1 rounded transition-colors ${tableDensity === 'compact' ? 'bg-[#3a3633] text-[#818cf8]' : 'text-[#9ca3af] hover:text-white'}`}
                                      >
                                        <List className="w-3.5 h-3.5" />
                                      </button>
                                    </div>
                                    {/* 테이블 종류 토글 */}
                                    <div className="flex bg-[#1e1b18] rounded-md border border-[#3a3633] p-0.5">
                                      <button
                                        onClick={() => handleTableViewChange('cannibalization')}
                                        className={`px-3 py-1 text-[0.625rem] font-bold rounded transition-colors ${tableView === 'cannibalization' ? 'bg-[#3a3633] text-indigo-400' : 'text-[#9ca3af] hover:text-white'}`}
                                      >
                                        가맹점 간섭도
                                      </button>
                                      <button
                                        onClick={() => handleTableViewChange('neighborhoods')}
                                        className={`px-3 py-1 text-[0.625rem] font-bold rounded transition-colors ${tableView === 'neighborhoods' ? 'bg-[#3a3633] text-indigo-400' : 'text-[#9ca3af] hover:text-white'}`}
                                      >
                                        행정동 비교
                                      </button>
                                    </div>
                                  </div>
                                </div>
                                <div>
                                  <table className="w-full text-left border-collapse">
                                    <thead className="sticky top-0 bg-[#1e1b18]/90 backdrop-blur-sm z-10">
                                      <tr className="text-[0.6875rem] font-mono text-[#9ca3af] uppercase tracking-wider">
                                        {tableView === 'cannibalization' ? (
                                          <>
                                            <th className="p-3 pl-5 font-medium">
                                              <SortHeader
                                                label="가맹점명"
                                                sortField="name"
                                                sortKey={sortKey}
                                                sortDir={sortDir}
                                                onSort={handleSort}
                                              />
                                            </th>
                                            <th className="p-3 font-medium">
                                              <SortHeader
                                                label="거리"
                                                sortField="distance"
                                                sortKey={sortKey}
                                                sortDir={sortDir}
                                                onSort={handleSort}
                                              />
                                            </th>
                                            <th className="p-3 font-medium">
                                              <SortHeader
                                                label="예상 매출 하락"
                                                sortField="impact"
                                                sortKey={sortKey}
                                                sortDir={sortDir}
                                                onSort={handleSort}
                                              />
                                            </th>
                                            <th className="p-3 font-medium">
                                              <SortHeader
                                                label="상태"
                                                sortField="status"
                                                sortKey={sortKey}
                                                sortDir={sortDir}
                                                onSort={handleSort}
                                              />
                                            </th>
                                          </>
                                        ) : (
                                          <>
                                            <th className="p-3 pl-5 font-medium">
                                              <SortHeader
                                                label="행정동"
                                                sortField="name"
                                                sortKey={sortKey}
                                                sortDir={sortDir}
                                                onSort={handleSort}
                                              />
                                            </th>
                                            <th className="p-3 font-medium">
                                              <SortHeader
                                                label="AI 점수"
                                                sortField="score"
                                                sortKey={sortKey}
                                                sortDir={sortDir}
                                                onSort={handleSort}
                                              />
                                            </th>
                                            <th className="p-3 font-medium">
                                              <SortHeader
                                                label="폐업률"
                                                sortField="closureRate"
                                                sortKey={sortKey}
                                                sortDir={sortDir}
                                                onSort={handleSort}
                                              />
                                            </th>
                                            <th className="p-3 font-medium">
                                              <SortHeader
                                                label="예상 BEP"
                                                sortField="bep"
                                                sortKey={sortKey}
                                                sortDir={sortDir}
                                                onSort={handleSort}
                                              />
                                            </th>
                                          </>
                                        )}
                                      </tr>
                                    </thead>
                                    <tbody className="text-xs divide-y divide-[#3a3633]">
                                      {tableView === 'cannibalization' ? (
                                        sortedCannRows.length === 0 ? (
                                          <tr>
                                            <td
                                              colSpan={4}
                                              className="py-8 text-center text-xs text-[#9ca3af]"
                                            >
                                              카니발리제이션 데이터 없음 — 500m 반경 내 경쟁 매장이
                                              없거나 분석 대상 지역 밖입니다.
                                            </td>
                                          </tr>
                                        ) : (
                                          sortedCannRows.map((row, i) => (
                                            <TableRow
                                              key={row.name}
                                              index={i}
                                              expanded={expandedRow === i}
                                              onToggle={() =>
                                                setExpandedRow(expandedRow === i ? null : i)
                                              }
                                              icon={<Store className="w-3.5 h-3.5" />}
                                              col1={row.name}
                                              col2={row.distance}
                                              col3={row.impact}
                                              status={row.status}
                                              density={tableDensity}
                                            />
                                          ))
                                        )
                                      ) : sortedNeighborhoodRows.length === 0 ? (
                                        <tr>
                                          <td
                                            colSpan={4}
                                            className="py-8 text-center text-xs text-[#9ca3af]"
                                          >
                                            행정동 비교 데이터 없음 — 시뮬레이션을 실행해 주세요.
                                          </td>
                                        </tr>
                                      ) : (
                                        sortedNeighborhoodRows.map((row, i) => (
                                          <TableRow
                                            key={row.name}
                                            index={i}
                                            expanded={expandedRow === i}
                                            onToggle={() =>
                                              setExpandedRow(expandedRow === i ? null : i)
                                            }
                                            icon={<MapPin className="w-3.5 h-3.5" />}
                                            col1={row.name}
                                            col2={row.score}
                                            col3={row.closureRate}
                                            status={row.bep}
                                            density={tableDensity}
                                          />
                                        ))
                                      )}
                                    </tbody>
                                  </table>
                                </div>
                                {/* Footer — 빈 공간을 채우는 메타 정보 */}
                                <div className="px-5 py-3 border-t border-[#3a3633] flex justify-between items-center text-[0.625rem] font-mono text-[#9ca3af]">
                                  <span>
                                    총{' '}
                                    {tableView === 'cannibalization'
                                      ? sortedCannRows.length
                                      : sortedNeighborhoodRows.length}
                                    건 ·{' '}
                                    {tableView === 'cannibalization'
                                      ? '가맹점 간섭도 분석'
                                      : '행정동 비교 분석'}
                                  </span>
                                  <span className="opacity-70">UPDATED {reportFullDate}</span>
                                </div>
                              </div>
                            </div>

                            {/* Right Column */}
                            <div className="lg:flex-[1] flex flex-col gap-4">
                              {/* Radar Chart */}
                              <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-xl flex flex-col items-center justify-center">
                                <div className="w-full text-left mb-2">
                                  <h2 className="text-sm font-bold text-white">
                                    상권 종합 지표 분석 (7 Core Metrics)
                                  </h2>
                                  <p className="text-[0.6875rem] text-indigo-400">
                                    에이전트 노드 분석 결과 통합 데이터
                                  </p>
                                </div>
                                <div className="relative w-[180px] h-[180px] my-2">
                                  {!hasMarketReport && (
                                    <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg border border-dashed border-[#3a3633] bg-[#1e1b18]/60 backdrop-blur-[2px]">
                                      <div className="text-center px-3">
                                        <div className="mx-auto mb-1 h-5 w-5 animate-pulse rounded-full bg-[#3a3633]" />
                                        <div className="text-[0.6875rem] font-semibold text-[#e2e8f0]">
                                          구현 예정
                                        </div>
                                        <div className="mt-0.5 text-[0.5625rem] text-[#9ca3af]">
                                          market_report 대기
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                  <svg
                                    viewBox="0 0 200 200"
                                    className="w-full h-full overflow-visible"
                                  >
                                    <defs>
                                      <clipPath id="radarReveal">
                                        <motion.circle
                                          cx={100}
                                          cy={100}
                                          initial={{ r: 0 }}
                                          animate={{ r: 70 }}
                                          transition={{ duration: 1.4, ease: 'linear' }}
                                        />
                                      </clipPath>
                                    </defs>
                                    {/* Grid + axis (항상 표시) */}
                                    <polygon
                                      points="100,40 147,63 158,113 126,154 74,154 42,113 53,63"
                                      fill="#1e1b18"
                                      stroke="#3a3633"
                                      strokeWidth="1"
                                    />
                                    <polygon
                                      points="100,70 123.5,81.5 129,106.5 113,127 87,127 71,106.5 76.5,81.5"
                                      fill="none"
                                      stroke="#3a3633"
                                      strokeWidth="1"
                                      strokeDasharray="2 2"
                                    />
                                    <line x1="100" y1="100" x2="100" y2="40" stroke="#3a3633" />
                                    <line x1="100" y1="100" x2="147" y2="63" stroke="#3a3633" />
                                    <line x1="100" y1="100" x2="158" y2="113" stroke="#3a3633" />
                                    <line x1="100" y1="100" x2="126" y2="154" stroke="#3a3633" />
                                    <line x1="100" y1="100" x2="74" y2="154" stroke="#3a3633" />
                                    <line x1="100" y1="100" x2="42" y2="113" stroke="#3a3633" />
                                    <line x1="100" y1="100" x2="53" y2="63" stroke="#3a3633" />
                                    {/* Data polygon + dots — market_report 기반 동적 계산 */}
                                    <g clipPath="url(#radarReveal)">
                                      <polygon
                                        points={radarPointsStr}
                                        fill="rgba(99,102,241,0.4)"
                                        stroke="#818cf8"
                                        strokeWidth="2"
                                        className="drop-shadow-[0_0_8px_rgba(99,102,241,0.6)]"
                                      />
                                      {radarVertices.map((v, i) => (
                                        <circle key={i} cx={v.x} cy={v.y} r={3} fill="#fff" />
                                      ))}
                                    </g>
                                    <text
                                      onClick={() => setActiveDrawer('attractiveness')}
                                      className="cursor-pointer hover:fill-[#818cf8] transition-colors"
                                      x="100"
                                      y="32"
                                      fill="#e5e5e5"
                                      fontSize="10"
                                      fontWeight="bold"
                                      textAnchor="middle"
                                    >
                                      <title>유동인구: 82/100 (마포구 상위 12%)</title>유동인구
                                    </text>
                                    <text
                                      onClick={() => setActiveDrawer('attractiveness')}
                                      className="cursor-pointer hover:fill-[#818cf8] transition-colors"
                                      x="157"
                                      y="60"
                                      fill="#a3a3a3"
                                      fontSize="10"
                                      textAnchor="start"
                                    >
                                      <title>매출: 74/100 (월 3,240만 추정)</title>매출
                                    </text>
                                    <text
                                      onClick={() => setActiveDrawer('attractiveness')}
                                      className="cursor-pointer hover:fill-[#818cf8] transition-colors"
                                      x="168"
                                      y="117"
                                      fill="#a3a3a3"
                                      fontSize="10"
                                      textAnchor="start"
                                    >
                                      <title>성장성: 56/100 (전년 대비 +3.2%)</title>성장성
                                    </text>
                                    <text
                                      onClick={() => setActiveDrawer('attractiveness')}
                                      className="cursor-pointer hover:fill-[#818cf8] transition-colors"
                                      x="133"
                                      y="166"
                                      fill="#a3a3a3"
                                      fontSize="10"
                                      textAnchor="middle"
                                    >
                                      <title>폐업률</title>폐업률
                                    </text>
                                    <text
                                      onClick={() => setActiveDrawer('attractiveness')}
                                      className="cursor-pointer hover:fill-[#818cf8] transition-colors"
                                      x="67"
                                      y="166"
                                      fill="#a3a3a3"
                                      fontSize="10"
                                      textAnchor="middle"
                                    >
                                      <title>임대료: 45/100 (평당 25만원)</title>임대료
                                    </text>
                                    <text
                                      onClick={() => setActiveDrawer('attractiveness')}
                                      className="cursor-pointer hover:fill-[#818cf8] transition-colors"
                                      x="32"
                                      y="117"
                                      fill="#a3a3a3"
                                      fontSize="10"
                                      textAnchor="end"
                                    >
                                      <title>경쟁강도: 68/100 (반경 500m 내 45개)</title>경쟁강도
                                    </text>
                                    <text
                                      onClick={() => setActiveDrawer('attractiveness')}
                                      className="cursor-pointer hover:fill-[#818cf8] transition-colors"
                                      x="43"
                                      y="60"
                                      fill="#a3a3a3"
                                      fontSize="10"
                                      textAnchor="end"
                                    >
                                      <title>접근성: 78/100 (지하철 도보 5분)</title>접근성
                                    </text>
                                  </svg>
                                </div>
                              </div>

                              {/* 폐업 위험도 카드 (B2 수지니) */}
                              {simResult?.closureRisk ? (
                                (() => {
                                  const cr = simResult.closureRisk;
                                  const pct = Math.round((cr.risk_score ?? 0) * 100);
                                  const levelConfig = {
                                    safe: {
                                      badge:
                                        'bg-emerald-400/20 text-emerald-300 border-emerald-400/40',
                                      bar: 'bg-emerald-400',
                                      label: '안전',
                                    },
                                    caution: {
                                      badge: 'bg-amber-400/20 text-amber-300 border-amber-400/40',
                                      bar: 'bg-amber-400',
                                      label: '주의',
                                    },
                                    danger: {
                                      badge: 'bg-rose-400/20 text-rose-300 border-rose-400/40',
                                      bar: 'bg-rose-400',
                                      label: '위험',
                                    },
                                  }[cr.risk_level] ?? {
                                    badge: 'bg-slate-500/20 text-slate-300 border-slate-500/40',
                                    bar: 'bg-slate-500',
                                    label: '—',
                                  };
                                  // 2026-04-27: closure_risk가 lgbm/tcn 두 모델 결과를 별도 노출
                                  // top_signals → top_signals_lgbm + top_signals_tcn (TCN 실패 시 빈 배열)
                                  const topLgbm = (cr.top_signals_lgbm ?? []).slice(0, 3);
                                  const topTcn = (cr.top_signals_tcn ?? []).slice(0, 3);
                                  const maxAbs = Math.max(
                                    ...topLgbm.map((s) => Math.abs(s.contribution)),
                                    ...topTcn.map((s) => Math.abs(s.contribution)),
                                    0.0001,
                                  );
                                  return (
                                    <div
                                      className={`bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-xl flex flex-col gap-3 ${
                                        cr.is_mock ? 'opacity-60' : ''
                                      }`}
                                    >
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                          <h2 className="text-sm font-bold text-white">
                                            폐업 위험도
                                          </h2>
                                          {cr.is_mock && (
                                            <span className="text-[0.5rem] font-mono px-1.5 py-0.5 rounded border border-slate-500/40 bg-slate-500/20 text-slate-300 uppercase tracking-wider">
                                              MOCK
                                            </span>
                                          )}
                                        </div>
                                        <span
                                          className={`inline-flex items-center gap-1 text-[0.5625rem] font-mono uppercase tracking-widest px-2 py-0.5 rounded-full border ${levelConfig.badge}`}
                                        >
                                          <span
                                            className={`w-1.5 h-1.5 rounded-full ${levelConfig.bar}`}
                                          />
                                          {levelConfig.label}
                                        </span>
                                      </div>
                                      <div>
                                        <div className="flex items-baseline justify-between mb-1.5">
                                          <span className="text-[0.625rem] text-[#9ca3af]">
                                            위험 점수
                                          </span>
                                          <span className="text-lg font-bold text-white font-mono tabular-nums">
                                            {pct}
                                            <span className="text-[0.6875rem] text-[#9ca3af] ml-0.5">
                                              /100
                                            </span>
                                          </span>
                                        </div>
                                        <div className="w-full h-2 bg-[#1e1b18] rounded-full overflow-hidden border border-[#3a3633]">
                                          <div
                                            className={`h-full ${levelConfig.bar} transition-all duration-700`}
                                            style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                                          />
                                        </div>
                                      </div>
                                      {(topLgbm.length > 0 || topTcn.length > 0) && (
                                        <div className="flex flex-col gap-3 pt-2 border-t border-[#3a3633]">
                                          {topLgbm.length > 0 && (
                                            <div className="flex flex-col gap-1.5">
                                              <div className="text-[0.625rem] text-[#9ca3af] mb-0.5 flex items-center gap-1.5">
                                                <span className="w-1 h-1 rounded-full bg-indigo-400" />
                                                LightGBM · 과거 패턴 기여 Top {topLgbm.length}
                                              </div>
                                              {topLgbm.map((s, i) => {
                                                const w = Math.round(
                                                  (Math.abs(s.contribution) / maxAbs) * 100,
                                                );
                                                const positive = s.contribution >= 0;
                                                return (
                                                  <div
                                                    key={`lgbm-${i}`}
                                                    className="flex items-center gap-2 text-[0.625rem]"
                                                  >
                                                    <span className="w-28 shrink-0 text-[#e2e8f0] truncate">
                                                      {s.feature}
                                                    </span>
                                                    <div className="flex-1 h-1.5 bg-[#1e1b18] rounded-full overflow-hidden border border-[#3a3633]">
                                                      <div
                                                        className={`h-full ${positive ? 'bg-rose-400' : 'bg-emerald-400'}`}
                                                        style={{ width: `${w}%` }}
                                                      />
                                                    </div>
                                                    <span
                                                      className={`w-12 text-right font-mono tabular-nums ${positive ? 'text-rose-300' : 'text-emerald-300'}`}
                                                    >
                                                      {positive ? '+' : ''}
                                                      {s.contribution.toFixed(2)}
                                                    </span>
                                                  </div>
                                                );
                                              })}
                                            </div>
                                          )}
                                          {topTcn.length > 0 && (
                                            <div className="flex flex-col gap-1.5 pt-2 border-t border-[#3a3633]/50">
                                              <div className="text-[0.625rem] text-[#9ca3af] mb-0.5 flex items-center gap-1.5">
                                                <span className="w-1 h-1 rounded-full bg-cyan-400" />
                                                TCN · 시계열 흐름 기여 Top {topTcn.length}
                                              </div>
                                              {topTcn.map((s, i) => {
                                                const w = Math.round(
                                                  (Math.abs(s.contribution) / maxAbs) * 100,
                                                );
                                                const positive = s.contribution >= 0;
                                                return (
                                                  <div
                                                    key={`tcn-${i}`}
                                                    className="flex items-center gap-2 text-[0.625rem]"
                                                  >
                                                    <span className="w-28 shrink-0 text-[#e2e8f0] truncate">
                                                      {s.feature}
                                                    </span>
                                                    <div className="flex-1 h-1.5 bg-[#1e1b18] rounded-full overflow-hidden border border-[#3a3633]">
                                                      <div
                                                        className={`h-full ${positive ? 'bg-cyan-400' : 'bg-emerald-400'}`}
                                                        style={{ width: `${w}%` }}
                                                      />
                                                    </div>
                                                    <span
                                                      className={`w-12 text-right font-mono tabular-nums ${positive ? 'text-cyan-300' : 'text-emerald-300'}`}
                                                    >
                                                      {positive ? '+' : ''}
                                                      {s.contribution.toFixed(2)}
                                                    </span>
                                                  </div>
                                                );
                                              })}
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })()
                              ) : (
                                <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-xl flex flex-col items-center justify-center min-h-[120px]">
                                  <span className="text-xs text-[#9ca3af]">
                                    폐업 위험도 데이터 없음
                                  </span>
                                </div>
                              )}

                              {/* [C1 신규] 핵심 소비층 분석 카드 (demographic_depth) */}
                              {(() => {
                                const d = simResult?.demographicReport;
                                if (!d) return null;
                                const genderKo = (g: string) =>
                                  (
                                    ({
                                      male: '남성',
                                      female: '여성',
                                      mixed: '혼합',
                                    }) as Record<string, string>
                                  )[g] ?? g;
                                const incomeLevelKo = (l: string) =>
                                  (
                                    ({
                                      high: '상',
                                      mid: '중',
                                      low: '하',
                                      unknown: 'N/A',
                                    }) as Record<string, string>
                                  )[l] ?? l;
                                const core = d.core_demographic;
                                const top3 = d.top_3_age_groups ?? [];
                                const peakHours = d.peak_consumption_hours ?? [];
                                return (
                                  <div className="rounded-xl border border-[#3a3633] bg-[#2c2825] p-5 shadow-xl">
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-2">
                                        <Users className="h-4 w-4 text-[#818cf8]" />
                                        <h3 className="text-sm font-semibold uppercase tracking-widest text-[#9ca3af]">
                                          핵심 소비층 분석
                                        </h3>
                                      </div>
                                      {d.elderly_ratio != null && (
                                        <span className="text-xs font-mono tabular-nums text-[#9ca3af]">
                                          고령: {d.elderly_ratio.toFixed(1)}%
                                        </span>
                                      )}
                                    </div>

                                    {core && (core.age || core.gender) && (
                                      <div className="mt-3 rounded-lg bg-[#818cf8]/10 p-3 ring-1 ring-[#818cf8]/30">
                                        <div className="text-xs uppercase tracking-wider text-[#a5b4fc]">
                                          주 소비층
                                        </div>
                                        <div className="mt-1 flex items-baseline gap-2 flex-wrap">
                                          <span className="text-2xl font-bold text-[#e2e8f0]">
                                            {core.age ? `${core.age}대` : ''}{' '}
                                            {genderKo(core.gender ?? '')}
                                          </span>
                                          {typeof core.share === 'number' && (
                                            <span className="text-sm text-[#9ca3af]">
                                              {(core.share * 100).toFixed(1)}% 매출 기여
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                    )}

                                    {top3.length > 0 && (
                                      <div className="mt-4 space-y-2">
                                        <div className="text-xs font-semibold uppercase tracking-wider text-[#9ca3af]">
                                          연령대 TOP 3
                                        </div>
                                        {top3.map((a) => (
                                          <div
                                            key={a.age_group}
                                            className="flex items-center gap-2 text-xs"
                                          >
                                            <span className="w-12 text-[#e2e8f0]">
                                              {a.age_group}대
                                            </span>
                                            <div className="flex-1 rounded-full bg-[#1e1b18]/50">
                                              <div
                                                className="h-2 rounded-full bg-[#818cf8]"
                                                style={{
                                                  width: `${Math.min(100, Math.max(0, a.share * 100))}%`,
                                                }}
                                              />
                                            </div>
                                            <span className="w-12 text-right font-mono tabular-nums text-[#9ca3af]">
                                              {(a.share * 100).toFixed(1)}%
                                            </span>
                                          </div>
                                        ))}
                                      </div>
                                    )}

                                    <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                                      <div className="rounded-lg bg-[#1e1b18]/50 p-2">
                                        <div className="text-[#9ca3af]">피크</div>
                                        <div className="mt-1 font-semibold text-[#e2e8f0]">
                                          {peakHours.slice(0, 2).join(' · ') || 'N/A'}
                                        </div>
                                      </div>
                                      <div className="rounded-lg bg-[#1e1b18]/50 p-2">
                                        <div className="text-[#9ca3af]">평/주말</div>
                                        <div className="mt-1 font-semibold font-mono tabular-nums text-[#e2e8f0]">
                                          {typeof d.weekday_weekend_ratio === 'number'
                                            ? d.weekday_weekend_ratio.toFixed(2)
                                            : 'N/A'}
                                        </div>
                                      </div>
                                      <div className="rounded-lg bg-[#1e1b18]/50 p-2">
                                        <div className="text-[#9ca3af]">소득</div>
                                        <div className="mt-1 font-semibold text-[#e2e8f0]">
                                          {incomeLevelKo(d.area_income_level ?? 'unknown')}
                                        </div>
                                      </div>
                                    </div>

                                    {d.resident_visitor_ratio != null && (
                                      <div className="mt-3 flex items-center gap-1.5 text-xs text-[#9ca3af]">
                                        <MapPin className="h-3 w-3 text-slate-400" />
                                        <span>
                                          외부 방문객 비율:{' '}
                                          {(d.resident_visitor_ratio * 100).toFixed(1)}%
                                        </span>
                                      </div>
                                    )}

                                    {d.brand_target_match_score != null && (
                                      <div className="mt-3 rounded-lg bg-amber-500/10 p-3 ring-1 ring-amber-500/30">
                                        <div className="flex items-baseline gap-2 flex-wrap">
                                          <span className="text-xs uppercase tracking-wider text-amber-300">
                                            브랜드 타겟 매칭
                                          </span>
                                          <span className="text-lg font-bold font-mono tabular-nums text-amber-200">
                                            {d.brand_target_match_score.toFixed(0)}/100
                                          </span>
                                        </div>
                                        {d.match_rationale && (
                                          <p className="mt-1 text-xs text-[#e2e8f0]">
                                            {d.match_rationale}
                                          </p>
                                        )}
                                      </div>
                                    )}

                                    {d.narrative && (
                                      <p className="mt-4 text-xs leading-relaxed text-[#9ca3af]">
                                        {d.narrative}
                                      </p>
                                    )}
                                  </div>
                                );
                              })()}

                              {/* Insights */}
                              <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-xl flex flex-col flex-1">
                                {/* Header with dynamic counter */}
                                <div className="flex items-center justify-between mb-3">
                                  <h2 className="text-sm font-bold text-white">
                                    SPOTTER AI 인사이트
                                  </h2>
                                  <span className="font-mono text-[0.5625rem] uppercase tracking-widest text-[#818cf8] bg-[#818cf8]/10 border border-[#818cf8]/30 px-2 py-0.5 rounded-full">
                                    3 INSIGHTS
                                  </span>
                                </div>
                                <div className="space-y-3">
                                  {/* 고정 카드 1: 저녁 시간대 매출 */}
                                  <InsightCard
                                    severity="advisory"
                                    onClick={() => setActiveDrawer('insight_traffic')}
                                    icon={<TrendingUp className="w-4 h-4 text-indigo-400" />}
                                    title="저녁 시간대 매출 집중형"
                                    desc="18시 이후 유동인구가 급증. 야간 메뉴 강화를 권장합니다."
                                  />
                                  {/* 법률 리스크 통합 카드: safe 제외하고 위험/주의 항목만 서브 표시 */}
                                  {(() => {
                                    const TYPE_LABEL: Record<string, string> = {
                                      franchise_law: '가맹사업법',
                                      commercial_lease_law: '상가임대차보호법',
                                      zoning_regulation: '용도지역 규제',
                                      food_hygiene: '식품위생법',
                                      safety_regulation: '안전규정',
                                      building_law: '건축법',
                                      fire_safety_law: '소방안전법',
                                      labor_law: '근로기준법',
                                      vat_law: '부가가치세법',
                                      privacy_law: '개인정보보호법',
                                      accessibility_law: '장애인편의법',
                                      sewage_law: '하수도법',
                                      fair_trade_law: '공정거래법',
                                      ftc_franchise: '공정위 정보공개서',
                                    };
                                    const severityOf = (
                                      level: string,
                                    ): 'critical' | 'advisory' | 'safe' => {
                                      const r = (level || '').toLowerCase();
                                      if (r === 'danger' || r === 'high') return 'critical';
                                      if (r === 'caution' || r === 'medium') return 'advisory';
                                      return 'safe';
                                    };

                                    // safe 항목 제외 — 위험·주의만 표시
                                    const dangerRisks = (simResult?.legalRisks ?? []).filter(
                                      (r) => severityOf(r.risk_level) !== 'safe',
                                    );

                                    if (dangerRisks.length === 0) {
                                      // 위험 항목 없으면 "안전" 긍정 메시지 (mock 제거됨)
                                      return (
                                        <InsightCard
                                          severity="advisory"
                                          onClick={() => setActiveDrawer('insight_legal')}
                                          icon={<Scale className="w-4 h-4 text-emerald-500" />}
                                          title="법률 리스크 — 안전"
                                          desc={
                                            simResult?.recommendation ||
                                            '해당 권역에서 감지된 고위험 법률 이슈가 없습니다. 세부 14개 법령 체크리스트는 drawer에서 확인하세요.'
                                          }
                                        />
                                      );
                                    }

                                    const topSev = dangerRisks.some(
                                      (r) => severityOf(r.risk_level) === 'critical',
                                    )
                                      ? 'critical'
                                      : 'advisory';

                                    const openLegalDrawer = (type: string | null) => {
                                      // 개별 법률이 지정되지 않으면 가장 위험한 첫 번째 항목을 기본 선택
                                      const fallbackType = dangerRisks[0]?.type ?? null;
                                      setSelectedLegalType(type ?? fallbackType);
                                      setActiveDrawer('insight_legal');
                                    };

                                    return (
                                      <div
                                        onClick={() => openLegalDrawer(null)}
                                        className="flex flex-col gap-2 p-3 rounded-lg bg-[#1e1b18] border border-[#3a3633] cursor-pointer hover:border-[#818cf8] hover:bg-[#818cf8]/[0.05] transition-all group"
                                      >
                                        <div className="flex items-center gap-3">
                                          <Scale
                                            className={`w-4 h-4 shrink-0 ${topSev === 'critical' ? 'text-rose-500' : 'text-amber-400'}`}
                                          />
                                          <div className="flex-1 flex items-center justify-between gap-2">
                                            <h4 className="text-[#e2e8f0] font-bold text-xs">
                                              법률 리스크 종합
                                            </h4>
                                            <span className="inline-flex items-center gap-1 shrink-0">
                                              <span
                                                className={`w-1.5 h-1.5 rounded-full ${topSev === 'critical' ? 'bg-rose-500' : 'bg-amber-400'}`}
                                              />
                                              <span className="text-[0.5rem] font-mono uppercase tracking-wider text-[#9ca3af]">
                                                {topSev === 'critical' ? '필수이행' : '확인필요'}
                                              </span>
                                            </span>
                                          </div>
                                        </div>
                                        <div className="flex flex-col gap-2 border-t border-[#3a3633] pt-2">
                                          {dangerRisks.map((risk, i) => {
                                            const sev = severityOf(risk.risk_level);
                                            const isCritical = sev === 'critical';
                                            return (
                                              <div
                                                key={i}
                                                onClick={(e) => {
                                                  e.stopPropagation();
                                                  openLegalDrawer(risk.type);
                                                }}
                                                className={`flex gap-2.5 pl-2.5 border-l-2 cursor-pointer rounded-r hover:bg-[#818cf8]/[0.08] transition-colors ${isCritical ? 'border-rose-500' : 'border-amber-400'}`}
                                              >
                                                <div className="flex flex-col gap-0.5 flex-1 min-w-0 py-0.5">
                                                  <div className="flex items-center gap-1.5">
                                                    <span className="text-[#e2e8f0] text-[0.6875rem] font-semibold">
                                                      {TYPE_LABEL[risk.type] || risk.type}
                                                    </span>
                                                    <span
                                                      className={`text-[0.5rem] font-mono px-1 py-0.5 rounded ${isCritical ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-400/20 text-amber-400'}`}
                                                    >
                                                      {isCritical ? '필수이행' : '확인필요'}
                                                    </span>
                                                  </div>
                                                  {risk.detail && (
                                                    <p className="text-[#9ca3af] text-[0.625rem] leading-relaxed">
                                                      {risk.detail}
                                                    </p>
                                                  )}
                                                </div>
                                              </div>
                                            );
                                          })}
                                        </div>
                                      </div>
                                    );
                                  })()}
                                  {/* 동적 카드 3: 타겟 고객층 */}
                                  <InsightCard
                                    severity="opportunity"
                                    onClick={() => setActiveDrawer('insight_target')}
                                    icon={<Users className="w-4 h-4 text-indigo-400" />}
                                    title={
                                      simResult?.analysis_metrics?.main_target_age
                                        ? `${simResult.analysis_metrics.main_target_age} 타겟 권역`
                                        : '주요 타겟 고객층'
                                    }
                                    desc={
                                      simResult?.analysis_metrics?.peak_time
                                        ? `피크 타임: ${simResult.analysis_metrics.peak_time} · 타겟층 집중 마케팅 전략 권장`
                                        : '유동인구 분석 기반 타겟 고객층 전략을 확인하세요.'
                                    }
                                  />
                                </div>

                                {/* --- AI Workflow & Report Buttons --- */}
                                <div className="flex flex-col gap-2 mt-3 shrink-0">
                                  <button
                                    onClick={() => setIsWorkflowOpen(true)}
                                    className="w-full py-2.5 bg-gradient-to-r from-[#818cf8]/20 to-transparent hover:from-[#818cf8]/40 border border-[#818cf8]/30 rounded-md text-xs font-bold text-[#e2e8f0] transition-all flex items-center justify-between px-4 group shadow-[0_0_15px_rgba(129,140,248,0.1)] hover:shadow-[0_0_20px_rgba(129,140,248,0.25)]"
                                  >
                                    <div className="flex items-center gap-2">
                                      <Network className="w-4 h-4 text-[#818cf8] group-hover:scale-110 transition-transform" />
                                      <span>AI 에이전트 워크플로우 보기</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                      <span className="text-[0.625rem] font-mono text-[#818cf8]">
                                        LIVE
                                      </span>
                                    </div>
                                  </button>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : dashboardMode === 'map' ? (
                        /* 🗺️ AI 에이전트 맵 뷰 — KPI 없이 화면 꽉 채움 */
                        <div className="flex-1 w-full h-full min-h-[700px] mt-4 relative animate-in zoom-in-95 fade-in duration-500 flex flex-col pb-6">
                          <div className="flex-1 bg-[#1e1b18] border border-[#3a3633] rounded-2xl overflow-hidden shadow-2xl flex flex-col relative">
                            {/* 맵 헤더 */}
                            <div className="h-14 bg-[#171717]/90 backdrop-blur-md border-b border-[#3a3633] flex justify-between items-center px-6 shrink-0 z-50">
                              <h3 className="text-sm font-black text-white flex items-center gap-3">
                                <span className="w-2.5 h-2.5 rounded-full bg-[#818cf8] animate-pulse shadow-[0_0_10px_rgba(129,140,248,0.8)]" />
                                Multi-Agent Geospatial Recommendations
                              </h3>
                              <p className="text-xs text-[#9ca3af] font-mono tracking-widest">
                                AI AGENT TARGETING SYSTEM
                              </p>
                            </div>
                            <div className="flex-1 relative">
                              <AgentMapVisualizer
                                height="100%"
                                locations={
                                  simResult?.vacancySpots && simResult.vacancySpots.length > 0
                                    ? simResult.vacancySpots.map((s) => ({
                                        id: `vacancy_${s.id}`,
                                        name: s.dong_name,
                                        lat: s.lat,
                                        lng: s.lon,
                                        type: 'vacancy' as const,
                                        listingCount: s.listing_count,
                                      }))
                                    : undefined
                                }
                                competitors={(simResult?.allCompetitorLocations?.length
                                  ? simResult.allCompetitorLocations
                                  : (simResult?.competitorIntel?.competition_500m?.samples ?? [])
                                )
                                  .filter((s: any) => s.lat && (s.lng ?? s.lon))
                                  .map((s: any) => ({
                                    id: s.id ?? `comp_${s.place_name}_${s.lat}`,
                                    name: s.place_name || s.brand_name || '경쟁업체',
                                    lat: s.lat,
                                    lng: s.lng ?? s.lon,
                                    distance_m: s.distance_m,
                                    is_franchise: s.is_franchise ?? false,
                                    category: s.category,
                                  }))}
                                onSpotClick={async (loc) => {
                                  // 공실 번호 마커 클릭 → ABM 탭 전환 + 해당 스팟만 5000 에이전트 시뮬
                                  if (!simResult || abmLoading) return;
                                  setDashboardMode('abm');
                                  await startAbm(
                                    {
                                      target_district: loc.name,
                                      business_type: businessType,
                                      brand_name:
                                        brand?.brand_name || user?.company_name || '신규 매장',
                                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                      langgraph_result: (simResult as any)._raw ?? simResult,
                                      n_agents: 5000,
                                      days: 1,
                                      spot_lat: loc.lat,
                                      spot_lon: loc.lng,
                                      scenario: {
                                        weather_override: null,
                                        date_override: null,
                                        weekend_force: false,
                                        rent_shock_pct: 0.0,
                                      },
                                      enable_llm_thought: true,
                                      enable_llm_decisions: true,
                                      store_area: storeArea,
                                    },
                                    { lat: loc.lat, lon: loc.lng, label: loc.name },
                                  );
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      ) : (
                        /* 🤖 ABM 페르소나 행동 시뮬 뷰 */
                        <AbmPersonaMap
                          abmResult={abmResult}
                          abmLoading={abmLoading}
                          abmError={abmError}
                          targetDistrict={selectedDongs[0] || '서교동'}
                          vacancySpots={simResult?.vacancySpots}
                          focusSpot={abmFocusSpot}
                          competitors={
                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                            ((simResult as any)?.allCompetitorLocations?.length
                              ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                (simResult as any).allCompetitorLocations
                              : // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                ((simResult as any)?.competitorIntel?.competition_500m?.samples ??
                                [])) as any
                          }
                          onClearResult={() => {
                            dismissAbmResult();
                            setAbmFocusSpot(null);
                            setDashboardMode('map');
                          }}
                          onSpotClick={async (spot) => {
                            if (!simResult || abmLoading) return;
                            await startAbm(
                              {
                                // 클릭한 스팟의 동을 target 으로 강제 (선택된 동과 다를 수 있음)
                                target_district: spot.dong_name,
                                business_type: businessType,
                                brand_name: brand?.brand_name || user?.company_name || '신규 매장',
                                langgraph_result: (simResult as any)._raw ?? simResult,
                                n_agents: 5000,
                                days: 1,
                                spot_lat: spot.lat,
                                spot_lon: spot.lon,
                                scenario: {
                                  weather_override: null,
                                  date_override: null,
                                  weekend_force: false,
                                  rent_shock_pct: 0.0,
                                },
                                enable_llm_thought: true,
                                enable_llm_decisions: true,
                                store_area: storeArea,
                              },
                              { lat: spot.lat, lon: spot.lon, label: spot.dong_name },
                            );
                          }}
                          onRunSimulation={async (scenario) => {
                            if (!simResult) return;
                            await startAbm(
                              {
                                target_district: selectedDongs[0] || '서교동',
                                business_type: businessType,
                                brand_name: brand?.brand_name || user?.company_name || '신규 매장',
                                langgraph_result: (simResult as any)._raw ?? simResult,
                                n_agents: 5000,
                                days: 1,
                                scenario: {
                                  weather_override: scenario.weather_override,
                                  date_override: scenario.date_override,
                                  weekend_force: scenario.weekend_force,
                                  rent_shock_pct: scenario.rent_shock_pct,
                                },
                                enable_llm_thought: true,
                                enable_llm_decisions: true,
                                store_area: storeArea,
                              },
                              abmFocusSpot,
                            );
                          }}
                        />
                      )}
                    </>
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
