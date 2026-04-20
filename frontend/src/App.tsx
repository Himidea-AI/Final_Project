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
 *   - CSS Variables (index.css) + Tailwind darkMode:"class"
 *   - isDark state → <div className="dark"> 토글
 *   - SkyThemeToggle 컴포넌트로 Light/Dark 전환
 *   - 시맨틱 클래스: bg-background, text-foreground, bg-card, text-primary 등
 *
 * [백엔드 연동]
 *   - api/client.ts의 USE_MOCK = true → Mock 데이터 반환 (프론트 독립 동작)
 *   - USE_MOCK = false로 변경 시 → FastAPI /api/simulate, /api/analyze 호출
 *   - SimulatorDashboard.runSim()에서 runSimulation() 호출 (v12.4부터 /simulate 단일 호출)
 *
 * [팀원 참고]
 *   - A1/B1: api/client.ts의 Mock 응답 형태 = 실제 API 응답과 동일해야 함
 *   - B2: SimResult.chartData 7개 항목 = 에이전트 노드별 점수
 *   - C2: Docker 배포 시 nginx.conf의 /api 프록시가 백엔드를 가리켜야 함
 */

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  forwardRef,
  createContext,
  useContext,
} from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import JoinUsPage from './pages/JoinUs/JoinUsPage';
import HQCommandCenter from './pages/HQCommandCenter';
import LoginPage from './pages/LoginPage';
import { AuthProvider, useAuth } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import AIVerdictBanner from './components/AIVerdictBanner';
import { ToastProvider, useToast } from './components/Toast';
import type {
  QuarterlyProjection,
  ShapResult,
  ClosureRisk,
  TrendForecast,
  DemographicReport,
} from './types';
import { QuarterlyProjectionChart } from './components/SimulationResult/QuarterlyProjectionChart';
import { ShapChart } from './components/SimulationResult/ShapChart';
// import AnalysisDashboard from "./pages/AnalysisDashboard"; // 팀원 파일 — JSX 에러 있어 비활성
import React from 'react';
import { SimulationFloatingWidget } from './components/simulation/SimulationFloatingWidget';
import { BeforeUnloadGuard } from './components/simulation/BeforeUnloadGuard';
import { ToastHost } from './components/simulation/ToastHost';
import { useCompletionToast } from './hooks/useCompletionToast';
import { useSimulationStore } from './stores/simulationStore';

interface SimResult {
  score: number;
  revenue: number;
  riskLevel: string;
  recommendation: string;
  chartData: { label: string; value: number }[];
  // 분기별 매출 예측 데이터 (TCN 모델 출력) — B2 수지니 연동
  quarterlyProjection: QuarterlyProjection[];
  // TCN SHAP 피처 기여도 분석 결과 (없으면 null) — B2 수지니 연동
  shapResult: ShapResult | null;
  // [C1 응답 필드 반영] v12.6 — 백엔드가 주는데 UI가 안 쓰던 5 영역
  marketReport?: {
    floating_population: number;
    rent_index: number;
    competition_intensity: number;
    estimated_revenue: number;
    survival_rate: number;
    closure_rate: number | null;
    growth_potential: number;
    accessibility: number;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  districtRankings?: { district: string; score: number; [k: string]: any }[];
  winnerDistrict?: string;
  topCandidates?: string[];
  legalRisks?: {
    type: string;
    risk_level: string;
    detail: string;
    recommendation?: string;
    articles?: { article_ref: string; content: string }[];
  }[];
  overallLegalRisk?: string;
  vacancyApplied?: boolean;
  vacancySpots?: {
    id: number;
    lat: number;
    lon: number;
    dong_name: string;
    listing_count: number;
  }[];
  analysis_metrics?: {
    main_target_age?: string;
    peak_time?: string;
    [k: string]: unknown;
  };
  // [B2 시나리오] 낙관/기본/비관 분기 매출 시나리오 — C1 UI 연동용
  scenarios?: {
    optimistic: { quarter: number; revenue: number }[];
    base: { quarter: number; revenue: number }[];
    pessimistic: { quarter: number; revenue: number }[];
  } | null;
  // [B2 수지니] 폐업 위험도
  closureRisk?: ClosureRisk | null;
  // [PR #72] 경쟁 매장 인텔리전스 (500m 반경)
  competitorIntel?: {
    competition_500m?: {
      total_competitors: number;
      franchise_count?: number;
      independent_count?: number;
      saturation_level: string;
      saturation_score?: number;
      brand_distribution?: Record<string, number>;
      samples: Array<{
        place_name: string;
        distance_m: number;
        category?: string;
      }>;
    };
    cannibalization?: { estimated_revenue_impact_pct: number };
    market_entry_signal?: 'green' | 'yellow' | 'red';
    differentiation_position?: string;
    key_opportunities?: string[];
    key_risks?: string[];
    recommended_actions?: string[];
    narrative?: string;
  } | null;
  // [PR #71] 트렌드 전망 (trend_forecaster 에이전트)
  trendForecast?: TrendForecast | null;
  // [PR #75] 인구통계 심층 분석 (demographic_depth 에이전트)
  demographicReport?: DemographicReport | null;
}

import {
  ChevronRight,
  ChevronLeft,
  Sliders,
  Activity,
  MapPin,
  ExternalLink,
  Mail,
  Phone,
  GitFork,
  Users,
  TrendingUp,
  Play,
  ChevronDown,
  User,
  Bell,
  Settings,
  X,
  ChevronsUpDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  Folder,
  LogOut,
  ShieldAlert,
  CheckCircle2,
  TrendingDown,
  Zap,
  Calendar,
  Download,
  FileText,
  Database,
  BarChart3,
  Crosshair,
  AlertTriangle,
  Scale,
  Store,
  Columns,
  Search,
  Rows3,
  AlignJustify,
  List,
  LayoutDashboard,
  Building2,
  ArrowRight,
  Terminal,
  Network,
  Circle,
  CircleDotDashed,
  BarChartBig,
  Map as MapIcon,
  LogIn,
} from 'lucide-react';

import AgentMapVisualizer from './components/AgentMapVisualizer';
import HybridSliderInput from './components/ui/HybridSliderInput';
import { useManagerList, formatRelativeTime, ManagerListProvider } from './hooks/useManagerList';
import {
  AreaChart,
  Area,
  XAxis,
  Tooltip as RechartsTooltipWrapper,
  ResponsiveContainer,
} from 'recharts';

/* ═══════════════════════════════════════════════════════
   DATA
   ═══════════════════════════════════════════════════════ */
import { LayoutGroup, motion, AnimatePresence } from 'framer-motion';

const DISTRICTS = [
  { name: '강남구', eng: 'GANGNAM', img: '/images/Gangnam-gu.svg' },
  { name: '강동구', eng: 'GANGDONG', img: '/images/Gangdong-gu.svg' },
  { name: '강북구', eng: 'GANGBUK', img: '/images/Gangbuk-gu.svg' },
  { name: '강서구', eng: 'GANGSEO', img: '/images/Gangseo-gu.svg' },
  { name: '관악구', eng: 'GWANAK', img: '/images/Gwanak-gu.svg' },
  { name: '광진구', eng: 'GWANGJIN', img: '/images/Gwangjin-gu.svg' },
  { name: '구로구', eng: 'GURO', img: '/images/Guro-gu.svg' },
  { name: '금천구', eng: 'GEUMCHEON', img: '/images/Geumcheon-gu.svg' },
  { name: '노원구', eng: 'NOWON', img: '/images/Nowon-gu.svg' },
  { name: '도봉구', eng: 'DOBONG', img: '/images/Dobong-gu.svg' },
  { name: '동대문구', eng: 'DONGDAEMUN', img: '/images/Dongdaemun-gu.svg' },
  { name: '동작구', eng: 'DONGJAK', img: '/images/Dongjak-gu.svg' },
  { name: '마포구', eng: 'MAPO', img: '/images/Mapo-gu.svg' },
  { name: '서대문구', eng: 'SEODAEMUN', img: '/images/Seodaemun-gu.svg' },
  { name: '서초구', eng: 'SEOCHO', img: '/images/Seocho-gu.svg' },
  { name: '성동구', eng: 'SEONGDONG', img: '/images/Seongdong-gu.svg' },
  { name: '성북구', eng: 'SEONGBUK', img: '/images/Seongbuk-gu.svg' },
  { name: '송파구', eng: 'SONGPA', img: '/images/Songpa-gu.svg' },
  { name: '양천구', eng: 'YANGCHEON', img: '/images/Yangcheon-gu.svg' },
  { name: '영등포구', eng: 'YEONGDEUNGPO', img: '/images/Yeongdeungpo-gu.svg' },
  { name: '용산구', eng: 'YONGSAN', img: '/images/Yongsan-gu.svg' },
  { name: '은평구', eng: 'EUNPYEONG', img: '/images/Eunpyeong-gu.svg' },
  { name: '종로구', eng: 'JONGNO', img: '/images/Jongno-gu.svg' },
  { name: '중구', eng: 'JUNG', img: '/images/Jung-gu.svg' },
  { name: '중랑구', eng: 'JUNGNANG', img: '/images/Jungnang-gu.svg' },
];

const MAPO_IDX = DISTRICTS.findIndex((d) => d.name === '마포구');

const MENU_ITEMS = ['ABOUT SPOTTER', 'SIMULATOR', 'CONTACT'];

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

const CHART_DATA = [
  { label: '유동인구', value: 82 },
  { label: '임대료', value: 45 },
  { label: '경쟁강도', value: 68 },
  { label: '매출추정', value: 74 },
  { label: '폐업률', value: 9 },
  { label: '성장성', value: 56 },
  { label: '접근성', value: 78 },
];

/* ═══════════════════════════════════════════════════════
   Smart Mock — 동/업종 이름 기반 해시로 동적 결과 생성
   발표 시 다른 동을 선택하면 다른 결과가 나오도록 함
   ═══════════════════════════════════════════════════════ */
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function generateSmartMock(dongName: string, businessType: string) {
  const seed = hashString(dongName + businessType);

  // 매출: 2500만 ~ 5500만 (만원 단위)
  const revenue = 2500 + (seed % 3001);
  // 매력도: 62 ~ 96
  const score = 62 + (seed % 35);
  // 리스크: seed 기반 분기
  const riskLevels = ['LOW', 'LOW', 'MEDIUM', 'LOW', 'HIGH'] as const;
  const riskLevel = riskLevels[seed % riskLevels.length];

  // 7대 지표: 각각 다른 seed offset으로 40~95 사이
  const metricSeeds = [0, 17, 31, 47, 61, 79, 89];
  const chartData = [
    '유동인구',
    '임대료',
    '경쟁강도',
    '매출추정',
    '폐업률',
    '성장성',
    '접근성',
  ].map((label, i) => ({
    label,
    value: 40 + ((seed + metricSeeds[i]) % 56),
  }));

  // AI 한 줄 평 (동 이름 포함)
  const verdicts = [
    `${dongName}은(는) ${businessType} 업종에 유리한 입지로, 유동인구 밀집도가 높은 상권입니다.`,
    `${dongName} 상권은 ${businessType} 창업 시 평균 이상의 매출이 예상되는 권역입니다.`,
    `${dongName}의 ${businessType} 시장은 경쟁이 치열하나, 타겟층 밀도가 높아 수익성이 기대됩니다.`,
    `${dongName}은(는) ${businessType} 업종의 성장 잠재력이 높은 지역으로 분석됩니다.`,
  ];
  const recommendation = verdicts[seed % verdicts.length];

  return { revenue, score, riskLevel, recommendation, chartData };
}

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

const PRICE_RANGES = [
  { label: '5천원 이하', value: 'under5k' },
  { label: '5천-1만', value: '5to10k' },
  { label: '1-2만', value: '10to20k' },
  { label: '2만 이상', value: 'over20k' },
];

const OPERATING_HOURS_OPTIONS = ['오전', '점심', '저녁', '심야'];

/* ═══════════════════════════════════════════════════════
   상세 데이터 테이블 — 정렬 가능한 row data (Mock)
   ═══════════════════════════════════════════════════════ */
interface CannRow {
  [key: string]: string;
  name: string;
  distance: string;
  impact: string;
  status: string;
}
interface NeighborhoodRow {
  [key: string]: string;
  name: string;
  score: string;
  closureRate: string;
  bep: string;
}

const CANNIBALIZATION_ROWS: CannRow[] = [
  { name: '연남파크점', distance: '450m', impact: '-2.1%', status: 'Safe' },
  { name: '홍대입구역점', distance: '820m', impact: '-0.8%', status: 'Safe' },
  { name: '망원시장점', distance: '1.2km', impact: '0.0%', status: 'None' },
  { name: '신촌로터리점', distance: '2.4km', impact: '0.0%', status: 'None' },
];

const NEIGHBORHOOD_ROWS: NeighborhoodRow[] = [
  { name: '연남동', score: '87 / 100', closureRate: '18%', bep: '3.5 개월' },
  { name: '서교동', score: '84 / 100', closureRate: '21%', bep: '4.1 개월' },
  { name: '망원동', score: '76 / 100', closureRate: '35%', bep: '5.2 개월' },
  { name: '합정동', score: '71 / 100', closureRate: '40%', bep: '6.0 개월' },
];

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
   DRILL-DOWN DRAWER MOCK DATA (v8.0)
   ⚠️ Frontend mockup. 백엔드 연동 시 SimulationOutput에서 직접 매핑.
   ═══════════════════════════════════════════════════════ */
type DrawerKey =
  | 'revenue'
  | 'attractiveness'
  | 'traffic'
  | 'cannibalization'
  | 'insight_legal'
  | 'insight_traffic'
  | 'insight_target'
  | null;

interface DetailDataEntry {
  title: string;
  aiReasoning?: string;
  confidence?: string;
  rank?: string;
  trend?: string;
  peakTime?: string;
  mainTarget?: string;
  warning?: string;
}

const mockDetailData: Record<string, DetailDataEntry> = {
  revenue: {
    title: '예상 월 매출 상세',
    aiReasoning:
      '유동인구 밀집도(상위 12%), 인근 동종업계 평균 매출액(2,800만) 대비 15% 초과 달성 예측. KT 통신 데이터 + 신용카드 매출 데이터 + LSTM 12개월 추세 모델 결합 분석.',
    confidence: '95%',
  },
  attractiveness: {
    title: '상권 종합 매력도 상세',
    aiReasoning:
      '7개 지표(유동인구·임대료·경쟁강도·매출추정·폐업률·성장성·접근성)를 가중 평균. 마포구 25개 동 중 상권 매력도 상위 8% 권역.',
    rank: '마포구 내 상위 8%',
    trend: '+5.2 Pts 지속 상승중',
  },
  traffic: {
    title: '일일 유동인구 상세',
    aiReasoning:
      'KT 통신사 셀룰러 데이터 기반 시간대별 체류 인구 측정. 18-21시 피크, 점심시간(12-14시) 보조 피크. 2030 여성 비중이 평균 대비 23% 높음.',
    peakTime: '18:00 - 21:00',
    mainTarget: '2030 여성 (68%)',
  },
  cannibalization: {
    title: '카니발리제이션 위험 상세',
    aiReasoning:
      '반경 500m 이내 동일 프랜차이즈 매장 진입 시 기존 매장 매출 감소율을 시뮬레이션. 거리 가중치 + 배후 세대 중첩률을 통합 산출.',
    warning: '반경 500m 내 동일 프랜차이즈 1개점 존재 (영향도 12%)',
  },
  insight_legal: {
    title: '상가임대차보호법 상세 분석',
    aiReasoning:
      '해당 권역 최근 3년 임대료 상승률 5.4%. 환산보증금 기준 초과 위기 매물 다수 감지. 계약 갱신 청구권 행사 시 법적 분쟁 가능성 높음. Legal Node가 14개 영역 3,775개 판례·법령 청크에서 유사 사례 검색.',
    warning: '환산보증금 한도 초과 위기 — 갱신 청구 시 임대인 거절 사유 발생 가능',
  },
  insight_traffic: {
    title: '저녁 시간대 매출 집중 분석',
    aiReasoning:
      '18시 이후 유동인구가 평균 대비 240% 증가. 인근 직장인 퇴근 동선 + 2030 여성 데이트 수요가 결합된 권역. 점심 매출이 약한 만큼, 저녁 메뉴 강화가 핵심 KPI.',
    peakTime: '18:00 - 21:00',
    mainTarget: '직장인 + 2030 여성',
  },
  insight_target: {
    title: '2030 여성 타겟 권역 분석',
    aiReasoning:
      '체류 인구 분석 결과 25-34세 여성 비중 68%. SNS 인스타그래머블 인테리어 + 디저트 메뉴 강화 시 객단가 +18%, 재방문율 +24% 예상.',
    confidence: '82%',
    mainTarget: '25-34세 여성 (68%)',
  },
};

/* ═══════════════════════════════════════════════════════
   NetworkBackground — Canvas 파티클 네트워크 배경
   ═══════════════════════════════════════════════════════
   - 화면 크기 비례 파티클 생성 (최대 350개)
   - 파티클 간 150px 이내 연결선 드로잉
   - scene === "intro" 일 때만 마우스 인터랙션 활성화:
     - 마그네틱 끌림 (반경 200px, 속도 0.02)
     - 마우스↔파티클 연결선 (반경 250px)
     - 클릭 시 레이더 핑 이펙트
   - isTransitioning 시 5배 가속, simulator 씬에서 0.2배 감속
*/

function NetworkBackground({
  isTransitioning,
  scene,
  theme,
}: {
  isTransitioning: boolean;
  scene: string;
  theme: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<{ x: number; y: number; vx: number; vy: number }[]>([]);
  const animRef = useRef<number>(0);
  const mouseRef = useRef<{ x: number; y: number }>({ x: -9999, y: -9999 });
  const pingRef = useRef<{ x: number; y: number; t: number }[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const onMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };
    const onClick = (e: MouseEvent) => {
      pingRef.current.push({ x: e.clientX, y: e.clientY, t: 0 });
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('click', onClick);

    // Init particles — responsive count based on screen area
    if (particlesRef.current.length === 0) {
      const particleCount = Math.min(350, Math.floor((canvas.width * canvas.height) / 8000));
      for (let i = 0; i < particleCount; i++) {
        particlesRef.current.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.6,
          vy: (Math.random() - 0.5) * 0.6,
        });
      }
    }

    const animate = () => {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const particles = particlesRef.current;
      let speedMult = 1;
      if (isTransitioning) speedMult = 5;
      else if (scene === 'simulator') speedMult = 0.2;

      const isLight = scene === 'simulator' && theme === 'light';
      const r = isLight ? 99 : 129;
      const g = isLight ? 102 : 140;
      const b = isLight ? 241 : 248;

      const isIntro = scene === 'intro';
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;

      // Update & draw particles
      for (const p of particles) {
        // Intro only: magnetic pull toward mouse
        if (isIntro) {
          const dmx = mx - p.x;
          const dmy = my - p.y;
          const md = Math.sqrt(dmx * dmx + dmy * dmy);
          if (md < 200 && md > 1) {
            const force = ((200 - md) / 200) * 0.015;
            p.vx += (dmx / md) * force;
            p.vy += (dmy / md) * force;
          }
        }

        p.x += p.vx * speedMult;
        p.y += p.vy * speedMult;
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r},${g},${b},0.5)`;
        ctx.fill();
      }

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(${r},${g},${b},${0.15 * (1 - dist / 150)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      // Intro only: mouse connection lines (radius 250, high visibility)
      if (isIntro && mx > 0) {
        for (const p of particles) {
          const dmx = mx - p.x;
          const dmy = my - p.y;
          const md = Math.sqrt(dmx * dmx + dmy * dmy);
          if (md < 250) {
            ctx.beginPath();
            ctx.moveTo(mx, my);
            ctx.lineTo(p.x, p.y);
            ctx.strokeStyle = `rgba(${r},${g},${b},${(1 - md / 250) * 0.8})`;
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }
        }

        // Radar ping effect
        const pings = pingRef.current;
        for (let i = pings.length - 1; i >= 0; i--) {
          const ping = pings[i];
          ping.t += 2;
          if (ping.t > 150) {
            pings.splice(i, 1);
            continue;
          }
          const alpha = 1 - ping.t / 150;
          ctx.beginPath();
          ctx.arc(ping.x, ping.y, ping.t, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(${r},${g},${b},${alpha * 0.3})`;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('click', onClick);
    };
  }, [isTransitioning, scene, theme]);

  const simClass = scene === 'simulator' ? 'scale-110 opacity-40' : 'scale-100 opacity-100';

  return (
    <canvas
      ref={canvasRef}
      className={`fixed inset-0 z-0 transition-all duration-1000 ${simClass}`}
    />
  );
}

/* ═══════════════════════════════════════════════════════
   Scene 1: Intro — 메인 진입 화면
   ═══════════════════════════════════════════════════════
   - 좌측: OHZI 스타일 타이포그래피 메뉴 (4개: About, Join Us, Simulator, Contact)
   - 우측: 로고 플로팅 + 앰버 글로우
   - 메뉴 클릭 시 transitionTo()로 해당 씬 이동 (암전 트랜지션)
*/

function IntroScene({
  activeMenuIndex,
  setActiveMenuIndex,
  onAboutClick,
  onLoginClick,
  onSimulatorClick,
  onContactClick,
}: {
  activeMenuIndex: number;
  setActiveMenuIndex: (i: number) => void;
  onAboutClick: () => void;
  onLoginClick: () => void;
  onSimulatorClick: () => void;
  onContactClick: () => void;
}) {
  return (
    <div className="relative z-10 h-full w-full overflow-hidden">
      {/* 🔐 Top-right 로그인 버튼 — 항상 간소하게 "로그인" 표시, 클릭 시 /login */}
      <button
        onClick={onLoginClick}
        className="absolute top-6 right-6 z-40 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#1e1b18]/70 backdrop-blur-md border border-[#3a3633] hover:border-[#818cf8] hover:bg-[#1e1b18] hover:shadow-[0_0_15px_rgba(129,140,248,0.25)] transition-all duration-200 text-[#9ca3af] hover:text-[#818cf8]"
        title="Login"
      >
        <LogIn className="w-3 h-3" />
        <span className="text-[11px] font-bold tracking-wider uppercase">Login</span>
      </button>

      {/* Background Watermark Logo (idea 5) — 화면을 가로지르는 거대한 반투명 로고 */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
        <img src="/logo.svg" alt="" className="w-[90vw] max-w-[1400px] h-auto opacity-[0.018]" />
      </div>

      {/* Right section — Floating Logo with Glow (원래 위치 복원) */}
      <div className="absolute right-[10%] top-1/2 -translate-y-1/2 p-10 cursor-pointer group hidden md:flex flex-col items-center pointer-events-auto z-30">
        <div className="relative animate-float-logo">
          <div className="absolute inset-0 bg-[#818cf8] blur-[50px] opacity-0 group-hover:opacity-30 transition-all duration-700 ease-out scale-75 group-hover:scale-125" />
          <img
            src="/logo.svg"
            alt="SPOTTER"
            className="w-48 h-auto relative z-10 opacity-90 transition-all duration-500 group-hover:scale-105 group-hover:drop-shadow-[0_0_30px_rgba(99,102,241,0.6)]"
          />
        </div>
        <div className="mt-8 text-center transition-all duration-500 group-hover:scale-105">
          <h1 className="text-4xl md:text-5xl font-black tracking-[0.2em] text-[#e2e8f0]">
            SPOTTER
          </h1>
          <p className="text-[#818cf8] font-mono text-xs tracking-widest mt-3 uppercase opacity-60 transition-opacity duration-500 group-hover:opacity-100">
            AI Franchise Simulator
          </p>
        </div>
      </div>

      {/* Left section — Typography menu (uniform single column) */}
      <div className="relative z-20 h-full flex flex-col justify-center pl-12 md:pl-20 lg:pl-32 pt-[18vh] pb-20">
        {/* Sub-copy */}
        <div className="flex items-center gap-4 mb-10 text-xs tracking-[0.3em] text-gray-500 uppercase">
          <div className="w-px h-4 bg-gray-600" />
          <span>
            0{activeMenuIndex + 1} / 0{MENU_ITEMS.length} — GET TO KNOW
          </span>
        </div>

        {/* Menu — SIMULATOR가 핵심이라 1단계 더 큼, 나머지는 보조 사이즈 */}
        <nav className="flex flex-col gap-3">
          {MENU_ITEMS.map((item, i) => {
            const isActive = activeMenuIndex === i;
            const isSimulator = i === 1;
            const sizeClasses = isSimulator
              ? 'text-3xl sm:text-5xl md:text-6xl lg:text-7xl'
              : 'text-2xl sm:text-4xl md:text-5xl lg:text-6xl';
            return (
              <button
                key={item}
                className="relative text-left group self-start whitespace-nowrap"
                style={{ width: 'fit-content', maxWidth: 'fit-content' }}
                onMouseEnter={() => setActiveMenuIndex(i)}
                onClick={() => {
                  if (i === 0) onAboutClick();
                  if (i === 1) onSimulatorClick();
                  if (i === 2) onContactClick();
                }}
              >
                {/* Indicator bar */}
                <div
                  className={`absolute -left-10 top-1/2 -translate-y-1/2 w-1.5 h-[80%] bg-[#818cf8] rounded-full transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] origin-top ${
                    isActive ? 'scale-x-100' : 'scale-x-0'
                  }`}
                />
                <span
                  className={`inline-block ${sizeClasses} font-black uppercase tracking-tight leading-none whitespace-nowrap origin-left transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                    isActive
                      ? 'text-[#e2e8f0] translate-x-0'
                      : 'text-[#3a3633] -translate-x-2 group-hover:text-[#9ca3af]'
                  }`}
                >
                  {item}
                </span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Marquee Strip (idea 4) — 화면 하단 가로 스크롤 데이터 띠 */}
      <div className="absolute bottom-0 left-0 w-full overflow-hidden border-t border-[#3a3633]/40 py-3 pointer-events-none z-20 bg-[#1e1b18]/50 backdrop-blur-sm">
        <div className="flex animate-marquee whitespace-nowrap">
          {[...Array(2)].map((_, k) => (
            <div
              key={k}
              className="flex items-center gap-12 px-6 font-mono text-[10px] uppercase tracking-[0.3em] shrink-0"
            >
              <span className="text-[#9ca3af]">AI Market Intelligence</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#818cf8]">Mapo-Gu MVP</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#9ca3af]">Cannibalization Analysis</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#9ca3af]">12-Month Forecast</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#818cf8]">Live Data · 19 Sources</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#9ca3af]">25 Districts</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#9ca3af]">LangGraph Multi-Agent</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#818cf8]">Project SPOTTER v3.8</span>
              <span className="text-[#3a3633]">●</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Scene 2: Accordion Gallery — 25개 구 선택 갤러리
   ═══════════════════════════════════════════════════════
   - 수평 스크롤 갤러리 (휠→가로 변환, Edge Panning, 드래그 스크롤)
   - 패널 호버 시 확장 + SVG 휘장 표시 + Staggered 글자 애니메이션
   - 상단 3열 헤더: 로고+BACK | 인디케이터 눈금 | SCROLL TO EXPLORE
   - 마포구 클릭 시 → /simulator로 이동
   - 자체 헤더를 갖고 있어 글로벌 헤더와 별도 (accordion 씬 자체 관리)
*/

function AccordionGallery({
  hoveredIdx,
  setHoveredIdx,
  onMapoClick,
  onLogoClick,
}: {
  hoveredIdx: number | null;
  setHoveredIdx: (i: number | null) => void;
  onMapoClick: () => void;
  onLogoClick: () => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const edgeScrollRef = useRef<number>(0);
  const edgeSpeedRef = useRef(0);

  // Drag scroll state
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragScrollLeft = useRef(0);

  // Wheel → horizontal scroll
  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      track.scrollLeft += e.deltaY * 1.5;
    };
    track.addEventListener('wheel', handler, { passive: false });
    return () => track.removeEventListener('wheel', handler);
  }, []);

  // Edge panning — rAF loop
  useEffect(() => {
    const tick = () => {
      const track = trackRef.current;
      if (track && edgeSpeedRef.current !== 0) {
        track.scrollLeft += edgeSpeedRef.current;
      }
      edgeScrollRef.current = requestAnimationFrame(tick);
    };
    edgeScrollRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(edgeScrollRef.current);
  }, []);

  // Mouse move → edge panning detection
  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const w = window.innerWidth;
      const x = e.clientX;
      const edgeZone = w * 0.15;

      if (x < edgeZone) {
        // Left edge — closer to edge = faster
        edgeSpeedRef.current = -((edgeZone - x) / edgeZone) * 12;
      } else if (x > w - edgeZone) {
        // Right edge
        edgeSpeedRef.current = ((x - (w - edgeZone)) / edgeZone) * 12;
      } else {
        edgeSpeedRef.current = 0;
      }

      // Drag scroll
      if (isDragging && trackRef.current) {
        const dx = e.clientX - dragStartX.current;
        trackRef.current.scrollLeft = dragScrollLeft.current - dx;
      }
    },
    [isDragging],
  );

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    dragStartX.current = e.clientX;
    dragScrollLeft.current = trackRef.current?.scrollLeft ?? 0;
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleMouseLeaveTrack = useCallback(() => {
    setIsDragging(false);
    edgeSpeedRef.current = 0;
  }, []);

  return (
    <div
      className="relative z-10 flex flex-col h-full w-full"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeaveTrack}
    >
      {/* Top bar — 3-column: Logo+Back | Indicator | Guide */}
      <div className="w-full h-24 border-b border-[#3a3633]/50 flex items-center px-8 md:px-16 justify-between bg-[#1e1b18]/80 backdrop-blur-md z-50 shrink-0">
        {/* Left — Logo + Back */}
        <div className="flex items-center gap-3 min-w-[180px]">
          <button
            onClick={onLogoClick}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.svg" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-[#e2e8f0]">SPOTTER</span>
          </button>
          <span className="text-[#3a3633]">/</span>
          <button
            onClick={onLogoClick}
            className="flex items-center gap-1.5 text-xs text-[#9ca3af] hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>

        {/* Center — Indicator */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-[3px]">
            {DISTRICTS.map((d, i) => (
              <div
                key={d.eng}
                className={`w-1 h-3 rounded-full transition-all duration-300 ${
                  hoveredIdx === i
                    ? 'bg-indigo-400 scale-y-150 shadow-[0_0_10px_rgba(99,102,241,0.5)]'
                    : 'bg-white/20'
                }`}
              />
            ))}
          </div>
          <span className="ml-3 text-xs text-gray-400 font-mono tabular-nums min-w-[80px]">
            {hoveredIdx !== null
              ? `${DISTRICTS[hoveredIdx].name} ${hoveredIdx + 1}`
              : '25 Districts'}{' '}
            / 25
          </span>
        </div>

        {/* Right — Guide text */}
        <div className="min-w-[180px] text-right">
          <span className="text-xs text-gray-600 tracking-widest">SCROLL TO EXPLORE</span>
        </div>
      </div>

      {/* Gallery track */}
      <div
        ref={trackRef}
        className={`flex-1 flex items-center gap-2 md:gap-3 overflow-x-auto scrollbar-hide px-4 ${
          isDragging ? 'cursor-grabbing' : 'cursor-grab'
        }`}
        onMouseDown={handleMouseDown}
      >
        {DISTRICTS.map((d, i) => {
          const isHovered = hoveredIdx === i;
          const isMapo = i === MAPO_IDX;

          return (
            <div
              key={d.eng}
              className={`group/panel relative h-[65vh] shrink-0 rounded-2xl overflow-hidden bg-[#3a3633] transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                isMapo ? 'cursor-pointer' : 'cursor-not-allowed'
              } ${
                isHovered
                  ? 'w-[320px] md:w-[480px] z-10 shadow-[0_0_30px_rgba(129,140,248,0.3)]'
                  : 'w-[70px] md:w-[80px] z-0'
              }`}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
              onClick={() => {
                if (isMapo && !isDragging) onMapoClick();
              }}
            >
              {/* Parallax background image */}
              <div
                className={`absolute inset-0 w-full h-full bg-contain bg-center bg-no-repeat transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                  isHovered
                    ? 'scale-100 opacity-80 grayscale-0'
                    : 'scale-[0.9] opacity-30 grayscale-0'
                }`}
                style={{ backgroundImage: `url(${d.img})` }}
              />

              {/* Gradient mask */}
              <div className="absolute inset-0 bg-gradient-to-t from-[#1e1b18] via-[#1e1b18]/60 to-transparent opacity-90 transition-opacity duration-1000" />

              {/* English name (shown on hover) */}
              <div
                className={`absolute top-12 left-6 right-6 transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                  isHovered ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
                }`}
              >
                <span className="text-xs tracking-[0.3em] text-gray-400 font-light uppercase">
                  {d.eng}-GU
                </span>
              </div>

              {/* Mapo badge (shown on hover) */}
              {isMapo && (
                <div
                  className={`absolute top-24 left-6 transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                    isHovered ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
                  }`}
                >
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs">
                    <Activity size={12} />
                    분석 가능
                  </span>
                </div>
              )}

              {/* ★ Staggered Letter Animation ★ */}
              <div className="absolute inset-0 pointer-events-none p-4 md:p-8">
                <div className="relative w-full h-full">
                  {/* Hover: horizontal staggered text */}
                  <h2 className="absolute left-6 md:left-8 bottom-24 md:bottom-20 flex gap-[2px]">
                    {d.name.split('').map((char, ci) => (
                      <span
                        key={ci}
                        className={`font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-white to-[#a3a3a3] transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] ${
                          isHovered
                            ? 'text-4xl md:text-5xl opacity-100 translate-y-0 blur-0'
                            : 'text-4xl md:text-5xl opacity-0 translate-y-10 blur-[4px]'
                        }`}
                        style={{
                          transitionDelay: isHovered ? `${ci * 40 + 100}ms` : '0ms',
                        }}
                      >
                        {char}
                      </span>
                    ))}
                  </h2>

                  {/* Default: vertical stacked staggered text */}
                  <h2 className="absolute left-1/2 -translate-x-1/2 bottom-10 md:bottom-12 flex flex-col items-center gap-1">
                    {d.name.split('').map((char, ci) => (
                      <span
                        key={ci}
                        className={`font-black text-transparent bg-clip-text bg-gradient-to-b from-white to-[#a3a3a3] leading-none transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] ${
                          isHovered
                            ? 'text-2xl md:text-3xl opacity-0 -translate-y-10 blur-[4px]'
                            : 'text-2xl md:text-3xl opacity-60 translate-y-0 blur-0'
                        }`}
                        style={{
                          transitionDelay: isHovered ? '0ms' : `${ci * 40 + 100}ms`,
                        }}
                      >
                        {char}
                      </span>
                    ))}
                  </h2>

                  {/* Bottom info */}
                  <div
                    className={`absolute left-0 bottom-0 flex flex-col items-start transition-all duration-[1000ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                      isHovered
                        ? 'opacity-100 translate-y-0 delay-[300ms]'
                        : 'opacity-0 translate-y-4 pointer-events-none'
                    }`}
                  >
                    {isMapo ? (
                      <div className="flex items-center gap-2 text-indigo-300 text-sm">
                        <Play size={14} />
                        <span>클릭하여 시뮬레이션 시작</span>
                      </div>
                    ) : (
                      <span className="px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 text-[9px] font-bold tracking-wider">
                        서비스 준비 중
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   About Page — 프로젝트 소개 에디토리얼 랜딩
   ═══════════════════════════════════════════════════════
   - Section 1: Hero (문제 정의 + "SPOTTER는 여기서 시작합니다")
   - Section 2: 5가지 차별점 (워터마크 넘버링)
   - Section 3: 기존 서비스 비교표 (취소선 vs 앰버 강조)
   - Section 4: 7개 공공데이터 배지 + NOW/NEXT/FUTURE 로드맵
*/

const FEATURES = [
  {
    num: '01',
    title: '카니발리제이션(자기잠식) 분석',
    desc: '같은 브랜드 기존 매장과의 영향권 중첩을 계산하여 매출 잠식률을 산출합니다. "3호점을 내면 1호점 매출이 얼마나 깎이는가?"에 대한 정량적 답을 제시합니다.',
  },
  {
    num: '02',
    title: '간접 경쟁(대체재) 분석',
    desc: '치킨집의 경쟁상대는 옆 치킨집만이 아닙니다. 피자·족발·배달 야식 등 소비 카테고리 전체의 경쟁 강도를 가중치 기반으로 반영합니다.',
  },
  {
    num: '03',
    title: 'What-if 시나리오 시뮬레이션',
    desc: '경쟁 매장 진입, 최저임금 변화, 임대료 상승 등 조건을 변경하면 즉시 재시뮬레이션합니다. 미래의 불확실성을 데이터로 대비하세요.',
  },
  {
    num: '04',
    title: '12개월 시간 축 예측',
    desc: '단순 스냅샷이 아닌, 12개월간의 매출 추이·경쟁 반응·생존 확률을 시계열로 예측합니다.',
  },
  {
    num: '05',
    title: '법률 리스크 AI 검토 (RAG)',
    desc: '가맹사업법 영업지역 보호, 상가임대차보호법 위반 여부를 AI가 자동으로 검토하여 법적 리스크를 사전에 차단합니다.',
  },
];

const COMPARISONS = [
  { old: '현재 상권 스냅샷만 제공', arrow: '→', now: '12개월 미래 예측 시뮬레이션' },
  { old: '같은 업종 경쟁만 분석', arrow: '→', now: '간접 경쟁(대체재)까지 반영' },
  { old: '자기잠식 분석 불가', arrow: '→', now: '카니발리제이션 정량 산출' },
  { old: '컨설팅 비용 수천만 원', arrow: '→', now: 'AI 기반 즉시 분석' },
  { old: '정적 리포트 1회 제공', arrow: '→', now: 'What-if 무제한 재시뮬레이션' },
  { old: '법률 리스크 수동 검토', arrow: '→', now: 'RAG 기반 자동 법률 검토' },
];

const DATA_SOURCES = [
  '소상공인시장진흥공단',
  '서울 생활인구 (KT)',
  '통계청 SGIS',
  '국토부 실거래가',
  '공정위 정보공개서',
  '서울 상권분석 (golmok)',
  'Naver DataLab',
];

const ROADMAP = [
  { phase: 'NOW', label: '서울시 마포구 16개 행정동 분석 지원' },
  { phase: 'NEXT', label: '서울 전체 25개 구 확장 + 프랜차이즈 브랜드 DB 고도화' },
  { phase: 'FUTURE', label: '전국 단위 확장 + 실시간 매출 데이터 연동 + B2B SaaS 출시' },
];

function AboutPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="absolute inset-0 z-20 overflow-y-auto bg-[#1e1b18]/95 backdrop-blur-sm text-[#e2e8f0] pb-32 custom-scrollbar">
      {/* Header */}
      <div className="fixed top-0 left-0 w-full h-24 border-b border-[#3a3633]/50 flex items-center px-8 md:px-16 bg-[#1e1b18]/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.svg" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-[#e2e8f0]">SPOTTER</span>
          </button>
          <span className="text-[#3a3633]">/</span>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-[#9ca3af] hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-8 md:px-16 pt-24">
        {/* ── Section 1: Hero ── */}
        <section className="min-h-[80vh] flex flex-col justify-center animate-[fadeSlideIn_1s_ease-out]">
          <p className="text-lg md:text-xl text-[#9ca3af] mb-6 tracking-wide">
            기존 상권분석 도구는{' '}
            <span className="text-[#818cf8] font-bold text-2xl md:text-3xl">'지금'</span>만
            보여줍니다.
          </p>

          <div className="flex flex-col gap-4 my-10">
            {[
              '이 자리에 매장을 내면, 1년 뒤 매출은 얼마일까?',
              '같은 브랜드 3호점이 1호점 매출을 얼마나 잡아먹을까?',
              '옆에 경쟁 매장이 들어오면, 내 생존 확률은?',
            ].map((q, i) => (
              <div
                key={i}
                className="border-l-2 border-indigo-500 pl-6 py-2"
                style={{ animationDelay: `${i * 150 + 300}ms` }}
              >
                <p className="text-xl md:text-2xl font-medium text-[#e2e8f0]/80 italic">"{q}"</p>
              </div>
            ))}
          </div>

          <h2 className="text-3xl md:text-5xl font-black mt-10 tracking-tight leading-tight">
            <span className="text-[#818cf8]">SPOTTER</span>는
            <br />
            여기서 시작합니다.
          </h2>
        </section>

        {/* ── Section 2: What We Do Differently ── */}
        <section className="py-24">
          <div className="flex items-center gap-4 mb-16">
            <div className="w-12 h-px bg-[#818cf8]" />
            <h3 className="text-xs font-mono tracking-[0.3em] text-[#9ca3af] uppercase">
              What We Do Differently
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
            {FEATURES.map((f) => (
              <div key={f.num} className="relative pl-2 pt-6">
                <span className="font-mono text-5xl md:text-7xl font-black text-[#3a3633] absolute -top-6 -left-4 opacity-50 z-0 select-none">
                  {f.num}
                </span>
                <h4 className="text-xl font-bold text-[#e2e8f0] mb-3 relative z-10">{f.title}</h4>
                <p className="text-[#9ca3af] leading-relaxed relative z-10">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Section 3: Comparison ── */}
        <section className="py-24">
          <div className="flex items-center gap-4 mb-16">
            <div className="w-12 h-px bg-[#818cf8]" />
            <h3 className="text-xs font-mono tracking-[0.3em] text-[#9ca3af] uppercase">
              Compared to Existing Solutions
            </h3>
          </div>

          <div className="flex flex-col">
            {COMPARISONS.map((c, i) => (
              <div
                key={i}
                className="flex justify-between items-center py-4 border-b border-[#3a3633]/50"
              >
                <span className="text-[#d1d5db] line-through decoration-[#3a3633] flex-1 text-sm">
                  {c.old}
                </span>
                <span className="text-[#3a3633] font-mono mx-6 shrink-0">{c.arrow}</span>
                <span className="text-indigo-400 font-bold text-lg flex-1 text-right">{c.now}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Section 4: Data & Roadmap ── */}
        <section className="py-24">
          {/* Data sources */}
          <div className="mb-20">
            <div className="flex items-center gap-4 mb-10">
              <div className="w-12 h-px bg-[#818cf8]" />
              <h3 className="text-xs font-mono tracking-[0.3em] text-[#9ca3af] uppercase">
                Data &amp; Trust
              </h3>
            </div>
            <p className="text-[#9ca3af] mb-6 text-sm">
              7개 공공데이터 API 기반 — 신뢰할 수 있는 데이터만 사용합니다.
            </p>
            <div className="flex flex-wrap gap-3">
              {DATA_SOURCES.map((src) => (
                <span
                  key={src}
                  className="px-4 py-2 rounded-full border border-[#3a3633] bg-[#2c2825] text-sm text-[#9ca3af] hover:border-indigo-500/50 hover:text-[#e2e8f0] transition-colors cursor-default"
                >
                  {src}
                </span>
              ))}
            </div>
          </div>

          {/* Roadmap */}
          <div>
            <div className="flex items-center gap-4 mb-10">
              <div className="w-12 h-px bg-[#818cf8]" />
              <h3 className="text-xs font-mono tracking-[0.3em] text-[#9ca3af] uppercase">
                Roadmap
              </h3>
            </div>
            <div className="flex flex-col gap-8">
              {ROADMAP.map((r, i) => (
                <div key={i} className="flex items-start gap-6">
                  <span className="font-mono text-indigo-400 w-24 shrink-0 text-sm font-bold pt-0.5">
                    {r.phase}
                  </span>
                  <div className="flex items-start gap-4">
                    <div className="mt-2 w-2 h-2 rounded-full bg-[#818cf8] shrink-0" />
                    <p className="text-[#e2e8f0] leading-relaxed">{r.label}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Contact Page — 벤토 박스 디지털 명함
   ═══════════════════════════════════════════════════════
   - 좌측: Mega Typography (GET IN TOUCH.)
   - 우측: Bento Grid (Workspace 4링크, Team, Location, Direct Inquiry)
   - 100vh One-page Fit (스크롤 없음)
*/

function ContactPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col bg-[#1e1b18]/95 backdrop-blur-sm text-[#e2e8f0] pb-10">
      {/* Header */}
      <div className="fixed top-0 left-0 w-full h-24 border-b border-[#3a3633]/50 flex items-center px-8 md:px-16 bg-[#1e1b18]/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.svg" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-[#e2e8f0]">SPOTTER</span>
          </button>
          <span className="text-[#3a3633]">/</span>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-[#9ca3af] hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex flex-col justify-center pt-24 px-8 md:px-16 overflow-hidden">
        <div className="max-w-6xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left — Mega Typography */}
          <div
            className="lg:col-span-5 flex flex-col justify-center"
            style={{ animation: 'fadeSlideIn 1s ease-out' }}
          >
            <span className="font-mono text-indigo-400 tracking-widest mb-4 text-xs">
              PROJECT SPOTTER
            </span>
            <h1 className="text-5xl lg:text-7xl xl:text-8xl font-black uppercase leading-none mb-8">
              GET IN
              <br />
              <span className="text-[#818cf8]">TOUCH.</span>
            </h1>
            <p className="text-[#d1d5db] leading-relaxed text-sm max-w-sm">
              AI 기반 프랜차이즈 상권분석 시뮬레이터 프로젝트에 대한 상세한 코드와 기획 문서는 아래
              워크스페이스에서 확인하실 수 있습니다.
            </p>
          </div>

          {/* Right — Bento Box */}
          <div className="lg:col-span-7 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Card 1: Workspace — full width */}
            <div
              className="group/card md:col-span-2 relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: 'fadeSlideIn 1s ease-out 100ms both' }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-5 md:p-6 flex flex-col justify-center">
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-4 block">
                  Workspace
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                    <div
                      className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                      style={{
                        background:
                          'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                      }}
                    />
                    <a
                      href="https://github.com/Himidea-AI/Final_Project"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <GitFork
                          size={18}
                          className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors"
                        />
                        <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">
                          GitHub
                        </span>
                      </div>
                      <ExternalLink
                        size={14}
                        className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors"
                      />
                    </a>
                  </div>
                  <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                    <div
                      className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                      style={{
                        background:
                          'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                      }}
                    />
                    <a
                      href="https://www.notion.so/333ac2a0181b802b807cf7de2447b890"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <ExternalLink
                          size={18}
                          className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors"
                        />
                        <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">
                          Notion
                        </span>
                      </div>
                      <ExternalLink
                        size={14}
                        className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors"
                      />
                    </a>
                  </div>
                  <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                    <div
                      className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                      style={{
                        background:
                          'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                      }}
                    />
                    <a
                      href="https://www.figma.com/board/lkjvfmKP4FU5XWBAyWR52a/%EC%A0%9C%EB%AA%A9-%EC%97%86%EC%9D%8C?node-id=0-1&p=f&t=ZITF88ooGHZ2rrHV-0"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <ExternalLink
                          size={18}
                          className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors"
                        />
                        <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">
                          Figma
                        </span>
                      </div>
                      <ExternalLink
                        size={14}
                        className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors"
                      />
                    </a>
                  </div>
                  <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                    <div
                      className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                      style={{
                        background:
                          'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                      }}
                    />
                    <a
                      href="https://bat981120.atlassian.net/jira/software/projects/IM3/boards/2"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <ExternalLink
                          size={18}
                          className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors"
                        />
                        <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">
                          Jira
                        </span>
                      </div>
                      <ExternalLink
                        size={14}
                        className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors"
                      />
                    </a>
                  </div>
                </div>
              </div>
            </div>

            {/* Card 2: Team Info */}
            <div
              className="group/card relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: 'fadeSlideIn 1s ease-out 200ms both' }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-5 md:p-6 flex flex-col justify-center">
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-2 block">
                  Team
                </span>
                <p className="text-lg font-bold text-white mb-4">
                  AI 심화과정 6인 팀 프로젝트 (3조)
                </p>
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-2 block">
                  Mentor
                </span>
                <p className="text-lg font-bold text-white">황태림</p>
              </div>
            </div>

            {/* Card 3: Location */}
            <div
              className="group/card relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: 'fadeSlideIn 1s ease-out 300ms both' }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-5 md:p-6 flex flex-col justify-center">
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-4 block">
                  Location
                </span>
                <div className="flex items-center gap-3">
                  <MapPin className="text-indigo-400 w-6 h-6 shrink-0" />
                  <span className="text-lg font-bold text-white leading-tight">
                    강남 하이미디어
                    <br />
                    아카데미
                  </span>
                </div>
              </div>
            </div>

            {/* Card 4: Direct Inquiry — full width */}
            <div
              className="group/card md:col-span-2 relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: 'fadeSlideIn 1s ease-out 400ms both' }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-5 md:p-6 flex flex-col justify-center">
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-4 block">
                  Direct Inquiry
                </span>
                <div className="flex flex-wrap gap-8">
                  <a
                    href="mailto:bat981120@gmail.com"
                    className="text-xl md:text-2xl font-black hover:text-indigo-400 transition-colors flex items-center gap-3"
                  >
                    <Mail className="w-5 h-5 text-[#9ca3af] shrink-0" />
                    bat981120@gmail.com
                  </a>
                  <a
                    href="tel:01067790080"
                    className="text-xl md:text-2xl font-black hover:text-indigo-400 transition-colors flex items-center gap-3"
                  >
                    <Phone className="w-5 h-5 text-[#9ca3af] shrink-0" />
                    010.6779.0080
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Scene 3: Simulator Dashboard — 시뮬레이션 대시보드
   ═══════════════════════════════════════════════════════
   [상태 플로우]
   idle    → 조건 입력 대기 (좌측 패널: 구/동 드롭다운, 반경, 임대료)
   loading → RUN SIMULATION 클릭 → API 호출 + 로딩 스트리밍 텍스트
   result  → 하이엔드 대시보드 (StatCard, SVG 차트, 레이더, 테이블, AI 인사이트)

   [백엔드 연동 (api/client.ts)]
   runSim() → runSimulation() 단일 호출 (v12.4: /simulate만 호출, /analyze 제거)
   응답 → SimResult로 변환 → UI 바인딩
   API 실패 시 fallback Mock 표시 (에러에도 화면 유지)

   [팀원 참고 — B1/A1]
   SimulationOutput.comparison 배열 → 동별 비교 테이블 데이터
   SimulationOutput.legal_risks 배열 → AI 인사이트 법률 경고
   SimulationOutput.market_report → 7개 항목별 차트 데이터 (backend main.py:308)
*/

/* ═══════════════════════════════════════════════════════
   Chart Mock Data + Custom Tooltip (Recharts 기반, Patch v13.0)
   — simResult → 실 API 데이터로 교체될 임시 mock
   ═══════════════════════════════════════════════════════ */
const CHART_BASE_DATE = (() => {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
})();

// 24H 시간대별 데이터 (today 06:00 → 익일 02:00)
const DAILY_CHART_DATA = [
  { time: CHART_BASE_DATE.getTime() + 6 * 3600000, revenue: 150, traffic: 120 },
  { time: CHART_BASE_DATE.getTime() + 10 * 3600000, revenue: 480, traffic: 320 },
  { time: CHART_BASE_DATE.getTime() + 14 * 3600000, revenue: 350, traffic: 250 },
  { time: CHART_BASE_DATE.getTime() + 18 * 3600000, revenue: 850, traffic: 580 },
  { time: CHART_BASE_DATE.getTime() + 22 * 3600000, revenue: 920, traffic: 450 },
  { time: CHART_BASE_DATE.getTime() + 26 * 3600000, revenue: 200, traffic: 100 },
];

// 12M 매출 예측 (LSTM 출력 placeholder)
const MONTHLY_CHART_DATA = Array.from({ length: 12 }).map((_, i) => {
  const d = new Date();
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  d.setMonth(d.getMonth() + i);
  return {
    time: d.getTime(),
    revenue: Math.floor(Math.random() * 500) + 500,
    traffic: Math.floor(Math.random() * 300) + 300,
  };
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function RechartsDarkTooltip(props: any) {
  const { active, payload, label } = props;
  const mode: 'daily' | 'monthly' = props.chartMode ?? 'daily';
  if (!active || !payload || !payload.length) return null;
  const date = new Date(label);
  const title =
    mode === 'daily'
      ? `${String(date.getHours() % 24).padStart(2, '0')}:00`
      : `${date.getFullYear()}년 ${date.getMonth() + 1}월`;

  return (
    <div className="bg-[#1e1b18] border border-[#3a3633] rounded-lg shadow-2xl px-4 py-3 text-xs min-w-[180px]">
      <div className="text-[10px] text-[#9ca3af] font-mono mb-2 tracking-widest uppercase">
        {title}
      </div>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((p: any) => {
        const isRevenue = p.dataKey === 'revenue';
        return (
          <div key={p.dataKey} className="flex items-center justify-between gap-3 py-0.5">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: p.stroke }} />
              <span className="text-[#9ca3af]">{isRevenue ? '예상 매출' : '유동인구'}</span>
            </div>
            <span className="text-white font-bold">
              {isRevenue
                ? `₩ ${(p.value * 10000).toLocaleString()}`
                : `${(p.value * 100).toLocaleString()} 명`}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * SimulatorDashboard — 시뮬레이션 분석 결과 대시보드
 * idle → loading(Progress Bar) → result(KPI + 차트 + 테이블)
 * API 실패 시 generateSmartMock() 폴백, businessType은 백엔드 연동 전 하드코딩
 */
function SimulatorDashboard({
  reportState,
  setReportState,
}: {
  reportState: string;
  setReportState: (s: 'idle' | 'loading' | 'result') => void;
}) {
  const [radius, setRadius] = useState(500);
  const [budget, setBudget] = useState(200);
  const [weighted, setWeighted] = useState(true);
  const [loadingText, setLoadingText] = useState('INITIALIZING AI ENGINE...');
  const [loadingProgress, setLoadingProgress] = useState(0);
  const { showToast } = useToast();
  const { user } = useAuth();
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  const [chartView, setChartView] = useState<'daily' | 'monthly'>('daily');
  const [tableView, setTableView] = useState<'cannibalization' | 'neighborhoods'>(
    'cannibalization',
  );
  const [dashboardMode, setDashboardMode] = useState<'data' | 'map'>('data');
  const [isDownloadOpen, setIsDownloadOpen] = useState(false);
  const [selectedGu] = useState('마포구');
  const [selectedDongs, setSelectedDongs] = useState<string[]>(() => [...DONG_DATA['마포구']]);
  const [dongDropdownOpen, setDongDropdownOpen] = useState(false);

  // [Frontend Mockup] 백엔드 연동 보류 — SimulationInput 확장 후 페이로드 매핑 필요
  const [businessType, setBusinessType] = useState('커피-음료');
  const [businessTypeOpen, setBusinessTypeOpen] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [storeArea, setStoreArea] = useState(15); // 평
  const [targetPrice, setTargetPrice] = useState('5to10k');
  const [operatingHours, setOperatingHours] = useState<string[]>(['점심', '저녁']);
  const [isWorkflowOpen, setIsWorkflowOpen] = useState(false);
  const [isSplitMode, setIsSplitMode] = useState(false);
  const [tableDensity, setTableDensity] = useState<'comfortable' | 'standard' | 'compact'>(
    'standard',
  );
  const [initialCapital, setInitialCapital] = useState(5000); // 만원

  // [A1] 유동인구 실시간 데이터
  const [popData, setPopData] = useState<any>(null);
  const [popLoading, setPopLoading] = useState(false);

  useEffect(() => {
    if (reportState !== 'result' || selectedDongs.length === 0) return;
    let cancelled = false;
    const fetchPop = async () => {
      setPopLoading(true);
      try {
        const { getLivePopulation } = await import('./api/client');
        const data = await getLivePopulation(selectedDongs);
        if (!cancelled) setPopData(data);
      } catch (e) {
        console.error('유동인구 API 실패:', e);
      } finally {
        if (!cancelled) setPopLoading(false);
      }
    };
    fetchPop();
    return () => {
      cancelled = true;
    };
  }, [reportState, selectedDongs]);

  // [v8.0/v8.1] Drill-down Drawer + 테이블 행 확장 + 정렬 상태
  const [activeDrawer, setActiveDrawer] = useState<DrawerKey>(null);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
      } else {
        setSortKey(key);
        setSortDir('asc');
      }
      setExpandedRow(null); // 정렬 변경 시 펼침 초기화
    },
    [sortKey, sortDir],
  );

  // 테이블 뷰 변경 시 정렬/펼침 초기화 헬퍼
  const handleTableViewChange = useCallback((view: 'cannibalization' | 'neighborhoods') => {
    setTableView(view);
    setSortKey(null);
    setExpandedRow(null);
  }, []);

  // 정렬된 행 데이터 — 가맹점 간섭도는 competitor_intel.samples 실데이터 우선
  // Pancras 2013 기반 거리 감쇠 모델: 0.813^km × base_rate(30%)
  // 원문 "1마일(1.609km)당 28.1% 감소" → per-km decay = (1-0.281)^(1/1.609) = 0.813
  const dynamicCannRows: CannRow[] = simResult?.competitorIntel?.competition_500m?.samples
    ? simResult.competitorIntel.competition_500m.samples.slice(0, 8).map((s) => {
        const dist = s.distance_m;
        const impactPct = -0.3 * Math.pow(0.813, dist / 1000) * 100;
        const status = dist < 300 ? 'Danger' : dist < 800 ? 'Caution' : 'Safe';
        return {
          name: s.place_name,
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
        bep: typeof r.bep_months === 'number' ? `${r.bep_months}개월` : '—',
      }))
    : [];
  const sortedNeighborhoodRows = sortRows(dynamicNeighborhoodRows, sortKey, sortDir);

  // 분기 매출 예측 차트 데이터 — /simulate 응답의 quarterly_projection을 Recharts time축 형식으로 변환
  const monthlyChartData = simResult?.quarterlyProjection?.length
    ? simResult.quarterlyProjection.map((q) => ({
        time: q.quarter, // X축: 분기 번호 (1~4)
        revenue: Math.round(q.revenue / 10000), // 원 → 만원 스케일 통일
        traffic: Math.round(q.confidence_lower / 10000),
        confidence_upper: Math.round(q.confidence_upper / 10000),
      }))
    : MONTHLY_CHART_DATA;

  // 레이더 차트 7축 꼭지점 — market_report 기반 동적 계산
  // 순서: 유동인구(12시) → 매출(2시) → 성장성(4시) → 폐업률(6시) → 임대료(8시) → 경쟁강도(10시) → 접근성(11시)
  const RADAR_FALLBACK_VALUES = [82, 74, 56, 9, 45, 68, 78]; // mock fallback
  const radarValues = simResult?.marketReport
    ? [
        simResult.marketReport.floating_population,
        simResult.marketReport.estimated_revenue,
        simResult.marketReport.growth_potential,
        simResult.marketReport.closure_rate != null
          ? Math.round(simResult.marketReport.closure_rate * 100)
          : 100 - simResult.marketReport.survival_rate,
        simResult.marketReport.rent_index,
        simResult.marketReport.competition_intensity,
        simResult.marketReport.accessibility,
      ]
    : RADAR_FALLBACK_VALUES;
  const RADAR_LABELS = [
    '유동인구',
    '매출',
    '성장성',
    '폐업률',
    '임대료',
    '경쟁강도',
    '접근성',
  ] as const;
  const radarVertices = radarValues.map((v, k) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * k) / 7;
    const r = Math.max(0, Math.min(100, v)) * 0.6; // max radius 60px
    return {
      x: 100 + Math.cos(angle) * r,
      y: 100 + Math.sin(angle) * r,
      value: v,
      label: RADAR_LABELS[k],
    };
  });
  const radarPointsStr = radarVertices.map((v) => `${v.x.toFixed(1)},${v.y.toFixed(1)}`).join(' ');

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
        ['Document ID', `SPTR-${Date.now().toString().slice(-8)}`],
        [],
        ['KPI 요약'],
        ['지표', '값', '트렌드'],
        [
          '예상 월 매출 (추정)',
          `₩ ${((simResult?.revenue ?? 3240) * 10000).toLocaleString()}`,
          '+12.5%',
        ],
        ['상권 종합 매력도', `${simResult?.score ?? 87} / 100`, '+5.2 Pts'],
        [
          '일일 유동인구',
          popData?.daily_average ? `${popData.daily_average.toLocaleString()} 명` : '42,105 명',
          popData?.date ?? '-2.4%',
        ],
        ['카니발리제이션 위험', `${simResult?.riskLevel ?? 'Low'} (12%)`, '안전 권역'],
        [],
        ['7 Core Metrics (레이더 차트)'],
        ['항목', '점수'],
        ...(simResult?.chartData ?? CHART_DATA).map((d) => [d.label, d.value]),
      ];
      const ws1 = XLSX.utils.aoa_to_sheet(summary);
      ws1['!cols'] = [{ wch: 25 }, { wch: 25 }, { wch: 15 }];
      XLSX.utils.book_append_sheet(wb, ws1, '요약');

      // Sheet 2: 가맹점 간섭도 (실데이터 없으면 Mock fallback)
      const cannRowsForExport = sortedCannRows.length > 0 ? sortedCannRows : CANNIBALIZATION_ROWS;
      const cann: (string | number)[][] = [
        ['가맹점명', '거리', '예상 매출 하락', '상태'],
        ...cannRowsForExport.map((r) => [r.name, r.distance, r.impact, r.status]),
      ];
      const ws2 = XLSX.utils.aoa_to_sheet(cann);
      ws2['!cols'] = [{ wch: 20 }, { wch: 12 }, { wch: 15 }, { wch: 12 }];
      XLSX.utils.book_append_sheet(wb, ws2, '가맹점 간섭도');

      // Sheet 3: 행정동 비교 (실데이터 없으면 Mock fallback)
      const neighborhoodRowsForExport =
        sortedNeighborhoodRows.length > 0 ? sortedNeighborhoodRows : NEIGHBORHOOD_ROWS;
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
  ]);

  const toggleOperatingHour = useCallback((hour: string) => {
    setOperatingHours((prev) =>
      prev.includes(hour) ? prev.filter((h) => h !== hour) : [...prev, hour],
    );
  }, []);

  // 결과 화면 진입 시 스크롤을 맨 위로 리셋 (리포트 최상단부터 보이도록)
  const dashboardRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (reportState === 'result' && dashboardRef.current) {
      dashboardRef.current.scrollTop = 0;
    }
  }, [reportState]);

  // 브라우저 뒤로가기 가로채기 — result 상태에서 뒤로가기 누르면 페이지 이탈 대신 idle로 복귀
  useEffect(() => {
    if (reportState !== 'result') return;
    // 가짜 history 엔트리 추가 → 뒤로가기 시 popstate 발생
    window.history.pushState({ simResult: true }, '');
    const handlePopState = () => {
      setReportState('idle');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [reportState, setReportState]);

  const toggleDong = useCallback((dong: string) => {
    setSelectedDongs((prev) => {
      if (prev.includes(dong)) {
        if (prev.length <= 1) return prev; // 최소 1개
        return prev.filter((d) => d !== dong);
      }
      return [...prev, dong];
    });
  }, []);

  const toggleAllDongs = useCallback(() => {
    const all = DONG_DATA[selectedGu];
    if (selectedDongs.length === all.length) {
      setSelectedDongs([all[0]]); // 전체 해제 시 첫 번째만 유지
    } else {
      setSelectedDongs([...all]);
    }
  }, [selectedGu, selectedDongs]);

  const runSim = useCallback(async () => {
    setReportState('loading');
    try {
      // [C1 연동] 백엔드 SimulationInput 9개 필드 전부 전송
      // business_type: UI 한글 라벨 → _SALES_CODE_MAP 키로 변환
      // brand_name: 로그인 유저의 company_name 사용
      // TODO(existing_stores): 매장 관리 UI 추가 시 실제 데이터 연동 (현재는 빈 배열)
      const payload = {
        business_type: BUSINESS_TYPE_BACKEND_KEY[businessType] || businessType,
        brand_name: user?.company_name || '',
        target_district: selectedDongs[0] || '서교동',
        existing_stores: [],
        initial_investment: initialCapital * 10000, // 만원 → 원
        monthly_rent: budget * 10000, // 만원 → 원
        simulation_months: 12,
        scenarios: [],
        // 신규 7 필드
        store_area: storeArea,
        target_price_range: targetPrice,
        operating_hours: operatingHours,
        initial_capital: initialCapital * 10000,
        commercial_radius: radius,
        population_weight: weighted,
      };

      // [IM3-205] fetch를 simulationStore로 위임 — 페이지 이동해도 fetch가 끊기지 않음
      // [찬영 요청] /simulate 하나만 호출 (이전에는 /analyze와 중복 호출)
      // /simulate 응답에 market_report 포함됨 (backend main.py:308)
      await useSimulationStore.getState().startSimulation(payload);
      const storeState = useSimulationStore.getState();
      if (storeState.status !== 'done' || !storeState.result) {
        throw new Error(storeState.error ?? 'Simulation failed');
      }
      const simRes = storeState.result;

      const mr = simRes.market_report;
      const topComp = simRes.comparison?.[0];
      const topRisk = simRes.legal_risks?.[0];

      setSimResult({
        score: topComp?.score ?? 87,
        revenue: topComp?.revenue ?? 3240,
        riskLevel: topRisk?.risk_level ?? 'LOW',
        recommendation: simRes.ai_recommendation || '',
        chartData: mr
          ? [
              { label: '유동인구', value: mr.floating_population },
              { label: '임대료', value: mr.rent_index },
              { label: '경쟁강도', value: mr.competition_intensity },
              { label: '매출추정', value: mr.estimated_revenue },
              {
                label: '폐업률',
                value:
                  mr.closure_rate != null
                    ? Math.round(mr.closure_rate * 100)
                    : 100 - mr.survival_rate,
              },
              { label: '성장성', value: mr.growth_potential },
              { label: '접근성', value: mr.accessibility },
            ]
          : CHART_DATA,
        // 분기별 매출 예측 (TCN 모델 출력, 없으면 빈 배열) — B2
        quarterlyProjection: simRes.quarterly_projection ?? [],
        // TCN SHAP 분석 결과 (없으면 null) — B2
        shapResult: simRes.shap_result ?? null,
        // [C1 응답 필드 반영] v12.6 — 백엔드가 주는데 UI가 안 쓰던 5 영역 저장
        marketReport: mr,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        districtRankings: (simRes as any).district_rankings,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        winnerDistrict: (simRes as any).winner_district,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        topCandidates: (simRes as any).top_3_candidates,
        legalRisks: simRes.legal_risks,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        overallLegalRisk: (simRes as any).overall_legal_risk,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        vacancyApplied: (simRes as any).vacancy_applied,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        vacancySpots: (simRes as any).vacancy_spots ?? [],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        analysis_metrics: (simRes as any).analysis_metrics,
        // [B2 시나리오] 낙관/기본/비관 분기 매출 시나리오 — C1 UI 연동용
        scenarios: simRes.scenarios ?? null,
        // [B2 수지니] 폐업 위험도
        closureRisk: simRes.closure_risk ?? null,
        // [PR #72] 경쟁 매장 인텔리전스
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        competitorIntel: (simRes as any).competitor_intel ?? null,
        // [PR #71] 트렌드 전망
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        trendForecast: (simRes as any).trend_forecast ?? null,
        // [PR #75] 인구통계 심층 분석
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        demographicReport: (simRes as any).demographic_report ?? null,
      });
      setReportState('result');
    } catch (err) {
      console.error('Simulation failed:', err);
      // Fallback — Smart Mock (동/업종 기반 동적 데이터)
      const mock = generateSmartMock(selectedDongs[0] || '연남동', businessType);
      setSimResult({
        score: mock.score,
        revenue: mock.revenue,
        riskLevel: mock.riskLevel,
        recommendation: mock.recommendation,
        chartData: mock.chartData,
        // mock fallback 시 분기 데이터 없음
        quarterlyProjection: [],
        // mock fallback 시 SHAP 데이터 없음
        shapResult: null,
      });
      setReportState('result');
    }
  }, [
    setReportState,
    selectedDongs,
    budget,
    businessType,
    user?.company_name,
    storeArea,
    targetPrice,
    operatingHours,
    initialCapital,
    radius,
    weighted,
  ]);

  // [IM3-205] 로딩 진행률을 simulationStore에서 미러 — store가 500ms 타이머 보유
  // 기존 로컬 타이머 useEffect는 store로 이관됨
  const _storeProgress = useSimulationStore((s) => s.progress);
  const _storeStage = useSimulationStore((s) => s.stage);
  useEffect(() => {
    setLoadingProgress(_storeProgress);
    if (_storeStage) setLoadingText(`${_storeStage}...`);
  }, [_storeProgress, _storeStage]);

  // Dark theme only
  const textPrimary = 'text-[#e2e8f0]';
  const textSecondary = 'text-[#9ca3af]';
  const accent = 'text-[#818cf8]';
  const accentBg = 'bg-[#818cf8]';
  const panel = 'bg-[#2c2825] border-[#3a3633] shadow-2xl';

  return (
    <div
      ref={dashboardRef}
      className="relative z-10 h-full w-full bg-[#1e1b18] overflow-y-auto custom-scrollbar"
    >
      {/* Top bar */}
      <div className="sticky top-0 z-30 flex items-center px-8 py-4 mt-14 bg-[#1e1b18]/80 backdrop-blur-xl">
        <span className={`text-xs font-medium tracking-wider ${textSecondary}`}>
          마포구 시뮬레이터
        </span>
      </div>

      {/* Dashboard body */}
      <div className="flex flex-col lg:flex-row gap-6 p-8 max-w-7xl mx-auto">
        {/* Left panel — Controls (result 상태일 땐 숨김 → 우측 리포트가 full-width로 확장) */}
        <div
          className={`lg:w-[380px] shrink-0 rounded-2xl border p-6 transition-all duration-700 ${panel} ${reportState === 'result' ? 'hidden' : ''}`}
        >
          <h3
            className={`flex items-center gap-2 text-sm font-bold tracking-wider mb-6 ${textPrimary}`}
          >
            <Sliders size={16} className={accent} />
            SIMULATION CONTROLS
          </h3>

          {/* ─────────── BASIC: 분석 대상 (지역) ─────────── */}
          <div className="mb-5">
            <div className="flex items-center gap-2 mb-2">
              <MapPin size={13} className={accent} />
              <label className={`text-xs font-medium ${textSecondary}`}>분석 대상</label>
            </div>

            {/* 구 — 고정 (explore에서 선택된 구, 변경 불가) */}
            <div className="mb-2 px-3 py-2.5 rounded-lg border border-[#3a3633] bg-[#1e1b18]/50 flex items-center justify-between">
              <span className="text-sm text-[#e2e8f0]">{selectedGu}</span>
              <span className="text-[10px] text-[#9ca3af] uppercase tracking-wider opacity-70">
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
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-[#3a3633] bg-[#1e1b18] text-sm text-[#e2e8f0] hover:border-[#818cf8]/50 transition-colors"
              >
                <span className="truncate">
                  {selectedDongs.length === DONG_DATA[selectedGu].length
                    ? `전체 ${selectedDongs.length}개 동`
                    : `${selectedDongs.length}개 동 선택됨`}
                </span>
                <ChevronRight
                  size={14}
                  className={`text-[#9ca3af] transition-transform duration-200 shrink-0 ${
                    dongDropdownOpen ? 'rotate-90' : ''
                  }`}
                />
              </button>
              {dongDropdownOpen && (
                <div className="absolute z-50 mt-1 w-full max-h-52 overflow-y-auto rounded-lg border border-[#3a3633] bg-[#2c2825] shadow-2xl custom-scrollbar">
                  <button
                    onClick={toggleAllDongs}
                    className="w-full text-left px-3 py-2 text-xs font-medium border-b border-[#3a3633] transition-colors text-[#818cf8] hover:bg-[#818cf8]/10"
                  >
                    {selectedDongs.length === DONG_DATA[selectedGu].length
                      ? '전체 해제'
                      : '전체 선택'}
                  </button>
                  {DONG_DATA[selectedGu].map((dong) => {
                    const checked = selectedDongs.includes(dong);
                    return (
                      <button
                        key={dong}
                        onClick={() => toggleDong(dong)}
                        className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                          checked
                            ? 'text-[#e2e8f0] hover:bg-[#3a3633]'
                            : 'text-[#666666] hover:bg-[#3a3633] hover:text-[#9ca3af]'
                        }`}
                      >
                        <div
                          className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                            checked
                              ? 'bg-[#818cf8] border-[#818cf8]'
                              : 'border-[#3a3633] bg-transparent'
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

          {/* ─────────── BASIC: 업종 ─────────── */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-2">
              <Store size={13} className={accent} />
              <label className={`text-xs font-medium ${textSecondary}`}>업종</label>
            </div>
            <div className="relative">
              <button
                onClick={() => {
                  setBusinessTypeOpen(!businessTypeOpen);
                  setDongDropdownOpen(false);
                }}
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-[#3a3633] bg-[#1e1b18] text-sm text-[#e2e8f0] hover:border-[#818cf8]/50 transition-colors"
              >
                <span>{businessType}</span>
                <ChevronRight
                  size={14}
                  className={`text-[#9ca3af] transition-transform duration-200 ${
                    businessTypeOpen ? 'rotate-90' : ''
                  }`}
                />
              </button>
              {businessTypeOpen && (
                <div className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto rounded-lg border border-[#3a3633] bg-[#2c2825] shadow-2xl custom-scrollbar">
                  {BUSINESS_TYPES.map((type) => (
                    <button
                      key={type}
                      onClick={() => {
                        setBusinessType(type);
                        setBusinessTypeOpen(false);
                      }}
                      className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                        type === businessType
                          ? 'text-[#818cf8] bg-[#818cf8]/10'
                          : 'text-[#9ca3af] hover:text-[#e2e8f0] hover:bg-[#3a3633]'
                      }`}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ─────────── 분석 조건 (Hybrid Slider + Input) ─────────── */}
          <div className="pt-5 border-t border-[#3a3633]">
            <HybridSliderInput
              label="상권 반경"
              value={radius}
              onChange={setRadius}
              min={100}
              max={1500}
              step={50}
              unit="m"
              infoText="분석 대상 반경. 카페는 300~500m, 음식점은 500~1000m 권장"
            />

            <HybridSliderInput
              label="임대료 예산"
              value={budget}
              onChange={setBudget}
              min={50}
              max={1000}
              step={10}
              unit="만원"
              infoText="월 임대료 예산. 마포구 평균 1층 기준 200~400만원"
            />

            {/* Toggle switch */}
            <div className="mb-2">
              <div className="flex items-center justify-between">
                <label className={`text-xs font-medium ${textSecondary} flex items-center gap-1`}>
                  유동인구 가중치
                  <span
                    className="text-[#818cf8] cursor-help"
                    title="ON: KT 통신 유동인구 데이터를 매출 예측에 반영. 카페/음식점은 ON 권장"
                  >
                    &#9432;
                  </span>
                </label>
                <button
                  onClick={() => setWeighted(!weighted)}
                  className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${
                    weighted ? accentBg : 'bg-[#3a3633]'
                  }`}
                >
                  <div
                    className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${
                      weighted ? 'translate-x-[22px]' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>

          {/* ─────────── ADVANCED 토글 ─────────── */}
          <div className="mt-5 pt-5 border-t border-[#3a3633]">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-dashed border-[#3a3633] bg-transparent hover:bg-[#1e1b18] hover:border-[#818cf8]/40 transition-colors group"
            >
              <span className="flex items-center gap-2">
                <Settings
                  size={13}
                  className="text-[#9ca3af] group-hover:text-[#818cf8] transition-colors"
                />
                <span
                  className={`text-xs font-medium ${textSecondary} group-hover:text-[#e2e8f0] transition-colors`}
                >
                  더 정확한 분석을 원하시나요?
                </span>
              </span>
              <ChevronDown
                size={14}
                className={`text-[#9ca3af] transition-transform duration-300 ${
                  showAdvanced ? 'rotate-180' : ''
                }`}
              />
            </button>
            <p className={`text-[10px] mt-1.5 ${textSecondary} opacity-60 px-1`}>
              미입력 항목은 평균값으로 자동 추정됩니다
            </p>
          </div>

          {/* ─────────── ADVANCED 펼침 영역 ─────────── */}
          <div
            className={`overflow-hidden transition-all duration-500 ease-out ${
              showAdvanced ? 'max-h-[1200px] opacity-100 mt-5' : 'max-h-0 opacity-0 mt-0'
            }`}
          >
            <div className="p-4 rounded-xl border border-[#3a3633] bg-[#1e1b18]/50 space-y-6">
              {/* 1. 매장 면적 */}
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

              {/* 2. 목표 객단가 */}
              <div>
                <label className={`block text-xs font-medium mb-2 ${textSecondary}`}>
                  목표 객단가
                </label>
                <div className="grid grid-cols-2 gap-1.5">
                  {PRICE_RANGES.map((range) => {
                    const active = targetPrice === range.value;
                    return (
                      <button
                        key={range.value}
                        onClick={() => setTargetPrice(range.value)}
                        className={`px-2 py-2 rounded-lg text-[11px] font-medium border transition-all ${
                          active
                            ? 'bg-[#818cf8]/15 border-[#818cf8] text-[#818cf8]'
                            : 'bg-transparent border-[#3a3633] text-[#9ca3af] hover:border-[#818cf8]/50 hover:text-[#e2e8f0]'
                        }`}
                      >
                        {range.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 3. 운영 시간대 (멀티 선택) */}
              <div>
                <div className="flex items-baseline justify-between mb-2">
                  <label className={`text-xs font-medium ${textSecondary}`}>주 타겟 시간대</label>
                  <span className="text-[10px] text-[#9ca3af] opacity-60">복수 선택 가능</span>
                </div>
                <div className="grid grid-cols-4 gap-1.5">
                  {OPERATING_HOURS_OPTIONS.map((hour) => {
                    const active = operatingHours.includes(hour);
                    return (
                      <button
                        key={hour}
                        onClick={() => toggleOperatingHour(hour)}
                        className={`py-2 rounded-lg text-[11px] font-medium border transition-all ${
                          active
                            ? 'bg-[#818cf8]/15 border-[#818cf8] text-[#818cf8]'
                            : 'bg-transparent border-[#3a3633] text-[#9ca3af] hover:border-[#818cf8]/50 hover:text-[#e2e8f0]'
                        }`}
                      >
                        {hour}
                      </button>
                    );
                  })}
                </div>
              </div>

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

              <p
                className={`text-[10px] ${textSecondary} opacity-50 italic pt-2 border-t border-[#3a3633]/50`}
              >
                * 권리금/보증금 제외, 인테리어·초기 운영비 기준
              </p>
            </div>
          </div>

          {/* ─────────── RUN SIMULATION (맨 아래) ─────────── */}
          <button
            onClick={runSim}
            disabled={reportState === 'loading'}
            className={`w-full mt-6 py-3.5 rounded-xl font-bold text-sm tracking-wider flex items-center justify-center gap-2 transition-all duration-300 ${
              reportState === 'loading'
                ? 'opacity-50 cursor-not-allowed'
                : 'hover:scale-[1.02] active:scale-[0.98]'
            } bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:from-[#4f46e5] hover:to-[#6366f1]`}
          >
            <Play size={16} />
            RUN SIMULATION
          </button>
        </div>

        {/* Right panel — Visualization */}
        <div
          className={`flex-1 rounded-2xl border p-6 min-h-[500px] transition-all duration-700 ${panel}`}
        >
          {/* --- Idle State (Empty State with Blurred Silhouette) --- */}
          {reportState === 'idle' && (
            <div className="relative flex-1 flex flex-col items-center justify-center w-full h-full min-h-[600px] animate-in fade-in zoom-in-95 duration-500 bg-card/5 border border-border/50 rounded-2xl overflow-hidden">
              {/* 1. 배경: 블러 처리된 가짜(Mock) 대시보드 실루엣 */}
              <div className="absolute inset-0 w-full h-full p-8 opacity-20 blur-[8px] pointer-events-none flex flex-col gap-4">
                {/* 가짜 헤더 영역 */}
                <div className="h-10 w-1/3 bg-secondary rounded-lg mb-4" />
                {/* 가짜 4 KPI 카드 */}
                <div className="grid grid-cols-4 gap-4">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-24 bg-card border border-border rounded-xl" />
                  ))}
                </div>
                {/* 가짜 메인 바디 */}
                <div className="flex flex-1 gap-4 mt-2">
                  <div className="flex-[2] flex flex-col gap-4">
                    <div className="flex-1 bg-card border border-border rounded-xl" />
                    <div className="flex-1 bg-card border border-border rounded-xl" />
                  </div>
                  <div className="flex-[1] bg-card border border-border rounded-xl" />
                </div>
              </div>

              {/* 2. 중앙 CTA (Call to Action) 가이드 박스 */}
              <div className="relative z-10 flex flex-col items-center max-w-md text-center bg-card/80 backdrop-blur-xl border border-border/50 p-10 rounded-3xl shadow-2xl">
                <div className="w-16 h-16 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(99,102,241,0.2)]">
                  <MapPin className="w-8 h-8 text-primary animate-bounce" />
                </div>

                <h2 className="text-2xl font-black text-foreground mb-3 tracking-tight">
                  첫 번째 시뮬레이션을 시작하세요
                </h2>

                <p className="text-sm text-muted-foreground leading-relaxed mb-8">
                  좌측 패널에서 분석을 원하는 <strong className="text-primary">행정동</strong>과{' '}
                  <strong className="text-primary">업종</strong>을 선택한 후,
                  <br />
                  하단의 RUN 버튼을 눌러 AI 예측 엔진을 가동하십시오.
                </p>

                {/* 좌측 패널을 가리키는 시각적 힌트 */}
                <div className="flex items-center gap-3 text-xs font-mono text-muted-foreground bg-background px-4 py-2 rounded-full border border-border">
                  <span className="flex items-center gap-1 text-primary">
                    <ChevronLeft className="w-4 h-4 animate-pulse" />
                    SELECT PARAMETERS
                  </span>
                  <span className="w-1 h-1 bg-border rounded-full" />
                  <span>PRESS RUN</span>
                </div>
              </div>
            </div>
          )}

          {reportState === 'loading' && (
            <div className="h-full flex flex-col items-center justify-center">
              <div className="relative w-24 h-24 mb-8">
                {/* Double spinner */}
                <div className="absolute inset-0 border-4 border-[#3a3633] border-t-[#818cf8] rounded-full animate-[spin_2s_linear_infinite]" />
                <div className="absolute inset-2 border-4 border-[#3a3633] border-b-[#818cf8] rounded-full animate-[spin_3s_linear_infinite_reverse]" />
                {/* Center percentage */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-lg font-black font-mono text-[#818cf8]">
                    {Math.round(loadingProgress)}%
                  </span>
                </div>
              </div>

              <div className="flex flex-col items-center gap-4 w-full max-w-md">
                <p className={`font-mono text-xl font-black tracking-[0.2em] uppercase ${accent}`}>
                  PROCESSING DATA
                </p>

                {/* Progress Bar */}
                <div className="w-full relative">
                  <div className="w-full h-2 bg-[#1e1b18] rounded-full overflow-hidden border border-[#3a3633]">
                    <div
                      className="h-full bg-gradient-to-r from-[#6366f1] to-[#818cf8] rounded-full transition-all duration-500 ease-out"
                      style={{ width: `${loadingProgress}%` }}
                    />
                  </div>
                  <div className="flex justify-between mt-1.5">
                    <span className="text-[9px] font-mono text-[#818cf8]">
                      {Math.round(loadingProgress)}%
                    </span>
                    <span className="text-[9px] font-mono text-[#9ca3af]">
                      ~{Math.max(0, Math.round((90 - loadingProgress) / 0.9))}초 남음
                    </span>
                  </div>
                </div>

                {/* Current step */}
                <div className="px-4 py-2 bg-black/10 rounded-md border border-[#3a3633]/30 backdrop-blur-sm flex items-center gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                  <p className={`font-mono text-xs tracking-widest ${textSecondary}`}>
                    [ {loadingText} ]
                  </p>
                </div>
              </div>
            </div>
          )}

          {reportState === 'result' && (
            <div className="absolute inset-0 z-40 bg-[#1e1b18] text-[#e2e8f0] font-sans p-4 md:p-6 pt-24 md:pt-28 overflow-y-auto custom-scrollbar flex flex-col animate-[fadeSlideIn_0.8s_ease-out]">
              <div className="max-w-[1920px] w-full mx-auto flex flex-col gap-4 xl:px-10 2xl:px-16 transition-all duration-500 pb-12">
                {/* Header & Nav */}
                <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-4 shrink-0">
                  <div>
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <Zap className="w-5 h-5 text-indigo-400" />
                      <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">
                        상권 분석 리포트
                      </h1>
                      {simResult?.winnerDistrict && (
                        <span className="ml-2 px-2.5 py-0.5 bg-[#818cf8]/10 border border-[#818cf8]/40 rounded-full text-[10px] font-bold text-[#818cf8] uppercase tracking-wider">
                          AI 추천 1위 · {simResult.winnerDistrict}
                        </span>
                      )}
                      {simResult?.vacancyApplied === false && (
                        <span
                          className="ml-2 px-2.5 py-0.5 bg-amber-500/10 border border-amber-500/40 rounded-full text-[10px] font-bold text-amber-400 uppercase tracking-wider"
                          title="공실 DB 로드 실패 — 랭킹에 공실 페널티 미반영"
                        >
                          공실 미반영
                        </span>
                      )}
                    </div>
                    <p className="text-[#9ca3af] text-sm">
                      서울특별시 마포구 {selectedDongs[0] || '연남동'} 일대 시뮬레이션 결과
                      {simResult?.topCandidates && simResult.topCandidates.length > 0 && (
                        <span className="ml-2 text-[#6b7280]">
                          · Top 3: {simResult.topCandidates.join(', ')}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {!isSplitMode && (
                      <div className="flex bg-[#1e1b18] rounded-lg border border-[#3a3633] p-1 shadow-inner">
                        <button
                          onClick={() => setDashboardMode('data')}
                          className={`flex items-center gap-2 px-3 py-1.5 text-[11px] font-bold rounded-md transition-all duration-300 ${
                            dashboardMode === 'data'
                              ? 'bg-[#3a3633] text-[#818cf8] shadow-sm'
                              : 'text-[#9ca3af] hover:text-white'
                          }`}
                        >
                          <BarChartBig className="w-3.5 h-3.5" />
                          데이터 뷰
                        </button>
                        <button
                          onClick={() => setDashboardMode('map')}
                          className={`flex items-center gap-2 px-3 py-1.5 text-[11px] font-bold rounded-md transition-all duration-300 ${
                            dashboardMode === 'map'
                              ? 'bg-[#3a3633] text-[#818cf8] shadow-sm'
                              : 'text-[#9ca3af] hover:text-white'
                          }`}
                        >
                          <MapIcon className="w-3.5 h-3.5" />
                          AI 에이전트 맵
                        </button>
                      </div>
                    )}
                    <button
                      onClick={() => setIsSplitMode(!isSplitMode)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-bold transition-all duration-300 border ${
                        isSplitMode
                          ? 'bg-amber-500 text-black border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.4)]'
                          : 'bg-[#2c2825] text-[#9ca3af] border-[#3a3633] hover:text-white hover:bg-[#3a3633]'
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
                      className="flex items-center gap-2 px-3 py-1.5 border border-[#3a3633] bg-[#2c2825] hover:bg-[#3a3633] rounded-md text-xs font-medium transition-colors"
                    >
                      <Calendar className="w-3.5 h-3.5 text-[#9ca3af]" /> {reportMonthLabel}
                    </button>
                    <div className="relative">
                      <button
                        onClick={() => setIsDownloadOpen(!isDownloadOpen)}
                        disabled={isGeneratingPDF || isGeneratingExcel}
                        className="flex items-center gap-2 px-3 py-2 bg-transparent border border-indigo-500/60 text-indigo-400 hover:bg-indigo-500/10 hover:border-indigo-500 rounded-lg text-[11px] font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                          <div className="absolute right-0 mt-2 w-48 bg-[#1e1b18] border border-[#3a3633] rounded-lg shadow-2xl py-1.5 z-50 flex flex-col gap-0.5">
                            <button
                              onClick={handleDownloadPDF}
                              className="w-full text-left px-3 py-2 text-xs text-white hover:bg-[#2c2825] flex items-center gap-2 transition-colors group"
                            >
                              <FileText className="w-3.5 h-3.5 text-indigo-400 group-hover:scale-110 transition-transform" />{' '}
                              PDF 리포트{' '}
                              <span className="text-[10px] text-[#9ca3af] ml-auto">보고용</span>
                            </button>
                            <button
                              onClick={handleDownloadExcel}
                              className="w-full text-left px-3 py-2 text-xs text-[#9ca3af] hover:text-white hover:bg-[#2c2825] flex items-center gap-2 transition-colors group"
                            >
                              <Database className="w-3.5 h-3.5 text-indigo-400 group-hover:scale-110 transition-transform" />{' '}
                              Raw Data{' '}
                              <span className="text-[10px] text-[#d1d5db] ml-auto">XLSX</span>
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
                      'text-amber-500',
                      'text-emerald-500',
                      'text-sky-500',
                      'text-rose-500',
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
                          />
                        ))}
                      </div>
                    );
                  })()}

                {/* Single Mode: 기존 대시보드 */}
                {!isSplitMode && (
                  <>
                    {/* [C1 신규] AI Verdict 신호등 배너 — signal + 한 줄 판단 */}
                    {(() => {
                      const rec = simResult?.recommendation;
                      const legalRisk = simResult?.overallLegalRisk;
                      const ciSignal = simResult?.competitorIntel?.market_entry_signal;
                      // signal 없고 recommendation도 없으면 렌더 안 함
                      if (!rec && !legalRisk && !ciSignal) return null;

                      // signal: competitor_intel 우선, 없으면 overall_legal_risk 매핑
                      let signal: 'green' | 'yellow' | 'red' = 'yellow';
                      if (ciSignal === 'green' || ciSignal === 'yellow' || ciSignal === 'red') {
                        signal = ciSignal;
                      } else if (legalRisk === 'safe') signal = 'green';
                      else if (legalRisk === 'danger') signal = 'red';
                      else if (legalRisk === 'caution') signal = 'yellow';

                      const sigCfg = {
                        green: {
                          emoji: '🟢',
                          label: 'GREEN',
                          bg: 'bg-emerald-500/10',
                          border: 'border-emerald-500/30',
                          badge: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40',
                          iconBg: 'bg-emerald-500/10 ring-1 ring-emerald-500/30',
                        },
                        yellow: {
                          emoji: '🟡',
                          label: 'YELLOW',
                          bg: 'bg-amber-500/10',
                          border: 'border-amber-500/30',
                          badge: 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40',
                          iconBg: 'bg-amber-500/10 ring-1 ring-amber-500/30',
                        },
                        red: {
                          emoji: '🔴',
                          label: 'RED',
                          bg: 'bg-rose-500/10',
                          border: 'border-rose-500/30',
                          badge: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40',
                          iconBg: 'bg-rose-500/10 ring-1 ring-rose-500/30',
                        },
                      }[signal];

                      // headline: rec의 첫 문장 or 첫 60자 + '…'
                      let oneLiner = '';
                      if (rec) {
                        const firstSentence = rec.match(/^(.+?[.!?。])\s/);
                        if (firstSentence && firstSentence[1].length <= 80) {
                          oneLiner = firstSentence[1].trim();
                        } else {
                          oneLiner = rec.length > 60 ? rec.slice(0, 60).trim() + '…' : rec;
                        }
                      }

                      return (
                        <div
                          className={`mb-2 overflow-hidden rounded-2xl border ${sigCfg.border} bg-gradient-to-br from-slate-900/95 to-slate-800/70 p-6 shadow-2xl ring-1 ring-slate-700/50`}
                        >
                          <div className="flex items-start gap-4">
                            <div
                              className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl ${sigCfg.iconBg} text-3xl`}
                            >
                              {sigCfg.emoji}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
                                  AI VERDICT
                                </h3>
                                <span
                                  className={`rounded-full px-2 py-0.5 text-xs font-bold ${sigCfg.badge}`}
                                >
                                  {sigCfg.label}
                                </span>
                              </div>
                              {oneLiner && (
                                <p className="mt-2 text-base font-semibold leading-snug text-slate-100">
                                  {oneLiner}
                                </p>
                              )}
                              {rec && rec !== oneLiner && (
                                <p className="mt-2 text-sm leading-relaxed text-slate-300">{rec}</p>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })()}

                    <AIVerdictBanner
                      headline={
                        simResult?.recommendation ||
                        '강력한 입지 독점력과 2030 타겟팅을 통한 고수익 확보 가능 상권'
                      }
                      severity="positive"
                      reason="AI 멀티에이전트(market·population·legal) 종합 분석 결과. 유동인구 밀집도 상위 12%, 인근 동종업계 평균 매출 대비 15% 초과 달성 예측."
                      isDirect={false}
                    />

                    {/* Main Dashboard Body — dashboardMode 토글 (data | map) */}
                    {dashboardMode === 'data' ? (
                      <div className="flex flex-col gap-4 h-full animate-in fade-in duration-500">
                        {/* 4 Stats Cards — data 뷰에서만 표시 */}
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
                          <StatCard
                            onClick={() => setActiveDrawer('revenue')}
                            title="예상 월 매출 (추정)"
                            value={`₩ ${((simResult?.revenue ?? 3240) * 10000).toLocaleString()}`}
                            trend="+12.5%"
                            trendUp={true}
                            icon={<BarChart3 />}
                            sparkline="M 0 20 Q 10 5, 20 15 T 40 10 T 60 25 T 80 5 T 100 0"
                          />
                          <StatCard
                            onClick={() => setActiveDrawer('attractiveness')}
                            title="상권 종합 매력도"
                            value={`${simResult?.score ?? 87} / 100`}
                            trend="+5.2 Pts"
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
                                  : '42,105 명'
                            }
                            trend={
                              popData?.change_pct !== undefined
                                ? `${popData.change_pct > 0 ? '+' : ''}${popData.change_pct}%`
                                : '-2.4%'
                            }
                            trendUp={popData?.change_pct ? popData.change_pct > 0 : false}
                            icon={<Users />}
                            sparkline="M 0 5 Q 15 10, 30 20 T 60 15 T 80 25 T 100 30"
                            subtitle={popData?.date ?? ''}
                          />
                          <StatCard
                            onClick={() => setActiveDrawer('cannibalization')}
                            title="카니발리제이션 위험"
                            value={`${simResult?.riskLevel ?? 'Low'} (12%)`}
                            trend="안전 권역"
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
                                  <p className="text-[11px] text-[#9ca3af]">
                                    {chartView === 'daily'
                                      ? '경쟁점 데이터 및 배후세대 동선 분석 기준'
                                      : 'AI 엔진을 통한 향후 1년간의 매출 예측값'}
                                  </p>
                                </div>
                                <div className="flex bg-[#1e1b18] rounded-md border border-[#3a3633] p-0.5">
                                  <button
                                    onClick={() => setChartView('daily')}
                                    className={`px-3 py-1 text-[10px] font-bold rounded transition-colors ${chartView === 'daily' ? 'bg-[#3a3633] text-indigo-400' : 'text-[#9ca3af] hover:text-white'}`}
                                  >
                                    24H 분석
                                  </button>
                                  <button
                                    onClick={() => setChartView('monthly')}
                                    className={`px-3 py-1 text-[10px] font-bold rounded transition-colors ${chartView === 'monthly' ? 'bg-[#3a3633] text-indigo-400' : 'text-[#9ca3af] hover:text-white'}`}
                                  >
                                    12M 예측
                                  </button>
                                </div>
                              </div>
                              <div
                                onClick={() => setActiveDrawer('traffic')}
                                className="flex-1 relative w-full cursor-pointer group/chart hover:bg-[#818cf8]/[0.03] rounded-lg transition-colors min-h-0"
                              >
                                <motion.div
                                  key={`chart-reveal-${chartView}`}
                                  initial={{ clipPath: 'inset(0 100% 0 0)' }}
                                  animate={{ clipPath: 'inset(0 0 0 0)' }}
                                  transition={{ duration: 1.4, ease: 'linear' }}
                                  className="w-full h-full"
                                >
                                  <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart
                                      data={
                                        chartView === 'daily' ? DAILY_CHART_DATA : monthlyChartData
                                      }
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
                                          <stop offset="0%" stopColor="#818cf8" stopOpacity={0.5} />
                                          <stop offset="100%" stopColor="#818cf8" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient
                                          id="rcTrafficGradient"
                                          x1="0"
                                          y1="0"
                                          x2="0"
                                          y2="1"
                                        >
                                          <stop offset="0%" stopColor="#9ca3af" stopOpacity={0.2} />
                                          <stop offset="100%" stopColor="#9ca3af" stopOpacity={0} />
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
                                  <h3 className="text-lg font-semibold mb-3">
                                    분기별 매출 예측 (TCN)
                                  </h3>
                                  <QuarterlyProjectionChart data={simResult.quarterlyProjection} />
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
                              const directionCfg: Record<string, { label: string; cls: string }> = {
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
                                <div className="mt-6 rounded-xl bg-slate-900/95 p-5 shadow-2xl ring-1 ring-slate-700/50">
                                  <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
                                      📈 향후 12개월 전망
                                    </h3>
                                    {confidence && (
                                      <span className="text-xs text-slate-400">
                                        신뢰도: {confidence}
                                      </span>
                                    )}
                                  </div>

                                  {(score != null || dirBadge) && (
                                    <div className="mt-3 flex items-baseline gap-3 flex-wrap">
                                      {score != null && (
                                        <>
                                          <span className="text-4xl font-bold text-slate-100">
                                            {Math.round(score)}
                                          </span>
                                          <span className="text-sm text-slate-400">/100</span>
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

                                  <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
                                    <div className="rounded-lg bg-slate-800/50 p-3">
                                      <div className="text-slate-400">업종 트렌드</div>
                                      <div className="mt-1 font-semibold text-slate-100">
                                        {industryDirLabel}
                                      </div>
                                    </div>
                                    <div className="rounded-lg bg-slate-800/50 p-3">
                                      <div className="text-slate-400">상권 분류</div>
                                      <div className="mt-1 font-semibold text-slate-100">
                                        {changeIxLabel ?? 'N/A'}
                                      </div>
                                    </div>
                                    <div className="rounded-lg bg-slate-800/50 p-3">
                                      <div className="text-slate-400">진행 방향</div>
                                      <div className="mt-1 font-semibold text-slate-100">
                                        {direction ?? 'N/A'}
                                      </div>
                                    </div>
                                  </div>

                                  {narrative && (
                                    <p className="mt-4 text-sm leading-relaxed text-slate-300">
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
                              const sigBadgeCfg: Record<string, { cls: string; label: string }> = {
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
                              return (
                                <div className="rounded-xl bg-slate-900/95 p-5 shadow-2xl ring-1 ring-slate-700/50">
                                  <div className="flex items-center justify-between flex-wrap gap-2">
                                    <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
                                      🎯 경쟁 + 잠식 분석
                                    </h3>
                                    {sigBadge && (
                                      <span
                                        className={`rounded-full px-3 py-1 text-xs font-bold uppercase ${sigBadge.cls}`}
                                      >
                                        {sigBadge.label}
                                      </span>
                                    )}
                                  </div>

                                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
                                    <div className="rounded-lg bg-slate-800/50 p-3">
                                      <div className="text-xs text-slate-400">500m 포화도</div>
                                      <div className="mt-1 text-lg font-semibold text-slate-100">
                                        {comp?.saturation_level ?? 'N/A'}
                                      </div>
                                      <div className="text-xs text-slate-500">
                                        {comp?.total_competitors ?? 0}개 매장
                                      </div>
                                    </div>
                                    <div className="rounded-lg bg-slate-800/50 p-3">
                                      <div className="text-xs text-slate-400">카니발 영향</div>
                                      <div className="mt-1 text-lg font-semibold text-rose-300">
                                        {cannImpactPct != null ? `${cannImpactPct}%` : 'N/A'}
                                      </div>
                                    </div>
                                    <div className="rounded-lg bg-slate-800/50 p-3">
                                      <div className="text-xs text-slate-400">프랜차이즈/독립</div>
                                      <div className="mt-1 text-lg font-semibold text-slate-100">
                                        {comp?.franchise_count ?? 0} /{' '}
                                        {comp?.independent_count ?? 0}
                                      </div>
                                    </div>
                                  </div>

                                  {diff && (
                                    <div className="mt-4 rounded-lg bg-cyan-500/10 p-3 ring-1 ring-cyan-500/30">
                                      <div className="text-xs uppercase tracking-wider text-cyan-400">
                                        차별화 포지션
                                      </div>
                                      <p className="mt-1 text-sm text-slate-100">{diff}</p>
                                    </div>
                                  )}

                                  {(opps.length > 0 || risks.length > 0) && (
                                    <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                                      {opps.length > 0 && (
                                        <div>
                                          <div className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                                            💡 기회
                                          </div>
                                          <ul className="mt-2 space-y-1">
                                            {opps.map((o, i) => (
                                              <li key={i} className="text-xs text-slate-300">
                                                • {o}
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                      {risks.length > 0 && (
                                        <div>
                                          <div className="text-xs font-semibold uppercase tracking-wider text-rose-400">
                                            ⚠️ 리스크
                                          </div>
                                          <ul className="mt-2 space-y-1">
                                            {risks.map((r, i) => (
                                              <li key={i} className="text-xs text-slate-300">
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
                                      <div className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                                        📋 추천 액션
                                      </div>
                                      <ul className="mt-2 space-y-1">
                                        {actions.map((a, i) => (
                                          <li key={i} className="text-xs text-slate-200">
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
                                    <p className="mt-4 text-xs leading-relaxed text-slate-400">
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
                                  <span className="hidden md:inline-block px-1.5 py-0.5 bg-[#3a3633] text-[#9ca3af] text-[9px] rounded uppercase font-mono">
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
                                      className={`px-3 py-1 text-[10px] font-bold rounded transition-colors ${tableView === 'cannibalization' ? 'bg-[#3a3633] text-indigo-400' : 'text-[#9ca3af] hover:text-white'}`}
                                    >
                                      가맹점 간섭도
                                    </button>
                                    <button
                                      onClick={() => handleTableViewChange('neighborhoods')}
                                      className={`px-3 py-1 text-[10px] font-bold rounded transition-colors ${tableView === 'neighborhoods' ? 'bg-[#3a3633] text-indigo-400' : 'text-[#9ca3af] hover:text-white'}`}
                                    >
                                      행정동 비교
                                    </button>
                                  </div>
                                </div>
                              </div>
                              <div>
                                <table className="w-full text-left border-collapse">
                                  <thead className="sticky top-0 bg-[#1e1b18]/90 backdrop-blur-sm z-10">
                                    <tr className="text-[11px] font-mono text-[#9ca3af] uppercase tracking-wider">
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
                              <div className="px-5 py-3 border-t border-[#3a3633] flex justify-between items-center text-[10px] font-mono text-[#9ca3af]">
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
                                <p className="text-[11px] text-indigo-400">
                                  에이전트 노드 분석 결과 통합 데이터
                                </p>
                              </div>
                              <div className="relative w-[180px] h-[180px] my-2">
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
                                const topSignals = (cr.top_signals ?? []).slice(0, 3);
                                const maxAbs = Math.max(
                                  ...topSignals.map((s) => Math.abs(s.contribution)),
                                  0.0001,
                                );
                                return (
                                  <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-xl flex flex-col gap-3">
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-2">
                                        <h2 className="text-sm font-bold text-white">
                                          폐업 위험도
                                        </h2>
                                        {cr.is_mock && (
                                          <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-slate-500/40 bg-slate-500/20 text-slate-300 uppercase tracking-wider">
                                            MOCK
                                          </span>
                                        )}
                                      </div>
                                      <span
                                        className={`inline-flex items-center gap-1 text-[9px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-full border ${levelConfig.badge}`}
                                      >
                                        <span
                                          className={`w-1.5 h-1.5 rounded-full ${levelConfig.bar}`}
                                        />
                                        {levelConfig.label}
                                      </span>
                                    </div>
                                    <div>
                                      <div className="flex items-baseline justify-between mb-1.5">
                                        <span className="text-[10px] text-[#9ca3af]">
                                          위험 점수
                                        </span>
                                        <span className="text-lg font-bold text-white font-mono">
                                          {pct}
                                          <span className="text-[11px] text-[#9ca3af] ml-0.5">
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
                                    {topSignals.length > 0 && (
                                      <div className="flex flex-col gap-1.5 pt-2 border-t border-[#3a3633]">
                                        <div className="text-[10px] text-[#9ca3af] mb-1">
                                          주요 기여 피처 Top {topSignals.length}
                                        </div>
                                        {topSignals.map((s, i) => {
                                          const abs = Math.abs(s.contribution);
                                          const w = Math.round((abs / maxAbs) * 100);
                                          const positive = s.contribution >= 0;
                                          return (
                                            <div
                                              key={i}
                                              className="flex items-center gap-2 text-[10px]"
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
                                                className={`w-12 text-right font-mono ${positive ? 'text-rose-300' : 'text-emerald-300'}`}
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
                                <div className="rounded-xl bg-slate-900/95 p-5 shadow-2xl ring-1 ring-slate-700/50">
                                  <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
                                      💳 핵심 소비층 분석
                                    </h3>
                                    {d.elderly_ratio != null && (
                                      <span className="text-xs text-slate-400">
                                        고령: {d.elderly_ratio.toFixed(1)}%
                                      </span>
                                    )}
                                  </div>

                                  {core && (core.age || core.gender) && (
                                    <div className="mt-3 rounded-lg bg-gradient-to-r from-cyan-500/10 to-transparent p-3">
                                      <div className="text-xs uppercase tracking-wider text-cyan-400">
                                        주 소비층
                                      </div>
                                      <div className="mt-1 flex items-baseline gap-2 flex-wrap">
                                        <span className="text-2xl font-bold text-slate-100">
                                          {core.age ? `${core.age}대` : ''}{' '}
                                          {genderKo(core.gender ?? '')}
                                        </span>
                                        {typeof core.share === 'number' && (
                                          <span className="text-sm text-slate-400">
                                            {(core.share * 100).toFixed(1)}% 매출 기여
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  )}

                                  {top3.length > 0 && (
                                    <div className="mt-4 space-y-2">
                                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                                        연령대 TOP 3
                                      </div>
                                      {top3.map((a) => (
                                        <div
                                          key={a.age_group}
                                          className="flex items-center gap-2 text-xs"
                                        >
                                          <span className="w-12 text-slate-300">
                                            {a.age_group}대
                                          </span>
                                          <div className="flex-1 rounded-full bg-slate-800/50">
                                            <div
                                              className="h-2 rounded-full bg-cyan-400"
                                              style={{
                                                width: `${Math.min(100, Math.max(0, a.share * 100))}%`,
                                              }}
                                            />
                                          </div>
                                          <span className="w-12 text-right text-slate-400">
                                            {(a.share * 100).toFixed(1)}%
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                                    <div className="rounded-lg bg-slate-800/50 p-2">
                                      <div className="text-slate-400">피크</div>
                                      <div className="mt-1 font-semibold text-slate-100">
                                        {peakHours[0] ?? 'N/A'}
                                      </div>
                                    </div>
                                    <div className="rounded-lg bg-slate-800/50 p-2">
                                      <div className="text-slate-400">평/주말</div>
                                      <div className="mt-1 font-semibold text-slate-100">
                                        {typeof d.weekday_weekend_ratio === 'number'
                                          ? d.weekday_weekend_ratio.toFixed(2)
                                          : 'N/A'}
                                      </div>
                                    </div>
                                    <div className="rounded-lg bg-slate-800/50 p-2">
                                      <div className="text-slate-400">소득</div>
                                      <div className="mt-1 font-semibold text-slate-100">
                                        {incomeLevelKo(d.area_income_level ?? 'unknown')}
                                      </div>
                                    </div>
                                  </div>

                                  {d.resident_visitor_ratio != null && (
                                    <div className="mt-3 text-xs text-slate-400">
                                      📍 외부 방문객 비율:{' '}
                                      {(d.resident_visitor_ratio * 100).toFixed(1)}%
                                    </div>
                                  )}

                                  {d.brand_target_match_score != null && (
                                    <div className="mt-3 rounded-lg bg-amber-500/10 p-3 ring-1 ring-amber-500/30">
                                      <div className="flex items-baseline gap-2 flex-wrap">
                                        <span className="text-xs uppercase tracking-wider text-amber-300">
                                          브랜드 타겟 매칭
                                        </span>
                                        <span className="text-lg font-bold text-amber-200">
                                          {d.brand_target_match_score.toFixed(0)}/100
                                        </span>
                                      </div>
                                      {d.match_rationale && (
                                        <p className="mt-1 text-xs text-slate-300">
                                          {d.match_rationale}
                                        </p>
                                      )}
                                    </div>
                                  )}

                                  {d.narrative && (
                                    <p className="mt-4 text-xs leading-relaxed text-slate-400">
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
                                <span className="font-mono text-[9px] uppercase tracking-widest text-[#818cf8] bg-[#818cf8]/10 border border-[#818cf8]/30 px-2 py-0.5 rounded-full">
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
                                    labor_law: '노동법',
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
                                    // 위험 항목 없으면 mock fallback 카드
                                    return (
                                      <InsightCard
                                        severity="critical"
                                        onClick={() => setActiveDrawer('insight_legal')}
                                        icon={<Scale className="w-4 h-4 text-rose-500" />}
                                        title="법률 리스크 경고 (Legal Node)"
                                        desc={
                                          simResult?.recommendation ||
                                          '상가임대차보호법 위반 사례 존재 권역. 최근 3년 평균 임대료 인상률이 5%를 초과하여 계약 갱신 시 법적 분쟁 리스크가 감지되었습니다.'
                                        }
                                      />
                                    );
                                  }

                                  const topSev = dangerRisks.some(
                                    (r) => severityOf(r.risk_level) === 'critical',
                                  )
                                    ? 'critical'
                                    : 'advisory';

                                  return (
                                    <div
                                      onClick={() => setActiveDrawer('insight_legal')}
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
                                            <span className="text-[8px] font-mono uppercase tracking-wider text-[#9ca3af]">
                                              {topSev === 'critical' ? 'CRITICAL' : 'ADVISORY'}
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
                                              className={`flex gap-2.5 pl-2.5 border-l-2 ${isCritical ? 'border-rose-500' : 'border-amber-400'}`}
                                            >
                                              <div className="flex flex-col gap-0.5 flex-1 min-w-0">
                                                <div className="flex items-center gap-1.5">
                                                  <span className="text-[#e2e8f0] text-[11px] font-semibold">
                                                    {TYPE_LABEL[risk.type] || risk.type}
                                                  </span>
                                                  <span
                                                    className={`text-[8px] font-mono px-1 py-0.5 rounded ${isCritical ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-400/20 text-amber-400'}`}
                                                  >
                                                    {isCritical ? '위험' : '주의'}
                                                  </span>
                                                </div>
                                                {risk.detail && (
                                                  <p className="text-[#9ca3af] text-[10px] leading-relaxed">
                                                    {risk.detail}
                                                  </p>
                                                )}
                                                {risk.articles && risk.articles.length > 0 && (
                                                  <details
                                                    className="mt-1"
                                                    onClick={(e) => e.stopPropagation()}
                                                  >
                                                    <summary className="cursor-pointer text-[10px] text-cyan-300 hover:text-cyan-200 font-mono">
                                                      근거 조항 {risk.articles.length}건 보기
                                                    </summary>
                                                    <ul className="mt-1.5 space-y-1.5 text-[10px]">
                                                      {risk.articles.map((a, ai) => (
                                                        <li
                                                          key={ai}
                                                          className="rounded border border-[#3a3633] bg-[#171717]/60 p-2"
                                                        >
                                                          <div className="font-semibold text-[#e2e8f0]">
                                                            {a.article_ref}
                                                          </div>
                                                          <div className="mt-1 text-[#9ca3af] leading-relaxed whitespace-pre-wrap">
                                                            {a.content}
                                                          </div>
                                                        </li>
                                                      ))}
                                                    </ul>
                                                  </details>
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
                                    <span className="text-[10px] font-mono text-[#818cf8]">
                                      LIVE
                                    </span>
                                  </div>
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
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
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ==========================================
          AI Agent Workflow Drawer
          ========================================== */}
      <>
        <div
          className={`fixed inset-0 z-[100] bg-[#050505]/70 backdrop-blur-sm transition-opacity duration-500 ${isWorkflowOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
          onClick={() => setIsWorkflowOpen(false)}
        />
        <div
          className={`fixed top-0 right-0 w-full md:w-[600px] h-full bg-[#1e1b18] border-l border-[#3a3633] z-[101] shadow-2xl flex flex-col transition-transform duration-[800ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${isWorkflowOpen ? 'translate-x-0' : 'translate-x-full'}`}
        >
          <div className="flex justify-between items-center p-6 border-b border-[#3a3633] bg-[#2c2825]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#818cf8]/10 border border-[#818cf8]/20 flex items-center justify-center">
                <Terminal className="w-4 h-4 text-[#818cf8]" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight">
                  LangGraph Execution Log
                </h2>
                <p className="text-[10px] text-[#a3a3a3] font-mono mt-0.5">MULTI-AGENT PIPELINE</p>
              </div>
            </div>
            <button
              onClick={() => setIsWorkflowOpen(false)}
              className="p-2 text-[#a3a3a3] hover:text-white hover:bg-[#3a3633] rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-6 bg-[#171717] custom-scrollbar">
            <SpotterAgentWorkflow />
          </div>
        </div>
      </>

      {/* [v8.0] Drill-down Drawer — KPI/차트 클릭 시 우측에서 슬라이드 인 */}
      <DetailDrawer
        isOpen={!!activeDrawer}
        onClose={() => setActiveDrawer(null)}
        drawerKey={activeDrawer}
        popData={popData}
        analysisMetrics={simResult?.analysis_metrics}
      />

      {/* [v12.0] Hidden A4 PDF Template — html2canvas 캡처용 (화면 밖) */}
      <HiddenPDFTemplate
        ref={pdfTemplateRef}
        districtFull={`마포구 ${selectedDongs[0] || '연남동'}`}
        stats={[
          {
            title: '예상 월 매출 (추정)',
            value: `₩ ${((simResult?.revenue ?? 3240) * 10000).toLocaleString()}`,
            trend: '+12.5%',
          },
          {
            title: '상권 종합 매력도',
            value: `${simResult?.score ?? 87} / 100`,
            trend: '+5.2 Pts',
          },
          {
            title: '일일 유동인구',
            value: popData?.daily_average
              ? `${popData.daily_average.toLocaleString()} 명`
              : '42,105 명',
            trend: popData?.date ?? '-2.4%',
          },
          {
            title: '카니발리제이션 위험',
            value: `${simResult?.riskLevel ?? 'Low'} (12%)`,
            trend: '안전 권역',
          },
        ]}
        cannibalizationRows={sortedCannRows.length > 0 ? sortedCannRows : CANNIBALIZATION_ROWS}
        neighborhoodRows={
          sortedNeighborhoodRows.length > 0 ? sortedNeighborhoodRows : NEIGHBORHOOD_ROWS
        }
        insights={[
          {
            severity: 'advisory',
            title: '저녁 시간대 매출 집중형',
            desc: '18시 이후 유동인구가 급증. 야간 메뉴 강화를 권장합니다.',
          },
          {
            severity: 'critical',
            title: '법률 리스크 경고 (Legal Node)',
            desc:
              simResult?.recommendation ||
              '상가임대차보호법 위반 사례 존재 권역. 최근 3년 평균 임대료 인상률이 5%를 초과하여 계약 갱신 시 법적 분쟁 리스크가 감지되었습니다.',
          },
          {
            severity: 'opportunity',
            title: '2030 여성 타겟 구역',
            desc: 'SNS 친화적 인테리어 도입 시 수익 창출 확률 34% 증가.',
          },
        ]}
        reportDate={reportFullDate}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Dashboard Sub-Components (결과 대시보드 전용)
   ═══════════════════════════════════════════════════════
   - StatCard: 스파크라인 + 트렌드 표시 카드
   - TableRow: 상태 뱃지 포함 테이블 행
   - InsightCard: AI 인사이트 카드
   ※ SkyThemeToggle, GlobalLimelightNav는 글로벌 헤더 전용
*/

function LogoutButton() {
  const { isLoggedIn, logout } = useAuth();
  const nav = useTransition();

  if (!isLoggedIn) return null;

  return (
    <button
      onClick={() => {
        logout();
        nav('/login');
      }}
      className="hidden md:flex items-center gap-1.5 px-3 py-1.5 text-[#9ca3af] hover:text-rose-400 hover:bg-rose-500/10 rounded-full text-xs font-medium transition-colors border border-transparent hover:border-rose-500/30"
      title="로그아웃"
    >
      <LogOut className="w-3.5 h-3.5" />
      <span>로그아웃</span>
    </button>
  );
}

/**
 * Notification Mock Items — 도메인 특화 샘플 3종
 * (실제 API 연동 전 demo 용도. 승인 대기는 실 데이터로 별도 렌더)
 */
const NOTIFICATION_MOCK_ITEMS = [
  {
    id: 'mock-legal',
    type: 'critical' as const,
    iconType: 'legal' as const,
    title: '[권리금 경고] 연남동 B권역, 최근 3년 상가임대차 갱신 거절 분쟁 급증 (Legal Agent)',
    time: '1시간 전',
    action: '법률 리스크 상세 리포트는 준비 중입니다.',
  },
  {
    id: 'mock-cannibal',
    type: 'warning' as const,
    iconType: 'cannibal' as const,
    title: '[간섭도 주의] 서교동 신규 출점 시 기존 3호점(홍대점) 예상 매출 -18% 타격 감지',
    time: '2시간 전',
    action: '카니발리제이션 분석 대시보드는 준비 중입니다.',
  },
  {
    id: 'mock-sim',
    type: 'success' as const,
    iconType: 'sim' as const,
    title: '[분석 완료] 마포구 망원동 112-4 일대 시뮬레이션 완료 및 보관함 저장됨',
    time: '5시간 전',
    action: '보관함 파이프라인은 준비 중입니다.',
  },
];

function GlobalLimelightNav() {
  const nav = useTransition();
  const { isLoggedIn, user, logout } = useAuth();
  const { showToast } = useToast();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, opacity: 0 });
  const [openDropdown, setOpenDropdown] = useState<'bell' | 'user' | null>(null);
  const navRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // 매니저 목록 — Bell 빨간 점 + 드롭다운 알림 소스
  const { pending: pendingManagers } = useManagerList();
  const isMaster = isLoggedIn && user?.role !== 'manager';
  // 마스터만 mock 알림 노출 (매니저는 승인 대기 없음 + 도메인 알림 관련 없음)
  const mockItems = isMaster ? NOTIFICATION_MOCK_ITEMS : [];
  const totalUnread = pendingManagers.length + mockItems.length;

  type NavItemType = 'folder' | 'bell' | 'settings' | 'user';
  const navItems: {
    type: NavItemType;
    icon: React.ReactElement;
    label: string;
    hasNoti?: boolean;
  }[] = [
    { type: 'folder', icon: <Folder />, label: '출점 파이프라인' },
    { type: 'user', icon: <User />, label: '내 프로필' },
    { type: 'settings', icon: <Settings />, label: '내 정보 관리' },
    { type: 'bell', icon: <Bell />, label: '알림', hasNoti: totalUnread > 0 },
  ];

  const targetIndex = hoverIndex !== null ? hoverIndex : activeIndex;

  useEffect(() => {
    if (targetIndex !== null) {
      const el = navRefs.current[targetIndex];
      if (el) setIndicatorStyle({ left: el.offsetLeft + el.offsetWidth / 2, opacity: 1 });
    } else {
      setIndicatorStyle((prev) => ({ ...prev, opacity: 0 }));
    }
  }, [targetIndex]);

  const handleItemClick = (index: number, type: NavItemType) => {
    // 비로그인 시 로그인 페이지로
    if (!isLoggedIn) {
      nav('/login');
      return;
    }

    setActiveIndex(index);

    if (type === 'folder') {
      setOpenDropdown(null);
      nav('/hq?tab=pipeline');
    } else if (type === 'settings') {
      setOpenDropdown(null);
      nav('/hq?tab=mypage');
    } else if (type === 'bell') {
      setOpenDropdown(openDropdown === 'bell' ? null : 'bell');
    } else if (type === 'user') {
      setOpenDropdown(openDropdown === 'user' ? null : 'user');
    }
  };

  return (
    <div className="relative hidden md:flex">
      {/* 아이콘 바 — overflow-hidden으로 빔 클리핑 */}
      <div
        className="relative flex items-center bg-[#2c2825] border border-[#3a3633] rounded-full h-10 px-2 shadow-sm overflow-hidden"
        onMouseLeave={() => setHoverIndex(null)}
      >
        {/* 호버 조명 효과 */}
        <div
          className="absolute top-0 z-10 pointer-events-none flex flex-col items-center transition-all duration-300 ease-[cubic-bezier(0.25,1,0.5,1)]"
          style={{
            left: `${indicatorStyle.left}px`,
            transform: 'translateX(-50%)',
            opacity: indicatorStyle.opacity,
          }}
        >
          <div className="w-6 h-[2px] bg-[#818cf8] rounded-b-full shadow-[0_0_8px_#818cf8]" />
          <div
            className="w-12 h-10 bg-[#818cf8]/20"
            style={{ clipPath: 'polygon(25% 0%, 75% 0%, 100% 100%, 0% 100%)' }}
          />
        </div>

        {/* 아이콘 리스트 */}
        {navItems.map((item, index) => (
          <button
            key={index}
            ref={(el) => {
              navRefs.current[index] = el;
            }}
            onClick={() => handleItemClick(index, item.type)}
            onMouseEnter={() => setHoverIndex(index)}
            className="relative z-20 flex items-center justify-center h-full px-3 text-[#9ca3af] hover:text-[#e2e8f0] transition-colors group"
            title={item.label}
          >
            {React.cloneElement(item.icon, {
              className: `w-4 h-4 transition-all duration-300 ${
                targetIndex === index
                  ? 'text-[#818cf8] scale-110 drop-shadow-[0_0_5px_rgba(129,140,248,0.5)]'
                  : 'scale-100 group-hover:scale-110'
              }`,
            } as React.HTMLAttributes<HTMLElement>)}

            {item.hasNoti && (
              <span className="absolute top-2 right-2 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
              </span>
            )}
          </button>
        ))}
      </div>

      {/* 드롭다운 — overflow-hidden 바깥에서 렌더링 */}

      {/* 🔔 알림 드롭다운 (Bell) — 실 승인 대기 + 도메인 특화 mock 혼합 (v11.3) */}
      {openDropdown === 'bell' && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpenDropdown(null)} />
          <div className="absolute top-12 right-0 w-80 bg-[#1e1b18] border border-[#3a3633] rounded-xl shadow-2xl py-2 z-40 animate-in fade-in slide-in-from-top-2 duration-200">
            {/* Header */}
            <div className="px-4 py-3 border-b border-[#3a3633] flex justify-between items-center bg-[#2c2825]/50">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-[#e2e8f0]">최근 알림</span>
                {totalUnread > 0 && (
                  <span className="px-1.5 py-0.5 bg-rose-500/20 text-rose-500 text-[9px] font-black rounded-full">
                    {totalUnread}
                  </span>
                )}
              </div>
              <button
                onClick={() => {
                  showToast('info', '모든 알림을 읽음 처리했습니다.');
                  setOpenDropdown(null);
                }}
                className="text-[10px] text-[#818cf8] font-bold hover:text-[#6366f1] transition-colors"
              >
                모두 읽음
              </button>
            </div>

            {/* Notification List */}
            <div className="max-h-[320px] overflow-y-auto custom-scrollbar">
              {totalUnread === 0 ? (
                <div className="px-4 py-10 text-center">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto mb-2 opacity-60" />
                  <p className="text-[11px] text-[#9ca3af]">새 알림이 없습니다</p>
                </div>
              ) : (
                <>
                  {/* 실 데이터 — 매니저 승인 대기 */}
                  {pendingManagers.map((m) => (
                    <div
                      key={m.id}
                      onClick={() => {
                        setOpenDropdown(null);
                        nav('/hq?tab=team');
                      }}
                      className="px-4 py-3 hover:bg-[#2c2825] cursor-pointer transition-colors border-b border-[#3a3633] flex gap-3 group"
                    >
                      <div className="shrink-0 mt-0.5 p-1.5 rounded-lg border bg-rose-500/10 border-rose-500/20 group-hover:border-rose-500/40 transition-colors">
                        <ShieldAlert className="w-4 h-4 text-rose-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-[#e2e8f0] leading-snug group-hover:text-white transition-colors">
                          <strong className="font-bold text-white mr-1">[권한 승인]</strong>
                          새로운 매니저 워크스페이스 승인 대기 ({m.contact_name} 님)
                        </p>
                        <p className="text-[10px] text-[#9ca3af] mt-1.5 font-mono">
                          {formatRelativeTime(m.created_at)} · {m.email}
                        </p>
                      </div>
                      <div className="shrink-0 flex items-center justify-center w-2">
                        <div className="w-1.5 h-1.5 bg-[#818cf8] rounded-full" />
                      </div>
                    </div>
                  ))}

                  {/* Mock 3종 — 법률/카니발/완료 */}
                  {mockItems.map((item) => {
                    const tag = item.title.split(']')[0] + ']';
                    const body = item.title.split(']').slice(1).join(']').trim();
                    const bgCls =
                      item.type === 'critical'
                        ? 'bg-rose-500/10 border-rose-500/20 group-hover:border-rose-500/40'
                        : item.type === 'warning'
                          ? 'bg-amber-500/10 border-amber-500/20 group-hover:border-amber-500/40'
                          : 'bg-emerald-500/10 border-emerald-500/20 group-hover:border-emerald-500/40';
                    const Icon =
                      item.iconType === 'legal'
                        ? Scale
                        : item.iconType === 'cannibal'
                          ? AlertTriangle
                          : CheckCircle2;
                    const iconColor =
                      item.type === 'critical'
                        ? 'text-rose-500'
                        : item.type === 'warning'
                          ? 'text-amber-500'
                          : 'text-emerald-500';
                    return (
                      <div
                        key={item.id}
                        onClick={() => {
                          showToast('info', item.action);
                          setOpenDropdown(null);
                        }}
                        className="px-4 py-3 hover:bg-[#2c2825] cursor-pointer transition-colors border-b border-[#3a3633] last:border-b-0 flex gap-3 group"
                      >
                        <div
                          className={`shrink-0 mt-0.5 p-1.5 rounded-lg border transition-colors ${bgCls}`}
                        >
                          <Icon className={`w-4 h-4 ${iconColor}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-[#e2e8f0] leading-snug group-hover:text-white transition-colors">
                            <strong className="font-bold text-white mr-1">{tag}</strong>
                            {body}
                          </p>
                          <p className="text-[10px] text-[#9ca3af] mt-1.5 font-mono">{item.time}</p>
                        </div>
                        <div className="shrink-0 flex items-center justify-center w-2">
                          <div className="w-1.5 h-1.5 bg-[#818cf8] rounded-full" />
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </div>

            {/* Footer */}
            <div className="p-2 border-t border-[#3a3633]">
              <button
                onClick={() => {
                  showToast('info', '전체 알림 센터는 준비 중입니다.');
                  setOpenDropdown(null);
                }}
                className="w-full py-2 text-[10px] font-bold text-[#9ca3af] hover:text-white hover:bg-[#2c2825] rounded-lg transition-colors"
              >
                알림 센터 전체 보기
              </button>
            </div>
          </div>
        </>
      )}

      {/* 유저/워크스페이스 드롭다운 (User) */}
      {openDropdown === 'user' && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpenDropdown(null)} />
          <div className="absolute top-12 right-0 w-56 bg-[#1e1b18] border border-[#3a3633] rounded-xl shadow-2xl py-2 z-40">
            <div className="px-4 py-3 border-b border-[#3a3633]">
              <p className="text-xs font-black text-[#e2e8f0]">SPOTTER-HQ</p>
              <p className="text-[10px] text-[#9ca3af] mt-0.5">마스터 계정 (팀장)</p>
            </div>
            <div className="py-1">
              <button
                onClick={() => {
                  setOpenDropdown(null);
                  nav('/hq?tab=team');
                }}
                className="w-full text-left px-4 py-2 text-xs text-[#d1d5db] hover:text-[#e2e8f0] hover:bg-[#2c2825] transition-colors"
              >
                팀 및 권역 관리
              </button>
              <button
                onClick={() => {
                  setOpenDropdown(null);
                  nav('/hq?tab=billing');
                }}
                className="w-full text-left px-4 py-2 text-xs text-[#d1d5db] hover:text-[#e2e8f0] hover:bg-[#2c2825] transition-colors"
              >
                결제 및 토큰 사용량
              </button>
            </div>
            <div className="border-t border-[#3a3633] py-1 mt-1">
              <button
                onClick={() => {
                  setOpenDropdown(null);
                  logout();
                  nav('/login');
                }}
                className="w-full text-left px-4 py-2 text-xs text-rose-400 hover:bg-rose-500/10 transition-colors"
              >
                로그아웃
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   HiddenPDFTemplate (v12.0) — A4 프린트 최적화 라이트 템플릿
   화면에는 보이지 않고 (absolute top-[-9999px]) html2canvas 캡처 전용.
   각 페이지는 794x1123 고정 → jsPDF로 페이지별 변환.
   ═══════════════════════════════════════════════════════ */
interface HiddenPDFTemplateProps {
  districtFull: string;
  stats: { title: string; value: string; trend: string }[];
  cannibalizationRows: CannRow[];
  neighborhoodRows: NeighborhoodRow[];
  insights: { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[];
  reportDate: string;
}

// 인디고 SPOTTER 로고 SVG 경로 (Light 테마 버전 — #6366f1)
const SPOTTER_LOGO_PATHS = (
  <>
    <path
      d="M18.5147 0C15.4686 0 12.5473 1.21005 10.3934 3.36396L3.36396 10.3934C1.21005 12.5473 0 15.4686 0 18.5147C0 24.8579 5.14214 30 11.4853 30C14.5314 30 17.4527 28.7899 19.6066 26.636L24.4689 21.7737C24.469 21.7738 24.4689 21.7736 24.4689 21.7737L38.636 7.6066C39.6647 6.57791 41.0599 6 42.5147 6C44.9503 6 47.0152 7.58741 47.7311 9.78407L52.2022 5.31296C50.1625 2.11834 46.586 0 42.5147 0C39.4686 0 36.5473 1.21005 34.3934 3.36396L15.364 22.3934C14.3353 23.4221 12.9401 24 11.4853 24C8.45584 24 6 21.5442 6 18.5147C6 17.0599 6.57791 15.6647 7.6066 14.636L14.636 7.6066C15.6647 6.57791 17.0599 6 18.5147 6C20.9504 6 23.0152 7.58748 23.7311 9.78421L28.2023 5.31307C26.1626 2.1184 22.5861 0 18.5147 0Z"
      fill="#6366f1"
    />
    <path
      d="M39.364 22.3934C38.3353 23.4221 36.9401 24 35.4853 24C33.05 24 30.9853 22.413 30.2692 20.2167L25.7982 24.6877C27.838 27.8819 31.4143 30 35.4853 30C38.5314 30 41.4527 28.7899 43.6066 26.636L62.636 7.6066C63.6647 6.57791 65.0599 6 66.5147 6C69.5442 6 72 8.45584 72 11.4853C72 12.9401 71.4221 14.3353 70.3934 15.364L63.364 22.3934C62.3353 23.4221 60.9401 24 59.4853 24C57.0498 24 54.985 22.4127 54.269 20.2162L49.798 24.6873C51.8377 27.8818 55.4141 30 59.4853 30C62.5314 30 65.4527 28.7899 67.6066 26.636L74.636 19.6066C76.7899 17.4527 78 14.5314 78 11.4853C78 5.14214 72.8579 0 66.5147 0C63.4686 0 60.5473 1.21005 58.3934 3.36396L39.364 22.3934Z"
      fill="#6366f1"
    />
  </>
);

function PDFPageHeader({
  pageNumber,
  totalPages,
  districtFull,
}: {
  pageNumber: number;
  totalPages: number;
  districtFull: string;
}) {
  return (
    <div className="flex justify-between items-center border-b border-slate-200 pb-4">
      <div className="flex items-center gap-2.5">
        <svg width="36" height="14" viewBox="0 0 78 30" fill="none">
          {SPOTTER_LOGO_PATHS}
        </svg>
        <span className="text-[13px] font-black tracking-[0.18em] text-slate-900">SPOTTER</span>
        <span className="text-[10px] text-slate-400 ml-1">/ {districtFull} 상권 분석 리포트</span>
      </div>
      <span className="text-[10px] text-slate-400 font-mono tracking-wider">
        PAGE {pageNumber} / {totalPages}
      </span>
    </div>
  );
}

function PDFPageFooter({ reportDate }: { reportDate: string }) {
  return (
    <div className="text-[9px] text-slate-400 font-mono border-t border-slate-200 pt-3 flex justify-between tracking-wider">
      <span>© PROJECT SPOTTER · CONFIDENTIAL</span>
      <span>GENERATED {reportDate}</span>
    </div>
  );
}

const HiddenPDFTemplate = forwardRef<HTMLDivElement, HiddenPDFTemplateProps>(
  ({ districtFull, stats, cannibalizationRows, neighborhoodRows, insights, reportDate }, ref) => {
    const TOTAL_PAGES = 4;
    const pageClass = 'w-[794px] h-[1123px] p-12 bg-white text-slate-900 relative flex flex-col';
    const docId = `SPTR-${Date.now().toString().slice(-8)}`;

    const severityStyle = {
      critical: { dot: 'bg-rose-500', bg: 'bg-rose-50 border-rose-200' },
      advisory: { dot: 'bg-[#6366f1]', bg: 'bg-indigo-50 border-indigo-200' },
      opportunity: { dot: 'bg-emerald-500', bg: 'bg-emerald-50 border-emerald-200' },
    };

    return (
      <div
        ref={ref}
        className="absolute top-[-9999px] left-[-9999px] w-[794px] bg-white font-sans"
        style={{ fontFamily: 'Pretendard, sans-serif' }}
      >
        {/* ─────────── Page 1: Cover ─────────── */}
        <div className={pageClass}>
          <div className="flex-1 flex flex-col items-center justify-center">
            <svg width="200" height="78" viewBox="0 0 78 30" fill="none" className="mb-10">
              {SPOTTER_LOGO_PATHS}
            </svg>
            <p className="text-[#6366f1] font-mono text-[11px] tracking-[0.3em] border border-[#6366f1] px-5 py-1.5 rounded-full bg-indigo-50 mb-16">
              AI FRANCHISE INTELLIGENCE REPORT
            </p>
            <h1 className="text-[44px] font-black text-slate-900 text-center leading-[1.2] tracking-tight">
              {districtFull}
              <br />
              상권 분석 결과
            </h1>
            <p className="text-sm text-slate-500 mt-6 tracking-wide">
              SPOTTER AI Multi-Agent Analysis · LangGraph
            </p>
          </div>

          <div className="flex justify-between items-end font-mono text-[10px] text-slate-500 pt-6 border-t border-slate-200">
            <div className="space-y-1.5">
              <p className="tracking-wider">GENERATED · {reportDate}</p>
              <p className="tracking-wider">REQUESTED BY · SPOTTER-HQ</p>
              <p className="tracking-wider">DOCUMENT ID · {docId}</p>
            </div>
            <div className="font-bold text-rose-500 text-sm tracking-[0.25em]">CONFIDENTIAL</div>
          </div>
        </div>

        {/* ─────────── Page 2: 종합 요약 + 차트 ─────────── */}
        <div className={pageClass}>
          <PDFPageHeader pageNumber={2} totalPages={TOTAL_PAGES} districtFull={districtFull} />

          <div className="flex-1 pt-8">
            <h2 className="text-[22px] font-black text-slate-900 mb-1">01. 상권 종합 요약</h2>
            <p className="text-xs text-slate-500 mb-6">
              Executive Summary · 핵심 KPI 및 시계열 분석
            </p>

            {/* KPI Grid */}
            <div className="grid grid-cols-4 gap-3 mb-8">
              {stats.map((s, i) => (
                <div key={i} className="border border-slate-200 bg-slate-50 p-4 rounded-lg">
                  <div className="text-[9px] text-slate-500 mb-2 uppercase tracking-wider">
                    {s.title}
                  </div>
                  <div className="text-[15px] font-black text-slate-900 leading-tight">
                    {s.value}
                  </div>
                  <div className="text-[9px] text-emerald-600 mt-1.5 font-mono">{s.trend}</div>
                </div>
              ))}
            </div>

            {/* Time Series Chart (Light Theme) */}
            <h3 className="text-sm font-bold mb-3 text-slate-900">
              시간대별 유동인구 및 매출 (24H)
            </h3>
            <div className="border border-slate-200 bg-slate-50 rounded-lg p-5 h-[220px] mb-6 relative">
              <svg
                viewBox="0 0 1000 300"
                className="absolute inset-5 w-[calc(100%-40px)] h-[calc(100%-40px)]"
                preserveAspectRatio="none"
              >
                <path
                  d="M 0 280 C 100 280, 150 200, 250 180 C 350 160, 400 250, 500 240 C 600 230, 700 80, 800 100 C 900 120, 950 200, 1000 220 L 1000 300 L 0 300 Z"
                  fill="url(#pdfGrayGrad)"
                  opacity="0.4"
                />
                <path
                  d="M 0 280 C 100 280, 150 200, 250 180 C 350 160, 400 250, 500 240 C 600 230, 700 80, 800 100 C 900 120, 950 200, 1000 220"
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth="3"
                />
                <path
                  d="M 0 290 C 150 290, 200 150, 300 120 C 400 90, 450 200, 550 180 C 650 160, 750 40, 850 50 C 950 60, 980 150, 1000 160 L 1000 300 L 0 300 Z"
                  fill="url(#pdfIndigoGrad)"
                  opacity="0.35"
                />
                <path
                  d="M 0 290 C 150 290, 200 150, 300 120 C 400 90, 450 200, 550 180 C 650 160, 750 40, 850 50 C 950 60, 980 150, 1000 160"
                  fill="none"
                  stroke="#6366f1"
                  strokeWidth="4"
                />
                <defs>
                  <linearGradient id="pdfIndigoGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity="0.5" />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="pdfGrayGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#94a3b8" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#94a3b8" stopOpacity="0" />
                  </linearGradient>
                </defs>
              </svg>
            </div>

            {/* Radar Chart */}
            <h3 className="text-sm font-bold mb-3 text-slate-900">
              상권 종합 지표 분석 (7 Core Metrics)
            </h3>
            <div className="border border-slate-200 bg-slate-50 rounded-lg p-5 flex items-center justify-center">
              <svg viewBox="0 0 200 200" width="240" height="240">
                <polygon
                  points="100,40 147,63 158,113 126,154 74,154 42,113 53,63"
                  fill="#ffffff"
                  stroke="#cbd5e1"
                  strokeWidth="1"
                />
                <polygon
                  points="100,70 123.5,81.5 129,106.5 113,127 87,127 71,106.5 76.5,81.5"
                  fill="none"
                  stroke="#cbd5e1"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                />
                <line x1="100" y1="100" x2="100" y2="40" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="147" y2="63" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="158" y2="113" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="126" y2="154" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="74" y2="154" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="42" y2="113" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="53" y2="63" stroke="#cbd5e1" />
                <polygon
                  points="100,50 140,70 145,110 115,140 85,130 60,105 70,75"
                  fill="rgba(99,102,241,0.25)"
                  stroke="#6366f1"
                  strokeWidth="2"
                />
                <circle cx="100" cy="50" r="3" fill="#6366f1" />
                <circle cx="140" cy="70" r="3" fill="#6366f1" />
                <circle cx="145" cy="110" r="3" fill="#6366f1" />
                <circle cx="115" cy="140" r="3" fill="#6366f1" />
                <circle cx="85" cy="130" r="3" fill="#6366f1" />
                <circle cx="60" cy="105" r="3" fill="#6366f1" />
                <circle cx="70" cy="75" r="3" fill="#6366f1" />
                <text
                  x="100"
                  y="32"
                  fill="#1e293b"
                  fontSize="10"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  유동인구
                </text>
                <text x="157" y="60" fill="#64748b" fontSize="10" textAnchor="start">
                  매출
                </text>
                <text x="168" y="117" fill="#64748b" fontSize="10" textAnchor="start">
                  성장성
                </text>
                <text x="133" y="166" fill="#64748b" fontSize="10" textAnchor="middle">
                  폐업률
                </text>
                <text x="67" y="166" fill="#64748b" fontSize="10" textAnchor="middle">
                  임대료
                </text>
                <text x="32" y="117" fill="#64748b" fontSize="10" textAnchor="end">
                  경쟁강도
                </text>
                <text x="43" y="60" fill="#64748b" fontSize="10" textAnchor="end">
                  접근성
                </text>
              </svg>
            </div>
          </div>

          <PDFPageFooter reportDate={reportDate} />
        </div>

        {/* ─────────── Page 3: 상세 데이터 테이블 ─────────── */}
        <div className={pageClass}>
          <PDFPageHeader pageNumber={3} totalPages={TOTAL_PAGES} districtFull={districtFull} />

          <div className="flex-1 pt-8 space-y-10">
            <div>
              <h2 className="text-[22px] font-black text-slate-900 mb-1">02. 가맹점 간섭도 분석</h2>
              <p className="text-xs text-slate-500 mb-4">
                Cannibalization Analysis · 반경 내 동일 브랜드 영향도
              </p>
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                    <th className="py-2.5 font-medium">가맹점명</th>
                    <th className="py-2.5 font-medium">거리</th>
                    <th className="py-2.5 font-medium">예상 매출 하락</th>
                    <th className="py-2.5 font-medium">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {cannibalizationRows.map((r, i) => (
                    <tr key={i} className="border-b border-slate-200">
                      <td className="py-3 font-medium text-slate-900">{r.name}</td>
                      <td className="py-3 text-slate-600 font-mono">{r.distance}</td>
                      <td className="py-3 font-mono font-bold text-slate-900">{r.impact}</td>
                      <td className="py-3">
                        <span
                          className={`px-2 py-0.5 text-[9px] rounded-full border font-bold ${
                            r.status === 'Safe'
                              ? 'bg-emerald-50 text-emerald-600 border-emerald-200'
                              : 'bg-slate-100 text-slate-600 border-slate-300'
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div>
              <h2 className="text-[22px] font-black text-slate-900 mb-1">03. 행정동 비교 분석</h2>
              <p className="text-xs text-slate-500 mb-4">
                Neighborhood Comparison · 인근 동 AI 점수 / 폐업률 / 손익분기점
              </p>
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                    <th className="py-2.5 font-medium">행정동</th>
                    <th className="py-2.5 font-medium">AI 점수</th>
                    <th className="py-2.5 font-medium">폐업률</th>
                    <th className="py-2.5 font-medium">예상 BEP</th>
                  </tr>
                </thead>
                <tbody>
                  {neighborhoodRows.map((r, i) => (
                    <tr key={i} className="border-b border-slate-200">
                      <td className="py-3 font-medium text-slate-900">{r.name}</td>
                      <td className="py-3 font-mono text-slate-900">{r.score}</td>
                      <td className="py-3 font-mono text-slate-900">{r.closureRate}</td>
                      <td className="py-3 font-mono text-[#6366f1] font-bold">{r.bep}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <PDFPageFooter reportDate={reportDate} />
        </div>

        {/* ─────────── Page 4: AI 인사이트 ─────────── */}
        <div className={pageClass}>
          <PDFPageHeader pageNumber={4} totalPages={TOTAL_PAGES} districtFull={districtFull} />

          <div className="flex-1 pt-8">
            <h2 className="text-[22px] font-black text-slate-900 mb-1">04. SPOTTER AI 인사이트</h2>
            <p className="text-xs text-slate-500 mb-6">
              LangGraph Multi-Agent Analysis · 에이전트 노드별 인사이트
            </p>

            <div className="space-y-4">
              {insights.map((insight, i) => {
                const style = severityStyle[insight.severity];
                return (
                  <div key={i} className={`border rounded-lg p-5 ${style.bg}`}>
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="text-[14px] font-bold text-slate-900 flex-1">
                        {insight.title}
                      </h3>
                      <span className="inline-flex items-center gap-1.5 shrink-0 ml-3">
                        <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                        <span className="text-[9px] font-mono uppercase tracking-[0.15em] text-slate-500">
                          {insight.severity.toUpperCase()}
                        </span>
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-700 leading-relaxed">{insight.desc}</p>
                  </div>
                );
              })}
            </div>

            <div className="mt-10 pt-6 border-t border-slate-200">
              <h4 className="text-[11px] font-bold text-slate-700 mb-2 uppercase tracking-wider">
                분석 방법론 (Methodology)
              </h4>
              <p className="text-[10px] text-slate-500 leading-relaxed">
                본 리포트는 SPOTTER AI 멀티 에이전트 시스템(LangGraph 기반)의 시뮬레이션 결과입니다.
                market_analyst, population_analyst, legal_advisor, financial_insight 4개 노드의 통합
                분석 결과를 포함하며, KT 통신사 셀룰러 데이터,
                공공데이터(상가정보·인구통계·임대시세), 그리고 A2 봉환 팀의 법률 RAG 시스템 (14개
                영역 3,775 청크)을 교차 검증하여 도출되었습니다.
              </p>
              <p className="text-[9px] text-slate-400 mt-3 font-mono">
                DOC ID · {docId} · SPOTTER v3.9 · LangGraph 0.2.x
              </p>
            </div>
          </div>

          <PDFPageFooter reportDate={reportDate} />
        </div>
      </div>
    );
  },
);
HiddenPDFTemplate.displayName = 'HiddenPDFTemplate';

/* ═══════════════════════════════════════════════════════
   DetailDrawer (v8.0) — KPI/차트 클릭 시 우측에서 슬라이드 인
   ═══════════════════════════════════════════════════════ */
function DetailDrawer({
  isOpen,
  onClose,
  drawerKey,
  popData,
  analysisMetrics,
}: {
  isOpen: boolean;
  onClose: () => void;
  drawerKey: DrawerKey;
  popData?: any;
  analysisMetrics?: { main_target_age?: string; peak_time?: string };
}) {
  const baseData = drawerKey ? mockDetailData[drawerKey] : null;
  const data: DetailDataEntry | null =
    drawerKey === 'insight_target' && analysisMetrics?.main_target_age
      ? {
          title: `${analysisMetrics.main_target_age} 타겟 권역 분석`,
          aiReasoning: `유동인구 분석 결과 주요 타겟층: ${analysisMetrics.main_target_age}. 피크 타임대 체류 인구 기반으로 메뉴·마케팅 전략을 해당 층에 집중하면 객단가 및 재방문율 향상이 기대됩니다.`,
          mainTarget: analysisMetrics.main_target_age,
          peakTime: analysisMetrics.peak_time,
        }
      : baseData;

  return (
    <>
      {/* Backdrop Overlay */}
      <div
        className={`fixed inset-0 z-[100] bg-[#1e1b18]/60 backdrop-blur-sm transition-opacity duration-500 ${
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <div
        className={`fixed top-0 right-0 w-full md:w-[480px] h-full bg-[#2c2825] border-l border-[#3a3633] z-[101] shadow-2xl flex flex-col transition-transform duration-[800ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {data && (
          <>
            {/* Header */}
            <div className="flex justify-between items-center p-6 border-b border-[#3a3633] shrink-0">
              <h2 className="text-xl font-bold text-[#e2e8f0]">{data.title}</h2>
              <button
                onClick={onClose}
                className="p-2 text-[#9ca3af] hover:text-[#818cf8] hover:bg-[#818cf8]/10 rounded-lg transition-colors"
                aria-label="Close drawer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 overflow-y-auto custom-scrollbar flex-1 text-[#e2e8f0]">
              {/* AI 산출 근거 */}
              <div className="bg-[#1e1b18] p-5 rounded-xl border border-[#3a3633] mb-4">
                <h3 className="text-xs font-bold text-[#818cf8] tracking-widest uppercase mb-2">
                  AI 산출 근거
                </h3>
                <p className="text-xs text-[#9ca3af] leading-relaxed">
                  {data.aiReasoning || '해당 지표에 대한 상세 분석 알고리즘 로그입니다.'}
                </p>
              </div>

              {/* 메타 데이터 */}
              {(data.confidence ||
                data.rank ||
                data.trend ||
                data.peakTime ||
                data.mainTarget ||
                data.warning) && (
                <div className="bg-[#1e1b18] p-5 rounded-xl border border-[#3a3633] mb-4 space-y-3">
                  <h3 className="text-xs font-bold text-[#818cf8] tracking-widest uppercase mb-3">
                    핵심 지표
                  </h3>
                  {data.confidence && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-[#9ca3af]">신뢰도</span>
                      <span className="text-sm font-bold text-[#e2e8f0] font-mono">
                        {data.confidence}
                      </span>
                    </div>
                  )}
                  {data.rank && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-[#9ca3af]">순위</span>
                      <span className="text-sm font-bold text-[#e2e8f0]">{data.rank}</span>
                    </div>
                  )}
                  {data.trend && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-[#9ca3af]">추세</span>
                      <span className="text-sm font-bold text-emerald-400">{data.trend}</span>
                    </div>
                  )}
                  {data.peakTime && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-[#9ca3af]">피크 타임</span>
                      <span className="text-sm font-bold text-[#e2e8f0] font-mono">
                        {data.peakTime}
                      </span>
                    </div>
                  )}
                  {data.mainTarget && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-[#9ca3af]">주 타겟층</span>
                      <span className="text-sm font-bold text-[#e2e8f0]">{data.mainTarget}</span>
                    </div>
                  )}
                  {data.warning && (
                    <div className="pt-3 border-t border-[#3a3633]">
                      <span className="text-xs text-rose-400 leading-relaxed block">
                        {data.warning}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Detailed Chart — 유동인구 동별 상세 (traffic drawer) */}
              {drawerKey === 'traffic' && popData?.dong_details ? (
                <div className="bg-[#1e1b18] p-5 rounded-xl border border-[#3a3633]">
                  <h3 className="text-xs font-bold text-[#818cf8] tracking-widest uppercase mb-3">
                    동별 유동인구 ({popData.date})
                  </h3>
                  <div className="space-y-2">
                    {popData.dong_details.map((d: any) => {
                      const maxPop = popData.dong_details[0]?.daily_total || 1;
                      const pct = Math.round((d.daily_total / maxPop) * 100);
                      return (
                        <div key={d.dong_name} className="flex items-center gap-3">
                          <span className="text-[11px] text-[#9ca3af] w-16 shrink-0">
                            {d.dong_name}
                          </span>
                          <div className="flex-1 bg-[#2c2825] rounded-full h-4 overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-indigo-600 to-indigo-400 rounded-full transition-all duration-700"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-[11px] text-white font-mono w-20 text-right">
                            {d.daily_total.toLocaleString()}
                          </span>
                          <span className="text-[9px] text-[#9ca3af] w-10">
                            피크 {d.peak_hour}시
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-[9px] text-[#9ca3af] mt-3">
                    ※ 서울시 생활인구 데이터 (KT 통신 기반) | {popData.data_delay_note}
                  </p>
                </div>
              ) : (
                <div className="w-full h-48 bg-[#1e1b18] border border-[#3a3633] rounded-xl flex items-center justify-center">
                  <span className="text-[#3a3633] font-mono text-xs tracking-[0.3em]">
                    DETAILED CHART AREA
                  </span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}

function StatCard({
  title,
  value,
  trend,
  trendUp,
  icon,
  sparkline,
  onClick,
  subtitle,
}: {
  title: string;
  value: string;
  trend: string;
  trendUp: boolean;
  icon: React.ReactElement;
  sparkline: string;
  onClick?: () => void;
  subtitle?: string;
}) {
  return (
    <div
      onClick={onClick}
      className="bg-[#2c2825] border border-[#3a3633] p-6 rounded-xl flex flex-col justify-between gap-3 group cursor-pointer hover:border-[#818cf8] hover:shadow-[0_0_20px_rgba(129,140,248,0.2)] transition-all min-h-[130px]"
    >
      <div className="flex justify-between items-start">
        <p className="text-[#9ca3af] text-xs font-medium">{title}</p>
        <div className="flex items-center gap-1.5">
          {subtitle && (
            <span className="text-[9px] text-[#9ca3af] opacity-50 font-mono">{subtitle}</span>
          )}
          <div className="text-[#9ca3af] opacity-50 group-hover:opacity-100 group-hover:text-indigo-400 transition-colors">
            {React.cloneElement(icon, {
              className: 'w-4 h-4',
            } as React.HTMLAttributes<HTMLElement>)}
          </div>
        </div>
      </div>
      <div>
        <h3 className="text-xl md:text-2xl font-black text-white tracking-tight mb-1">{value}</h3>
        <div className="flex items-center justify-between">
          <span
            className={`text-[10px] font-bold flex items-center gap-0.5 ${trendUp ? 'text-emerald-500' : 'text-rose-500'}`}
          >
            {trendUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}{' '}
            {trend}
          </span>
          <svg
            viewBox="0 0 100 30"
            className="w-12 h-4 overflow-visible opacity-50 group-hover:opacity-100 transition-opacity"
          >
            <path
              d={sparkline}
              fill="none"
              stroke={trendUp ? '#10b981' : '#f43f5e'}
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   SortHeader — 정렬 가능한 테이블 컬럼 헤더
   ═══════════════════════════════════════════════════════ */
function SortHeader({
  label,
  sortField,
  sortKey,
  sortDir,
  onSort,
}: {
  label: string;
  sortField: string;
  sortKey: string | null;
  sortDir: 'asc' | 'desc';
  onSort: (key: string) => void;
}) {
  const isActive = sortKey === sortField;
  return (
    <span
      onClick={() => onSort(sortField)}
      className={`inline-flex items-center gap-1 cursor-pointer transition-colors select-none ${
        isActive ? 'text-[#818cf8]' : 'hover:text-[#e2e8f0]'
      }`}
    >
      {label}
      {isActive ? (
        sortDir === 'asc' ? (
          <ChevronUp className="w-3 h-3 text-[#818cf8]" />
        ) : (
          <ChevronDown className="w-3 h-3 text-[#818cf8]" />
        )
      ) : (
        <ChevronsUpDown className="w-3 h-3 opacity-60" />
      )}
    </span>
  );
}

function TableRow({
  icon,
  col1,
  col2,
  col3,
  status,
  expanded,
  onToggle,
  density = 'standard',
}: {
  icon: React.ReactNode;
  col1: string;
  col2: string;
  col3: string;
  status: string;
  index?: number;
  expanded?: boolean;
  onToggle?: () => void;
  density?: 'comfortable' | 'standard' | 'compact';
}) {
  const getStatusColor = (s: string) => {
    if (s === 'Safe') return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
    if (s === 'Warning') return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
    if (s.includes('개월')) return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
    return 'bg-[#1e1b18] text-[#9ca3af] border-[#3a3633]';
  };
  const dc =
    density === 'compact'
      ? 'py-1.5 px-3 text-[10px]'
      : density === 'comfortable'
        ? 'py-4 px-3 text-sm'
        : 'py-3 px-3 text-xs';
  const statusSize = density === 'compact' ? 'text-[9px]' : 'text-[10px]';
  return (
    <>
      <tr
        onClick={onToggle}
        className={`cursor-pointer transition-colors group ${
          expanded ? 'bg-[#818cf8]/[0.06]' : 'hover:bg-[#3a3633]/50'
        }`}
      >
        <td className={`${dc} pl-5 font-medium text-[#e2e8f0]`}>
          <span className="inline-flex items-center gap-2">
            <ChevronRight
              size={12}
              className={`text-[#9ca3af] transition-transform duration-300 ${
                expanded ? 'rotate-90 text-[#818cf8]' : ''
              }`}
            />
            <span className="text-[#9ca3af] group-hover:text-indigo-400 transition-colors">
              {icon}
            </span>
            {col1}
          </span>
        </td>
        <td className={`${dc} text-[#9ca3af] font-mono`}>{col2}</td>
        <td className={`${dc} font-mono font-bold text-white`}>{col3}</td>
        <td className={dc}>
          <span
            className={`px-2 py-0.5 ${statusSize} font-bold rounded-full border whitespace-nowrap ${getStatusColor(status)}`}
          >
            {status}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-[#1e1b18]">
          <td colSpan={4} className="p-5 border-l-2 border-[#818cf8]">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* 1. Mini Map — 상권 겹침 (Venn) */}
              <div className="flex flex-col gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#9ca3af]">
                  상권 겹침
                </span>
                <div className="bg-[#2c2825] rounded-lg border border-[#3a3633] p-3 flex items-center justify-center">
                  <svg viewBox="0 0 120 70" className="w-full max-w-[160px] h-16">
                    <circle
                      cx="42"
                      cy="35"
                      r="22"
                      fill="rgba(129,140,248,0.2)"
                      stroke="#818cf8"
                      strokeWidth="1.5"
                    />
                    <circle
                      cx="78"
                      cy="35"
                      r="22"
                      fill="rgba(244,63,94,0.2)"
                      stroke="#f43f5e"
                      strokeWidth="1.5"
                    />
                    <text
                      x="42"
                      y="38"
                      fontSize="6"
                      fill="#818cf8"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      신규
                    </text>
                    <text
                      x="78"
                      y="38"
                      fontSize="6"
                      fill="#f43f5e"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      기존
                    </text>
                    <text
                      x="60"
                      y="38"
                      fontSize="5"
                      fill="#e2e8f0"
                      textAnchor="middle"
                      opacity="0.6"
                    >
                      ∩
                    </text>
                  </svg>
                </div>
              </div>

              {/* 2. 시간대별 영향도 */}
              <div className="flex flex-col gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#9ca3af]">
                  시간대별 영향도
                </span>
                <div className="bg-[#2c2825] rounded-lg border border-[#3a3633] p-3 flex flex-col gap-1.5 text-[10px] font-mono">
                  <div className="flex justify-between">
                    <span className="text-[#9ca3af]">오전 (06-11)</span>
                    <span className="text-emerald-400">-0.4%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#9ca3af]">점심 (11-14)</span>
                    <span className="text-rose-400">-2.1%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#9ca3af]">저녁 (17-21)</span>
                    <span className="text-rose-400">-3.4%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#9ca3af]">심야 (21-02)</span>
                    <span className="text-emerald-400">-0.8%</span>
                  </div>
                </div>
              </div>

              {/* 3. Counterfactual */}
              <div className="flex flex-col gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#9ca3af]">
                  Counterfactual
                </span>
                <div className="bg-[#2c2825] rounded-lg border border-[#3a3633] p-3 flex-1 flex flex-col justify-center gap-1">
                  <p className="text-[10px] text-[#9ca3af] leading-relaxed">이 매장이 없었다면</p>
                  <p className="text-lg font-black text-[#818cf8] font-mono leading-none">+18.4%</p>
                  <p className="text-[9px] text-[#9ca3af]">월 매출 추가 예상</p>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function InsightCard({
  icon,
  title,
  desc,
  severity = 'advisory',
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  severity?: 'critical' | 'advisory' | 'opportunity';
  onClick?: () => void;
}) {
  const { showToast } = useToast();
  const severityStyle = {
    critical: { dot: 'bg-rose-500', label: 'CRITICAL' },
    advisory: { dot: 'bg-[#818cf8]', label: 'ADVISORY' },
    opportunity: { dot: 'bg-emerald-500', label: 'OPPORTUNITY' },
  }[severity];

  return (
    <div
      onClick={onClick}
      className="flex flex-col gap-2 p-3 rounded-lg bg-[#1e1b18] border border-[#3a3633] cursor-pointer hover:border-[#818cf8] hover:bg-[#818cf8]/[0.05] transition-all group"
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5">{icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h4 className="text-[#e2e8f0] font-bold text-xs">{title}</h4>
            <span className="inline-flex items-center gap-1 shrink-0">
              <span className={`w-1.5 h-1.5 rounded-full ${severityStyle.dot}`} />
              <span className="text-[8px] font-mono uppercase tracking-wider text-[#9ca3af]">
                {severityStyle.label}
              </span>
            </span>
          </div>
          <p className="text-[#9ca3af] text-[10px] leading-relaxed">{desc}</p>
        </div>
      </div>

      {/* Feedback buttons */}
      <div className="flex justify-end gap-1 pt-1 -mb-0.5 -mr-0.5 opacity-50 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => {
            e.stopPropagation();
            showToast('success', '소중한 피드백이 전달되었습니다. AI 학습에 반영됩니다.');
          }}
          className="p-1 rounded hover:bg-[#818cf8]/10 hover:text-[#818cf8] text-[#9ca3af] transition-colors"
          aria-label="유용함"
        >
          <ThumbsUp className="w-3 h-3" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            showToast('info', '소중한 피드백이 전달되었습니다. AI 학습에 반영됩니다.');
          }}
          className="p-1 rounded hover:bg-rose-500/10 hover:text-rose-400 text-[#9ca3af] transition-colors"
          aria-label="유용하지 않음"
        >
          <ThumbsDown className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   App — Root (전체 앱 진입점)
   ═══════════════════════════════════════════════════════
   [글로벌 상태]
   - isDark: Light/Dark 테마 토글 (SkyThemeToggle 연결)
   - isTransitioning: 씬 전환 시 800ms 암전 오버레이
   - isAppLoaded: 프리로더 완료 여부

   [글로벌 헤더]
   - 인트로 제외 모든 씬에 공통 표시
   - 좌: 로고+BACK / 우: SkyThemeToggle + GlobalLimelightNav
   - ※ AccordionGallery는 자체 3열 헤더를 사용 (중앙 인디케이터 포함)

   [프리로더]
   - 앱 최초 진입 시 3초간 5축 자이로스코프 홀로그램
   - 100% → warp-out 트랜지션 → main-scene-in → isAppLoaded=true → DOM 제거
*/

/* ═══════════════════════════════════════════════════════
   DashboardPanelView — VS 비교 모드용 압축 대시보드 패널
   isVariantB=true면 망원동 데이터, false면 연남동 데이터 출력
   ═══════════════════════════════════════════════════════ */
function DashboardPanelView({
  districtName,
  isVariantB,
  popData,
  dongName,
  accentOverride,
  panelIndex = 0,
}: {
  districtName: string;
  isVariantB: boolean;
  popData?: any;
  dongName?: string;
  accentOverride?: string;
  panelIndex?: number;
}) {
  const revenue = isVariantB ? '₩ 28,100,000' : '₩ 32,400,000';
  const score = isVariantB ? '76 / 100' : '87 / 100';
  const dongPop = popData?.dong_details?.find((d: any) => d.dong_name === dongName);
  const traffic = dongPop
    ? `${dongPop.daily_total.toLocaleString()} 명`
    : isVariantB
      ? '38,205 명'
      : '42,105 명';
  const risk = isVariantB ? 'MEDIUM (28%)' : 'Low (12%)';
  const scoreTrend = isVariantB ? '-2.1 Pts' : '+5.2 Pts';
  const revenueTrend = isVariantB ? '+6.3%' : '+12.5%';
  const radarValues = isVariantB ? [62, 81, 55, 68, 71, 58, 73] : [78, 65, 72, 87, 74, 82, 80];
  const radarLabels = ['유동인구', '임대료', '경쟁강도', '매출추정', '폐업률', '성장성', '접근성'];
  const colorMap = ['text-amber-500', 'text-emerald-500', 'text-sky-500', 'text-rose-500'];
  const badgeColorMap = [
    'bg-amber-500/10 text-amber-500 border-amber-500/20',
    'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
    'bg-sky-500/10 text-sky-500 border-sky-500/20',
    'bg-rose-500/10 text-rose-500 border-rose-500/20',
  ];
  const panelLabels = ['기준', '비교 A', '비교 B', '비교 C'];
  const accentColor = accentOverride || colorMap[panelIndex] || 'text-amber-500';
  const badgeColor = badgeColorMap[panelIndex] || badgeColorMap[0];

  // 레이더 차트 좌표 계산
  const radarPoints = radarValues
    .map((v, i) => {
      const angle = (Math.PI * 2 * i) / 7 - Math.PI / 2;
      const r = (v / 100) * 70;
      return `${100 + r * Math.cos(angle)},${100 + r * Math.sin(angle)}`;
    })
    .join(' ');

  return (
    <div className="flex flex-col gap-4 w-full animate-in fade-in zoom-in-95 duration-500">
      {/* 구역 타이틀 */}
      <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MapPin className={`w-4 h-4 ${accentColor}`} />
          <span className="font-bold text-white text-sm">{districtName}</span>
        </div>
        <span className={`px-2 py-0.5 text-[10px] font-bold rounded border ${badgeColor}`}>
          {panelLabels[panelIndex]}
        </span>
      </div>

      {/* 4 Stats Cards */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-4">
          <p className="text-[10px] text-[#9ca3af] mb-1">예상 월 매출</p>
          <p className="text-lg font-black text-white">{revenue}</p>
          <p className={`text-[10px] mt-1 ${isVariantB ? 'text-emerald-400' : 'text-indigo-400'}`}>
            {revenueTrend}
          </p>
        </div>
        <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-4">
          <p className="text-[10px] text-[#9ca3af] mb-1">상권 매력도</p>
          <p className="text-lg font-black text-white">{score}</p>
          <p className={`text-[10px] mt-1 ${isVariantB ? 'text-rose-400' : 'text-indigo-400'}`}>
            {scoreTrend}
          </p>
        </div>
        <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-4">
          <p className="text-[10px] text-[#9ca3af] mb-1">일 유동인구</p>
          <p className="text-lg font-black text-white">{traffic}</p>
          <p className="text-[10px] mt-1 text-[#9ca3af]">
            {dongPop ? `피크 ${dongPop.peak_hour}시 · ${popData?.date}` : 'KT 통신망 기준'}
          </p>
        </div>
        <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-4">
          <p className="text-[10px] text-[#9ca3af] mb-1">카니발리제이션</p>
          <p className="text-lg font-black text-white">{risk}</p>
          <p className={`text-[10px] mt-1 ${isVariantB ? 'text-amber-400' : 'text-emerald-400'}`}>
            {isVariantB ? '주의 권역' : '안전 권역'}
          </p>
        </div>
      </div>

      {/* 레이더 차트 */}
      <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 flex flex-col items-center">
        <h3 className="text-xs font-bold text-white mb-3 self-start">7대 지표 분석</h3>
        <div className="relative w-[200px] h-[200px]">
          <svg viewBox="0 0 200 200" className="w-full h-full overflow-visible">
            {[20, 40, 60, 80].map((r) => (
              <polygon
                key={r}
                points={Array.from({ length: 7 }, (_, i) => {
                  const a = (Math.PI * 2 * i) / 7 - Math.PI / 2;
                  return `${100 + r * 0.7 * Math.cos(a)},${100 + r * 0.7 * Math.sin(a)}`;
                }).join(' ')}
                fill="none"
                stroke="#3a3633"
                strokeWidth="0.5"
              />
            ))}
            <polygon
              points={radarPoints}
              fill={isVariantB ? 'rgba(16,185,129,0.15)' : 'rgba(129,140,248,0.15)'}
              stroke={isVariantB ? '#10b981' : '#818cf8'}
              strokeWidth="2"
            />
            {radarValues.map((v, i) => {
              const angle = (Math.PI * 2 * i) / 7 - Math.PI / 2;
              const r = (v / 100) * 70;
              return (
                <circle
                  key={i}
                  cx={100 + r * Math.cos(angle)}
                  cy={100 + r * Math.sin(angle)}
                  r="3"
                  fill={isVariantB ? '#10b981' : '#818cf8'}
                />
              );
            })}
            {radarLabels.map((label, i) => {
              const angle = (Math.PI * 2 * i) / 7 - Math.PI / 2;
              const lx = 100 + 85 * Math.cos(angle);
              const ly = 100 + 85 * Math.sin(angle);
              return (
                <text
                  key={i}
                  x={lx}
                  y={ly}
                  fill="#9ca3af"
                  fontSize="9"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {label}
                </text>
              );
            })}
          </svg>
        </div>
      </div>

      {/* AI 인사이트 요약 */}
      <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5">
        <h3 className="text-xs font-bold text-white mb-3">AI 인사이트</h3>
        <div className="space-y-2">
          <div className="flex items-start gap-2 text-xs text-[#d1d5db]">
            <TrendingUp className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
            <span>
              {isVariantB
                ? '망원동은 주거 밀집형 상권으로 점심 시간대 매출 비중이 높습니다.'
                : '저녁 시간대 유동인구 급증. 야간 메뉴 강화를 권장합니다.'}
            </span>
          </div>
          <div className="flex items-start gap-2 text-xs text-[#d1d5db]">
            <Scale className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
            <span>
              {isVariantB
                ? '반경 300m 내 동종 프랜차이즈 7개. 카니발리제이션 주의 필요.'
                : '상가임대차보호법 위반 사례 존재 권역. 법적 분쟁 리스크 감지.'}
            </span>
          </div>
          <div className="flex items-start gap-2 text-xs text-[#d1d5db]">
            <Users className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
            <span>
              {isVariantB
                ? '3040 직장인 비율 38%. 오피스 근접성이 강점입니다.'
                : '2030 여성 타겟 구역. SNS 친화적 인테리어 도입 시 수익 +34%.'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   SpotterAgentWorkflow — AI 에이전트 파이프라인 시각화
   LangGraph 5-노드 워크플로우를 Drawer 안에서 표시
   ═══════════════════════════════════════════════════════ */
// 🌟 백엔드 아키텍처 변경(Parallel Analysis) 완벽 반영
// - Supervisor LLM 제거 → 하드코딩 parallel_analysis 라우터로 교체
// - Market / Population / Legal 3개 에이전트 동시(Parallel) 실행
const spotterAgentTasks = [
  {
    id: '1',
    title: 'Parallel Analysis Node (병렬 라우터)',
    description:
      'LLM 개입 없이 하드코딩된 코드로 3개의 전문 에이전트를 동시에(Parallel) 병렬 호출하여 속도를 극대화합니다.',
    status: 'completed' as const,
    priority: 'high',
    dependencies: [] as string[],
    subtasks: [
      {
        id: '1.1',
        title: '파라미터 추출 및 쿼리 최적화',
        description: '사용자 입력값 파싱 및 DB 쿼리 파라미터 생성',
        status: 'completed' as const,
        tools: ['Python', 'Regex'],
      },
      {
        id: '1.2',
        title: '하위 에이전트 병렬 분배 (Simultaneous Dispatch)',
        description: 'Market, Population, Legal 에이전트 동시 실행 트리거',
        status: 'completed' as const,
        tools: ['LangGraph Parallel'],
      },
    ],
  },
  {
    id: '2',
    title: 'Market Analyst (상권 & 경쟁 분석)',
    description: 'pgvector DB에서 상권의 매출 현황과 카니발리제이션 위험도를 계산합니다.',
    status: 'in-progress' as const,
    priority: 'high',
    dependencies: ['1'],
    subtasks: [
      {
        id: '2.1',
        title: '경쟁점 반경 검색 (Vector Search)',
        description: 'HNSW 인덱스를 활용한 500m 내 동종 업계 검색',
        status: 'completed' as const,
        tools: ['pgvector', 'PostgreSQL'],
      },
      {
        id: '2.2',
        title: '예상 매출 LSTM 추론',
        description: '최근 3년 매출 데이터를 기반으로 향후 12개월 매출 예측',
        status: 'in-progress' as const,
        tools: ['LSTM Model', 'TensorFlow'],
      },
      {
        id: '2.3',
        title: '카니발리제이션 타격률 계산',
        description: '인접 가맹점 간의 상권 중첩도 기반 매출 하락률 도출',
        status: 'pending' as const,
        tools: ['Cannibalization Engine'],
      },
    ],
  },
  {
    id: '3',
    title: 'Population Analyst (유동인구 분석)',
    description: 'KT 통신망 데이터를 기반으로 시간대별, 성별/연령별 유동인구를 군집화합니다.',
    status: 'in-progress' as const,
    priority: 'medium',
    dependencies: ['1'],
    subtasks: [
      {
        id: '3.1',
        title: '시간대별 유동인구 집계',
        description: '06시~02시까지의 시간대별 트래픽 분포 계산',
        status: 'completed' as const,
        tools: ['KT API'],
      },
      {
        id: '3.2',
        title: '핵심 타겟(Primary Target) 매칭',
        description: '브랜드 타겟층(2030 여성)과 해당 상권 유동인구 비율 대조',
        status: 'in-progress' as const,
        tools: ['Demographic Scraper'],
      },
    ],
  },
  {
    id: '4',
    title: 'Legal Analyst (법률 리스크 RAG)',
    description:
      '상가임대차보호법 및 지역 규제 데이터를 검색하여 권리금/임대료 리스크를 판단합니다.',
    status: 'in-progress' as const,
    priority: 'high',
    dependencies: ['1'],
    subtasks: [
      {
        id: '4.1',
        title: '문서 청크 검색 (Similarity Search)',
        description: '관련 법률 문서 및 최근 판례 RAG 검색',
        status: 'in-progress' as const,
        tools: ['Sentence-Transformers', 'Vector DB'],
      },
      {
        id: '4.2',
        title: '리스크 요약 및 경고 생성',
        description: '검색된 판례를 바탕으로 LLM 기반 위험 요소 3줄 요약',
        status: 'pending' as const,
        tools: ['Gemini 1.5 Pro'],
      },
    ],
  },
  {
    id: '5',
    title: 'Strategy Synthesizer (최종 종합)',
    description:
      '병렬 실행된 3개 에이전트의 결과를 취합하여 7대 지표를 정규화하고 최종 인사이트를 작성합니다.',
    status: 'pending' as const,
    priority: 'high',
    dependencies: ['2', '3', '4'],
    subtasks: [
      {
        id: '5.1',
        title: '0~100점 정규화 (Normalization)',
        description: '7개 주요 메트릭을 레이더 차트용 점수로 변환',
        status: 'pending' as const,
        tools: ['Math Module'],
      },
      {
        id: '5.2',
        title: '종합 매력도 및 BEP 산출',
        description: '투자금 대비 손익분기점(BEP) 도달 개월 수 계산',
        status: 'pending' as const,
        tools: ['ROI Calculator'],
      },
    ],
  },
];

type TaskStatus = 'completed' | 'in-progress' | 'pending';
type AgentTask = {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: string;
  dependencies: string[];
  subtasks: {
    id: string;
    title: string;
    description: string;
    status: TaskStatus;
    tools: string[];
  }[];
};

function SpotterAgentWorkflow() {
  const [tasks, setTasks] = useState<AgentTask[]>(spotterAgentTasks as AgentTask[]);
  // 병렬 실행 중인 3개 (Market/Population/Legal) 모두 펼쳐두어 동시성 시각화
  const [expandedTasks, setExpandedTasks] = useState<string[]>(['2', '3', '4']);
  const [expandedSubtasks, setExpandedSubtasks] = useState<Record<string, boolean>>({});

  // 병렬(Parallel) 처리 시뮬레이션 — 3개 에이전트가 약간의 시차로 동시 완료
  useEffect(() => {
    const t1 = setTimeout(() => toggleSubtaskStatus('2', '2.2'), 2000);
    const t2 = setTimeout(() => toggleSubtaskStatus('3', '3.2'), 2500);
    const t3 = setTimeout(() => toggleSubtaskStatus('4', '4.1'), 3000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleTaskExpansion = (taskId: string) => {
    setExpandedTasks((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId],
    );
  };
  const toggleSubtaskExpansion = (taskId: string, subtaskId: string) => {
    const key = `${taskId}-${subtaskId}`;
    setExpandedSubtasks((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleSubtaskStatus = (taskId: string, subtaskId: string) => {
    setTasks((prev) =>
      prev.map((task) => {
        if (task.id === taskId) {
          const updatedSubtasks = task.subtasks.map((subtask) => {
            if (subtask.id === subtaskId)
              return {
                ...subtask,
                status: (subtask.status === 'completed' ? 'pending' : 'completed') as TaskStatus,
              };
            return subtask;
          });
          const allCompleted = updatedSubtasks.every((s) => s.status === 'completed');
          return {
            ...task,
            subtasks: updatedSubtasks,
            status: (allCompleted ? 'completed' : 'in-progress') as TaskStatus,
          };
        }
        return task;
      }),
    );
  };

  const variants = {
    hidden: { opacity: 0, y: -5 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { type: 'spring' as const, stiffness: 500, damping: 30 },
    },
    listVisible: {
      opacity: 1,
      height: 'auto',
      transition: { duration: 0.25, staggerChildren: 0.05, when: 'beforeChildren' as const },
    },
    listHidden: {
      opacity: 0,
      height: 0,
      overflow: 'hidden' as const,
      transition: { duration: 0.2 },
    },
  };

  return (
    <div className="w-full font-sans text-[#e2e8f0]">
      <LayoutGroup>
        <ul className="space-y-1">
          {tasks.map((task, index) => {
            const isExpanded = expandedTasks.includes(task.id);
            const isCompleted = task.status === 'completed';
            return (
              <motion.li
                key={task.id}
                className={index !== 0 ? 'mt-2 pt-2 border-t border-[#3a3633]' : ''}
                initial="hidden"
                animate="visible"
                variants={variants}
              >
                <motion.div
                  className="group flex items-center px-3 py-2.5 rounded-lg hover:bg-[#2c2825] transition-colors cursor-pointer"
                  onClick={() => toggleTaskExpansion(task.id)}
                >
                  <div className="mr-3 shrink-0">
                    <AnimatePresence mode="wait">
                      <motion.div
                        key={task.status}
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                      >
                        {task.status === 'completed' ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                        ) : task.status === 'in-progress' ? (
                          <CircleDotDashed className="w-5 h-5 text-[#818cf8] animate-spin-slow" />
                        ) : (
                          <Circle className="w-5 h-5 text-[#404040]" />
                        )}
                      </motion.div>
                    </AnimatePresence>
                  </div>
                  <div className="flex-1 flex justify-between items-center min-w-0">
                    <div className="truncate pr-4">
                      <span
                        className={`text-sm font-bold ${isCompleted ? 'text-[#9ca3af] line-through decoration-[#3a3633]' : 'text-[#e2e8f0]'}`}
                      >
                        {task.title}
                      </span>
                    </div>
                    <div className="flex shrink-0 gap-2 items-center">
                      {task.dependencies.length > 0 && (
                        <div className="hidden sm:flex gap-1 mr-2">
                          {task.dependencies.map((dep) => (
                            <span
                              key={dep}
                              className="px-1.5 py-0.5 rounded bg-[#2c2825] border border-[#3a3633] text-[9px] font-mono text-[#9ca3af]"
                            >
                              Step {dep} 완료 후
                            </span>
                          ))}
                        </div>
                      )}
                      <span
                        className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${isCompleted ? 'bg-emerald-500/10 text-emerald-500' : task.status === 'in-progress' ? 'bg-[#818cf8]/10 text-[#818cf8]' : 'bg-[#3a3633] text-[#9ca3af]'}`}
                      >
                        {task.status.replace('-', ' ')}
                      </span>
                    </div>
                  </div>
                </motion.div>
                <AnimatePresence mode="wait">
                  {isExpanded && task.subtasks.length > 0 && (
                    <motion.div
                      className="relative overflow-hidden ml-[22px] pl-4 border-l-2 border-dashed border-[#3a3633] mt-2 mb-3"
                      variants={variants}
                      initial="listHidden"
                      animate="listVisible"
                      exit="listHidden"
                      layout
                    >
                      <ul className="space-y-1">
                        {task.subtasks.map((subtask) => {
                          const subtaskKey = `${task.id}-${subtask.id}`;
                          const isSubExp = expandedSubtasks[subtaskKey];
                          return (
                            <motion.li
                              key={subtask.id}
                              className="flex flex-col"
                              variants={variants}
                              layout
                            >
                              <div
                                className="flex items-center p-1.5 rounded-md hover:bg-[#2c2825] cursor-pointer transition-colors"
                                onClick={() => toggleSubtaskExpansion(task.id, subtask.id)}
                              >
                                <div
                                  className="mr-2"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleSubtaskStatus(task.id, subtask.id);
                                  }}
                                >
                                  {subtask.status === 'completed' ? (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                  ) : subtask.status === 'in-progress' ? (
                                    <CircleDotDashed className="w-4 h-4 text-[#818cf8] animate-spin-slow" />
                                  ) : (
                                    <Circle className="w-4 h-4 text-[#404040]" />
                                  )}
                                </div>
                                <span
                                  className={`text-xs ${subtask.status === 'completed' ? 'text-[#6b7280] line-through' : 'text-[#d1d5db]'}`}
                                >
                                  {subtask.title}
                                </span>
                              </div>
                              <AnimatePresence mode="wait">
                                {isSubExp && (
                                  <motion.div
                                    className="ml-6 pl-3 border-l border-dashed border-[#404040] py-2"
                                    variants={variants}
                                    initial="listHidden"
                                    animate="listVisible"
                                    exit="listHidden"
                                    layout
                                  >
                                    <p className="text-[11px] text-[#9ca3af] mb-2 leading-relaxed">
                                      {subtask.description}
                                    </p>
                                    <div className="flex flex-wrap items-center gap-1.5">
                                      <span className="text-[9px] font-mono text-[#6b7280] uppercase">
                                        Tools:
                                      </span>
                                      {subtask.tools.map((tool) => (
                                        <span
                                          key={tool}
                                          className="px-1.5 py-0.5 rounded bg-[#1e1b18] border border-[#3a3633] text-[9px] font-mono text-[#818cf8]"
                                        >
                                          {tool}
                                        </span>
                                      ))}
                                    </div>
                                  </motion.div>
                                )}
                              </AnimatePresence>
                            </motion.li>
                          );
                        })}
                      </ul>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.li>
            );
          })}
        </ul>
      </LayoutGroup>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   CommandPalette — Cmd+K 전역 커맨드 팔레트
   ═══════════════════════════════════════════════════════ */
function CommandPalette({
  isOpen,
  onClose,
  onNavigate,
}: {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (path: string) => void;
}) {
  const { showToast } = useToast();
  if (!isOpen) return null;

  const handleAction = (action: () => void) => {
    action();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[99999] flex items-start justify-center pt-[15vh] sm:pt-[20vh] px-4">
      <div className="absolute inset-0 bg-[#050505]/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl bg-[#1e1b18] border border-[#3a3633] rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.5)] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Search Input */}
        <div className="flex items-center px-4 border-b border-[#3a3633]">
          <Search className="w-5 h-5 text-[#818cf8]" />
          <input
            autoFocus
            type="text"
            placeholder="Type a command or search..."
            className="w-full bg-transparent border-none px-4 py-5 text-sm text-[#e2e8f0] placeholder-[#9ca3af] focus:outline-none"
          />
          <kbd className="px-2 py-1 bg-[#2c2825] border border-[#3a3633] rounded text-[10px] font-mono text-[#9ca3af]">
            ESC
          </kbd>
        </div>
        {/* Commands */}
        <div className="max-h-[60vh] overflow-y-auto p-2 custom-scrollbar">
          <div className="px-3 py-2 text-[10px] font-bold text-[#9ca3af] uppercase tracking-wider">
            Navigation
          </div>
          <button
            onClick={() => handleAction(() => onNavigate('accordion'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <LayoutDashboard className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                시뮬레이터 대시보드
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[#3a3633] group-hover:text-[#818cf8]" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('hq'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Building2 className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                HQ 커맨드 센터
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[#3a3633] group-hover:text-[#818cf8]" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('about'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <FileText className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                About SPOTTER
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[#3a3633] group-hover:text-[#818cf8]" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('contact'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Mail className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                Contact
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[#3a3633] group-hover:text-[#818cf8]" />
          </button>

          <div className="px-3 py-2 mt-2 text-[10px] font-bold text-[#9ca3af] uppercase tracking-wider">
            Quick Actions
          </div>
          <button
            onClick={() => handleAction(() => showToast('info', '테마 전환 기능은 준비 중입니다.'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Settings className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                다크/라이트 테마 전환
              </span>
            </div>
          </button>
          <button
            onClick={() =>
              handleAction(() => showToast('info', '로그아웃은 우측 상단 메뉴를 이용해주세요.'))
            }
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-rose-500/10 group transition-colors"
          >
            <div className="flex items-center gap-3">
              <LogOut className="w-4 h-4 text-[#9ca3af] group-hover:text-rose-500" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-rose-500">
                로그아웃
              </span>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}

/** 암전 트랜지션 네비게이션 Context — 모든 하위 컴포넌트에서 사용 가능 */
const TransitionContext = createContext<(path: string) => void>(() => {});
export const useTransition = () => useContext(TransitionContext);

/** 현재 경로 → scene 이름 매핑 */
function pathToScene(
  pathname: string,
): 'intro' | 'about' | 'joinus' | 'accordion' | 'simulator' | 'contact' | 'hq' | 'login' {
  if (pathname === '/about') return 'about';
  if (pathname === '/joinus') return 'joinus';
  if (pathname === '/explore') return 'accordion';
  if (pathname === '/simulator') return 'simulator';
  if (pathname === '/contact') return 'contact';
  if (pathname === '/hq') return 'hq';
  if (pathname === '/login') return 'login';
  return 'intro';
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const scene = pathToScene(location.pathname);

  const [isTransitioning, setIsTransitioning] = useState(false);
  const [reportState, setReportState] = useState<'idle' | 'loading' | 'result'>('idle');
  const [activeMenuIndex, setActiveMenuIndex] = useState(2);

  // Simulation background tracking (IM3-205): store가 페이지 이동과 독립적으로
  // 시뮬레이션 상태를 보유. useCompletionToast는 running→done/error 전이 감지.
  useCompletionToast();
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
              <Routes>
                <Route
                  path="/"
                  element={
                    <IntroScene
                      activeMenuIndex={activeMenuIndex}
                      setActiveMenuIndex={setActiveMenuIndex}
                      onAboutClick={() => transitionTo('about')}
                      onLoginClick={() => transitionTo('login')}
                      onSimulatorClick={() => transitionTo('accordion')}
                      onContactClick={() => transitionTo('contact')}
                    />
                  }
                />
                <Route path="/about" element={<AboutPage onBack={() => transitionTo('intro')} />} />
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
                      onLogoClick={() => transitionTo('intro')}
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
                <Route
                  path="/hq"
                  element={
                    <ProtectedRoute requireRole="master">
                      <HQCommandCenter />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/login"
                  element={<LoginPage onLogoClick={() => transitionTo('intro')} />}
                />
              </Routes>

              {/* IM3-205: 시뮬레이션 백그라운드 추적 — 라우팅 바깥에 마운트 */}
              <SimulationFloatingWidget />
              <BeforeUnloadGuard />
              <ToastHost />

              {/* Global header — all scenes except intro */}
              {scene !== 'intro' && scene !== 'login' && !isTransitioning && (
                <header className="fixed top-0 left-0 w-full h-24 border-b border-[#3a3633] flex items-center px-8 md:px-16 justify-between bg-[#1e1b18]/90 backdrop-blur-md z-50 transition-colors duration-500">
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
                        // 시뮬레이터 result 상태 → history.back() 호출 → popstate 리스너가 idle로 복귀
                        // (브라우저 뒤로가기와 동일한 코드 경로 → 히스토리 정합성 유지)
                        if (scene === 'simulator' && reportState === 'result') {
                          window.history.back();
                          return;
                        }
                        transitionTo(scene === 'simulator' ? 'accordion' : 'intro');
                      }}
                      className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors duration-300"
                    >
                      <ChevronRight size={14} className="rotate-180" />
                      BACK
                    </button>
                  </div>
                  <div className="flex items-center gap-4 md:gap-6">
                    <GlobalLimelightNav />
                    <LogoutButton />
                  </div>
                </header>
              )}

              {/* Command Palette (Cmd+K / Ctrl+K) */}
              <CommandPalette
                isOpen={isCommandOpen}
                onClose={() => setIsCommandOpen(false)}
                onNavigate={(target) => {
                  setIsCommandOpen(false);
                  transitionTo(target as any);
                }}
              />

              {/* Transition overlay */}
              <div
                className={`fixed inset-0 z-50 bg-black pointer-events-none transition-opacity duration-[800ms] ${
                  isTransitioning ? 'opacity-100' : 'opacity-0'
                }`}
              />

              {/* 3D Hologram Preloader */}
              {!isAppLoaded && (
                <div
                  className="absolute inset-0 z-[99999] bg-[#1e1b18] flex flex-col items-center justify-center"
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
                      <div className="absolute w-[40%] h-[40%] rounded-full bg-indigo-500/20 blur-[40px]" />

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
                          stroke="#818cf8"
                          strokeWidth="0.5"
                          strokeDasharray="2 6"
                        />
                        <circle
                          cx="100"
                          cy="100"
                          r="90"
                          fill="none"
                          stroke="#818cf8"
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
                          stroke="#6366f1"
                          strokeWidth="3"
                          strokeDasharray="60 30 10 30"
                          strokeLinecap="round"
                        />
                        <circle cx="100" cy="15" r="5" fill="#818cf8" />
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
                          stroke="#a5b4fc"
                          strokeWidth="1"
                          strokeDasharray="4 8"
                        />
                        <circle
                          cx="100"
                          cy="100"
                          r="70"
                          fill="none"
                          stroke="#818cf8"
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
                          stroke="#a5b4fc"
                          strokeWidth="1"
                          style={{ filter: 'drop-shadow(0 0 8px #a5b4fc)' }}
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
                          stroke="#818cf8"
                          strokeWidth="1"
                          strokeDasharray="4 16"
                        />
                        <circle
                          cx="100"
                          cy="100"
                          r="94"
                          fill="none"
                          stroke="#6366f1"
                          strokeWidth="0.5"
                        />
                      </svg>

                      {/* Center percentage */}
                      <div
                        className="absolute flex flex-col items-center justify-center pointer-events-none"
                        style={{ animation: 'energy-pulse 2s ease-in-out infinite' }}
                      >
                        <span className="font-black text-6xl md:text-8xl text-indigo-400 tracking-tighter leading-none">
                          {loadProgress}
                          <span className="text-3xl md:text-4xl text-indigo-400/60 ml-1">%</span>
                        </span>
                        <span className="font-mono text-[10px] md:text-xs text-indigo-400/80 tracking-[0.3em] mt-2">
                          SYNCING...
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Terminal logs */}
                  <div className="absolute bottom-10 left-10 md:bottom-16 md:left-16 font-mono text-[10px] md:text-xs text-[#9ca3af] max-w-md">
                    <div className="flex flex-col gap-1.5">
                      {loadLogs.map((log, idx) => (
                        <div
                          key={idx}
                          className={idx === loadLogs.length - 1 ? 'text-indigo-400 font-bold' : ''}
                        >
                          {log}
                        </div>
                      ))}
                    </div>
                    <div className="w-2 h-3 bg-indigo-500 mt-2 animate-pulse" />
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
