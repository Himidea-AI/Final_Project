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
 *   - SimulatorDashboard.runSim()에서 runSimulation() + analyzeLocation() 호출
 *
 * [팀원 참고]
 *   - A1/B1: api/client.ts의 Mock 응답 형태 = 실제 API 응답과 동일해야 함
 *   - B2: SimResult.chartData 7개 항목 = 에이전트 노드별 점수
 *   - C2: Docker 배포 시 nginx.conf의 /api 프록시가 백엔드를 가리켜야 함
 */

import { useState, useEffect, useRef, useCallback, forwardRef } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import JoinUsPage from "./pages/JoinUs/JoinUsPage";
import HQCommandCenter from "./pages/HQCommandCenter";
import LoginPage from "./pages/LoginPage";
import { runSimulation, analyzeLocation } from "./api/client";
import React from "react";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import * as XLSX from "xlsx";

/**
 * 시뮬레이션 결과 — UI 바인딩용
 * 백엔드 SimulationOutput + AnalysisResult를 프론트 UI에 맞게 변환한 구조.
 * runSim() 함수에서 API 응답을 이 형태로 매핑하여 simResult state에 저장.
 */
interface SimResult {
  score: number;        // 상권 종합 매력도 (0~100)
  revenue: number;      // 예상 월 매출 (만원 단위)
  riskLevel: string;    // 카니발리제이션 위험도 ("LOW" | "MEDIUM" | "HIGH")
  recommendation: string; // AI 추천 코멘트 (에이전트 생성)
  chartData: { label: string; value: number }[]; // 7개 항목별 점수 (레이더 차트 데이터)
}
import {
  ChevronRight,
  Sliders,
  Activity,
  MapPin,
  BarChart3,
  Play,
  ExternalLink,
  Mail,
  Phone,
  GitFork,
  Users,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Download,
  Calendar,
  Store,
  Crosshair,
  Zap,
  Scale,
  FileText,
  Database,
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
} from "lucide-react";

/* ═══════════════════════════════════════════════════════
   DATA
   ═══════════════════════════════════════════════════════ */

const DISTRICTS = [
  { name: "강남구", eng: "GANGNAM", img: "/images/Gangnam-gu.svg" },
  { name: "강동구", eng: "GANGDONG", img: "/images/Gangdong-gu.svg" },
  { name: "강북구", eng: "GANGBUK", img: "/images/Gangbuk-gu.svg" },
  { name: "강서구", eng: "GANGSEO", img: "/images/Gangseo-gu.svg" },
  { name: "관악구", eng: "GWANAK", img: "/images/Gwanak-gu.svg" },
  { name: "광진구", eng: "GWANGJIN", img: "/images/Gwangjin-gu.svg" },
  { name: "구로구", eng: "GURO", img: "/images/Guro-gu.svg" },
  { name: "금천구", eng: "GEUMCHEON", img: "/images/Geumcheon-gu.svg" },
  { name: "노원구", eng: "NOWON", img: "/images/Nowon-gu.svg" },
  { name: "도봉구", eng: "DOBONG", img: "/images/Dobong-gu.svg" },
  { name: "동대문구", eng: "DONGDAEMUN", img: "/images/Dongdaemun-gu.svg" },
  { name: "동작구", eng: "DONGJAK", img: "/images/Dongjak-gu.svg" },
  { name: "마포구", eng: "MAPO", img: "/images/Mapo-gu.svg" },
  { name: "서대문구", eng: "SEODAEMUN", img: "/images/Seodaemun-gu.svg" },
  { name: "서초구", eng: "SEOCHO", img: "/images/Seocho-gu.svg" },
  { name: "성동구", eng: "SEONGDONG", img: "/images/Seongdong-gu.svg" },
  { name: "성북구", eng: "SEONGBUK", img: "/images/Seongbuk-gu.svg" },
  { name: "송파구", eng: "SONGPA", img: "/images/Songpa-gu.svg" },
  { name: "양천구", eng: "YANGCHEON", img: "/images/Yangcheon-gu.svg" },
  { name: "영등포구", eng: "YEONGDEUNGPO", img: "/images/Yeongdeungpo-gu.svg" },
  { name: "용산구", eng: "YONGSAN", img: "/images/Yongsan-gu.svg" },
  { name: "은평구", eng: "EUNPYEONG", img: "/images/Eunpyeong-gu.svg" },
  { name: "종로구", eng: "JONGNO", img: "/images/Jongno-gu.svg" },
  { name: "중구", eng: "JUNG", img: "/images/Jung-gu.svg" },
  { name: "중랑구", eng: "JUNGNANG", img: "/images/Jungnang-gu.svg" },
];

const MAPO_IDX = 12;

const MENU_ITEMS = ["ABOUT SPOTTER", "JOIN US", "SIMULATOR", "CONTACT"];

const DONG_DATA: Record<string, string[]> = {
  "강남구": ["신사동","논현1동","논현2동","압구정동","청담동","삼성1동","삼성2동","대치1동","대치2동","대치4동","역삼1동","역삼2동","도곡1동","도곡2동","개포1동","개포2동","개포3동","개포4동","일원본동","일원1동","수서동","세곡동"],
  "강동구": ["강일동","상일1동","상일2동","명일1동","명일2동","고덕1동","고덕2동","암사1동","암사2동","암사3동","천호1동","천호2동","천호3동","성내1동","성내2동","성내3동","둔촌1동","둔촌2동"],
  "강북구": ["삼양동","미아동","송중동","송천동","삼각산동","번1동","번2동","번3동","수유1동","수유2동","수유3동","우이동","인수동"],
  "강서구": ["염창동","등촌1동","등촌2동","등촌3동","화곡1동","화곡2동","화곡3동","화곡4동","화곡6동","화곡8동","가양1동","가양2동","가양3동","발산1동","공항동","방화1동","방화2동","방화3동"],
  "관악구": ["보라매동","청림동","행운동","낙성대동","중앙동","인헌동","남현동","서원동","신원동","서림동","신사동","신림동","난향동","조원동","대학동","은천동","성현동","청룡동","난곡동","삼성동","미성동"],
  "광진구": ["중곡1동","중곡2동","중곡3동","중곡4동","능동","구의1동","구의2동","구의3동","광장동","자양1동","자양2동","자양3동","자양4동","화양동","군자동"],
  "구로구": ["신도림동","구로1동","구로2동","구로3동","구로4동","구로5동","가리봉동","고척1동","고척2동","개봉1동","개봉2동","개봉3동","오류1동","오류2동","항동"],
  "금천구": ["가산동","독산1동","독산2동","독산3동","독산4동","시흥1동","시흥2동","시흥3동","시흥4동","시흥5동"],
  "노원구": ["월계1동","월계2동","월계3동","공릉1동","공릉2동","하계1동","하계2동","중계본동","중계1동","중계2동","중계3동","상계1동","상계2동","상계3·4동","상계5동","상계6·7동","상계8동","상계9동","상계10동"],
  "도봉구": ["쌍문1동","쌍문2동","쌍문3동","쌍문4동","방학1동","방학2동","방학3동","창1동","창2동","창3동","창4동","창5동","도봉1동","도봉2동"],
  "동대문구": ["용신동","제기동","전농1동","전농2동","답십리1동","답십리2동","장안1동","장안2동","청량리동","회기동","휘경1동","휘경2동","이문1동","이문2동"],
  "동작구": ["노량진1동","노량진2동","상도1동","상도2동","상도3동","상도4동","흑석동","사당1동","사당2동","사당3동","사당4동","사당5동","대방동","신대방1동","신대방2동"],
  "마포구": ["공덕동","아현동","도화동","용강동","대흥동","염리동","신수동","서강동","서교동","합정동","망원1동","망원2동","연남동","성산1동","성산2동","상암동"],
  "서대문구": ["충현동","천연동","북아현동","신촌동","연희동","홍제1동","홍제2동","홍제3동","홍은1동","홍은2동","남가좌1동","남가좌2동","북가좌1동","북가좌2동"],
  "서초구": ["서초1동","서초2동","서초3동","서초4동","잠원동","반포본동","반포1동","반포2동","반포3동","반포4동","방배본동","방배1동","방배2동","방배3동","방배4동","양재1동","양재2동","내곡동"],
  "성동구": ["왕십리2동","왕십리도선동","마장동","사근동","행당1동","행당2동","응봉동","금호1가동","금호2·3가동","금호4가동","옥수동","성수1가1동","성수1가2동","성수2가1동","성수2가3동","송정동","용답동"],
  "성북구": ["성북동","삼선동","동선동","돈암1동","돈암2동","안암동","보문동","정릉1동","정릉2동","정릉3동","정릉4동","길음1동","길음2동","종암동","월곡1동","월곡2동","장위1동","장위2동","장위3동","석관동"],
  "송파구": ["풍납1동","풍납2동","거여1동","거여2동","마천1동","마천2동","방이1동","방이2동","오륜동","오금동","송파1동","송파2동","석촌동","삼전동","가락본동","가락1동","가락2동","문정1동","문정2동","장지동","위례동","잠실본동","잠실2동","잠실3동","잠실4동","잠실6동","잠실7동"],
  "양천구": ["목1동","목2동","목3동","목4동","목5동","신월1동","신월2동","신월3동","신월4동","신월5동","신월6동","신월7동","신정1동","신정2동","신정3동","신정4동","신정6동","신정7동"],
  "영등포구": ["영등포본동","영등포동","여의동","당산1동","당산2동","도림동","문래동","양평1동","양평2동","신길1동","신길3동","신길4동","신길5동","신길6동","신길7동","대림1동","대림2동","대림3동"],
  "용산구": ["후암동","용산2가동","남영동","청파동","원효로1동","원효로2동","효창동","용문동","한강로동","이촌1동","이촌2동","이태원1동","이태원2동","한남동","서빙고동","보광동"],
  "은평구": ["녹번동","불광1동","불광2동","갈현1동","갈현2동","구산동","대조동","응암1동","응암2동","응암3동","역촌동","신사1동","신사2동","증산동","수색동","진관동"],
  "종로구": ["청운효자동","사직동","삼청동","부암동","평창동","무악동","교남동","가회동","종로1·2·3·4가동","종로5·6가동","이화동","혜화동","창신1동","창신2동","창신3동","숭인1동","숭인2동"],
  "중구": ["소공동","회현동","명동","필동","장충동","광희동","을지로동","신당동","다산동","약수동","청구동","신당5동","동화동","황학동","중림동"],
  "중랑구": ["면목본동","면목2동","면목3·8동","면목4동","면목5동","면목7동","상봉1동","상봉2동","중화1동","중화2동","묵1동","묵2동","망우본동","망우3동","신내1동","신내2동"],
};

const CHART_DATA = [
  { label: "유동인구", value: 82 },
  { label: "임대료", value: 45 },
  { label: "경쟁강도", value: 68 },
  { label: "매출추정", value: 74 },
  { label: "생존율", value: 91 },
  { label: "성장성", value: 56 },
  { label: "접근성", value: 78 },
];

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
  "한식음식점",
  "중식음식점",
  "일식음식점",
  "양식음식점",
  "제과점",
  "패스트푸드점",
  "치킨전문점",
  "분식전문점",
  "호프-간이주점",
  "커피-음료",
];

const PRICE_RANGES = [
  { label: "5천원 이하", value: "under5k" },
  { label: "5천-1만", value: "5to10k" },
  { label: "1-2만", value: "10to20k" },
  { label: "2만 이상", value: "over20k" },
];

const OPERATING_HOURS_OPTIONS = ["오전", "점심", "저녁", "심야"];

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
  survival: string;
  bep: string;
}

const CANNIBALIZATION_ROWS: CannRow[] = [
  { name: "연남파크점", distance: "450m", impact: "-2.1%", status: "Safe" },
  { name: "홍대입구역점", distance: "820m", impact: "-0.8%", status: "Safe" },
  { name: "망원시장점", distance: "1.2km", impact: "0.0%", status: "None" },
  { name: "신촌로터리점", distance: "2.4km", impact: "0.0%", status: "None" },
];

const NEIGHBORHOOD_ROWS: NeighborhoodRow[] = [
  { name: "연남동", score: "87 / 100", survival: "82%", bep: "3.5 개월" },
  { name: "서교동", score: "84 / 100", survival: "79%", bep: "4.1 개월" },
  { name: "망원동", score: "76 / 100", survival: "65%", bep: "5.2 개월" },
  { name: "합정동", score: "71 / 100", survival: "60%", bep: "6.0 개월" },
];

// 정렬용 값 추출 (문자열 컬럼은 그대로, 숫자 컬럼은 파싱)
function extractSortValue(row: Record<string, string>, key: string): number | string {
  const v = row[key];
  if (v === undefined || v === null) return ""; // 다른 뷰의 컬럼 키일 때 안전 fallback
  if (key === "distance") {
    // "450m" → 450, "1.2km" → 1200
    const num = parseFloat(v);
    return v.endsWith("km") ? num * 1000 : num;
  }
  // "-2.1%", "82%", "87 / 100", "3.5 개월" 모두 parseFloat로 첫 숫자 추출
  if (["impact", "score", "survival", "bep"].includes(key)) {
    return parseFloat(v);
  }
  return v; // name, status는 문자열 정렬
}

function sortRows<T extends Record<string, string>>(
  rows: T[],
  key: string | null,
  dir: "asc" | "desc"
): T[] {
  if (!key) return rows;
  return [...rows].sort((a, b) => {
    const av = extractSortValue(a, key);
    const bv = extractSortValue(b, key);
    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

/* ═══════════════════════════════════════════════════════
   DRILL-DOWN DRAWER MOCK DATA (v8.0)
   ⚠️ Frontend mockup. 백엔드 연동 시 SimulationOutput에서 직접 매핑.
   ═══════════════════════════════════════════════════════ */
type DrawerKey =
  | "revenue"
  | "attractiveness"
  | "traffic"
  | "cannibalization"
  | "insight_legal"
  | "insight_traffic"
  | "insight_target"
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
    title: "예상 월 매출 상세",
    aiReasoning:
      "유동인구 밀집도(상위 12%), 인근 동종업계 평균 매출액(2,800만) 대비 15% 초과 달성 예측. KT 통신 데이터 + 신용카드 매출 데이터 + LSTM 12개월 추세 모델 결합 분석.",
    confidence: "95%",
  },
  attractiveness: {
    title: "상권 종합 매력도 상세",
    aiReasoning:
      "7개 지표(유동인구·임대료·경쟁강도·매출추정·생존율·성장성·접근성)를 가중 평균. 마포구 25개 동 중 상권 매력도 상위 8% 권역.",
    rank: "마포구 내 상위 8%",
    trend: "+5.2 Pts 지속 상승중",
  },
  traffic: {
    title: "일평균 유동인구 상세",
    aiReasoning:
      "KT 통신사 셀룰러 데이터 기반 시간대별 체류 인구 측정. 18-21시 피크, 점심시간(12-14시) 보조 피크. 2030 여성 비중이 평균 대비 23% 높음.",
    peakTime: "18:00 - 21:00",
    mainTarget: "2030 여성 (68%)",
  },
  cannibalization: {
    title: "카니발리제이션 위험 상세",
    aiReasoning:
      "반경 500m 이내 동일 프랜차이즈 매장 진입 시 기존 매장 매출 감소율을 시뮬레이션. 거리 가중치 + 배후 세대 중첩률을 통합 산출.",
    warning: "반경 500m 내 동일 프랜차이즈 1개점 존재 (영향도 12%)",
  },
  insight_legal: {
    title: "상가임대차보호법 상세 분석",
    aiReasoning:
      "해당 권역 최근 3년 임대료 상승률 5.4%. 환산보증금 기준 초과 위기 매물 다수 감지. 계약 갱신 청구권 행사 시 법적 분쟁 가능성 높음. Legal Node가 14개 영역 3,775개 판례·법령 청크에서 유사 사례 검색.",
    warning: "환산보증금 한도 초과 위기 — 갱신 청구 시 임대인 거절 사유 발생 가능",
  },
  insight_traffic: {
    title: "저녁 시간대 매출 집중 분석",
    aiReasoning:
      "18시 이후 유동인구가 평균 대비 240% 증가. 인근 직장인 퇴근 동선 + 2030 여성 데이트 수요가 결합된 권역. 점심 매출이 약한 만큼, 저녁 메뉴 강화가 핵심 KPI.",
    peakTime: "18:00 - 21:00",
    mainTarget: "직장인 + 2030 여성",
  },
  insight_target: {
    title: "2030 여성 타겟 권역 분석",
    aiReasoning:
      "체류 인구 분석 결과 25-34세 여성 비중 68%. SNS 인스타그래머블 인테리어 + 디저트 메뉴 강화 시 객단가 +18%, 재방문율 +24% 예상.",
    confidence: "82%",
    mainTarget: "25-34세 여성 (68%)",
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
  const particlesRef = useRef<
    { x: number; y: number; vx: number; vy: number }[]
  >([]);
  const animRef = useRef<number>(0);
  const mouseRef = useRef<{ x: number; y: number }>({ x: -9999, y: -9999 });
  const pingRef = useRef<{ x: number; y: number; t: number }[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const onMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };
    const onClick = (e: MouseEvent) => {
      pingRef.current.push({ x: e.clientX, y: e.clientY, t: 0 });
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("click", onClick);

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
      else if (scene === "simulator") speedMult = 0.2;

      const isLight = scene === "simulator" && theme === "light";
      const r = isLight ? 99 : 129;
      const g = isLight ? 102 : 140;
      const b = isLight ? 241 : 248;

      const isIntro = scene === "intro";
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
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("click", onClick);
    };
  }, [isTransitioning, scene, theme]);

  const simClass =
    scene === "simulator"
      ? "scale-110 opacity-40"
      : "scale-100 opacity-100";

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
  onJoinUsClick,
  onSimulatorClick,
  onContactClick,
}: {
  activeMenuIndex: number;
  setActiveMenuIndex: (i: number) => void;
  onAboutClick: () => void;
  onJoinUsClick: () => void;
  onSimulatorClick: () => void;
  onContactClick: () => void;
}) {
  return (
    <div className="relative z-10 h-full w-full overflow-hidden">
      {/* Background Watermark Logo (idea 5) — 화면을 가로지르는 거대한 반투명 로고 */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
        <img
          src="/logo.svg"
          alt=""
          className="w-[90vw] max-w-[1400px] h-auto opacity-[0.018]"
        />
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
            0{activeMenuIndex + 1} / 04 — GET TO KNOW
          </span>
        </div>

        {/* Menu — 균일 사이즈, 일렬 정렬 */}
        <nav className="flex flex-col gap-3">
          {MENU_ITEMS.map((item, i) => {
            const isActive = activeMenuIndex === i;
            return (
              <button
                key={item}
                className="relative text-left group self-start whitespace-nowrap"
                style={{ width: "fit-content", maxWidth: "fit-content" }}
                onMouseEnter={() => setActiveMenuIndex(i)}
                onClick={() => {
                  if (i === 0) onAboutClick();
                  if (i === 1) onJoinUsClick();
                  if (i === 2) onSimulatorClick();
                  if (i === 3) onContactClick();
                }}
              >
                {/* Indicator bar */}
                <div
                  className={`absolute -left-10 top-1/2 -translate-y-1/2 w-1.5 h-[80%] bg-[#818cf8] rounded-full transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] origin-top ${
                    isActive ? "scale-x-100" : "scale-x-0"
                  }`}
                />
                <span
                  className={`inline-block text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-black uppercase tracking-tight leading-none whitespace-nowrap origin-left transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                    isActive
                      ? "text-[#e2e8f0] translate-x-0"
                      : "text-[#3a3633] -translate-x-2 group-hover:text-[#9ca3af]"
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
    track.addEventListener("wheel", handler, { passive: false });
    return () => track.removeEventListener("wheel", handler);
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
    [isDragging]
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
            <span className="text-sm font-bold tracking-wider text-[#e2e8f0]">
              SPOTTER
            </span>
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
                    ? "bg-indigo-400 scale-y-150 shadow-[0_0_10px_rgba(99,102,241,0.5)]"
                    : "bg-white/20"
                }`}
              />
            ))}
          </div>
          <span className="ml-3 text-xs text-gray-400 font-mono tabular-nums min-w-[80px]">
            {hoveredIdx !== null
              ? `${DISTRICTS[hoveredIdx].name} ${hoveredIdx + 1}`
              : "25 Districts"}{" "}
            / 25
          </span>
        </div>

        {/* Right — Guide text */}
        <div className="min-w-[180px] text-right">
          <span className="text-xs text-gray-600 tracking-widest">
            SCROLL TO EXPLORE
          </span>
        </div>
      </div>

      {/* Gallery track */}
      <div
        ref={trackRef}
        className={`flex-1 flex items-center gap-2 md:gap-3 overflow-x-auto scrollbar-hide px-4 ${
          isDragging ? "cursor-grabbing" : "cursor-grab"
        }`}
        onMouseDown={handleMouseDown}
      >
          {DISTRICTS.map((d, i) => {
            const isHovered = hoveredIdx === i;
            const isMapo = i === MAPO_IDX;

            return (
              <div
                key={d.eng}
                className={`group/panel relative h-[65vh] shrink-0 rounded-2xl overflow-hidden cursor-pointer bg-[#3a3633] transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                  isHovered
                    ? "w-[320px] md:w-[480px] z-10 shadow-[0_0_30px_rgba(129,140,248,0.3)]"
                    : "w-[70px] md:w-[80px] z-0"
                }`}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
                onClick={() => {
                  if (isMapo && !isDragging) onMapoClick();
                }}
              >
                {/* 1. Animated Gradient Border — 호버 시에만 회전 빛 표시 */}
                <div
                  className={`absolute inset-[-50%] z-0 animate-spin-slow transition-opacity duration-500 ${
                    isHovered ? "opacity-100" : "opacity-0"
                  }`}
                  style={{
                    background:
                      "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
                  }}
                />

                {/* 2. 실제 컨텐츠 컨테이너 (2px 인셋으로 테두리만 노출) */}
                <div
                  className={`absolute inset-[2px] z-10 overflow-hidden rounded-[14px] transition-colors duration-500 ${
                    isHovered ? "bg-[#2c2825]" : "bg-[#1e1b18]"
                  }`}
                >
                {/* Parallax background image */}
                <div
                  className={`absolute inset-0 w-full h-full bg-contain bg-center bg-no-repeat transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                    isHovered
                      ? "scale-100 opacity-80 grayscale-0"
                      : "scale-[0.9] opacity-30 grayscale-0"
                  }`}
                  style={{ backgroundImage: `url(${d.img})` }}
                />

                {/* Gradient mask */}
                <div className="absolute inset-0 bg-gradient-to-t from-[#1e1b18] via-[#1e1b18]/60 to-transparent opacity-90 transition-opacity duration-1000" />

                {/* District number */}
                <div
                  className={`absolute top-6 left-0 right-0 text-center font-mono text-xs transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                    isHovered ? "text-gray-400 opacity-100" : "text-gray-600 opacity-0"
                  }`}
                >
                  {String(i + 1).padStart(2, "0")}
                </div>

                {/* English name (shown on hover) */}
                <div
                  className={`absolute top-12 left-6 right-6 transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                    isHovered
                      ? "opacity-100 translate-y-0"
                      : "opacity-0 translate-y-4"
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
                      isHovered
                        ? "opacity-100 translate-y-0"
                        : "opacity-0 translate-y-4"
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
                      {d.name.split("").map((char, ci) => (
                        <span
                          key={ci}
                          className={`font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-white to-[#a3a3a3] transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] ${
                            isHovered
                              ? "text-4xl md:text-5xl opacity-100 translate-y-0 blur-0"
                              : "text-4xl md:text-5xl opacity-0 translate-y-10 blur-[4px]"
                          }`}
                          style={{
                            transitionDelay: isHovered
                              ? `${ci * 40 + 100}ms`
                              : "0ms",
                          }}
                        >
                          {char}
                        </span>
                      ))}
                    </h2>

                    {/* Default: vertical stacked staggered text */}
                    <h2 className="absolute left-1/2 -translate-x-1/2 bottom-10 md:bottom-12 flex flex-col items-center gap-1">
                      {d.name.split("").map((char, ci) => (
                        <span
                          key={ci}
                          className={`font-black text-transparent bg-clip-text bg-gradient-to-b from-white to-[#a3a3a3] leading-none transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] ${
                            isHovered
                              ? "text-2xl md:text-3xl opacity-0 -translate-y-10 blur-[4px]"
                              : "text-2xl md:text-3xl opacity-60 translate-y-0 blur-0"
                          }`}
                          style={{
                            transitionDelay: isHovered
                              ? "0ms"
                              : `${ci * 40 + 100}ms`,
                          }}
                        >
                          {char}
                        </span>
                      ))}
                    </h2>

                    {/* Bottom info (shown on hover) */}
                    <div
                      className={`absolute left-0 bottom-0 flex flex-col items-start transition-all duration-[1000ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                        isHovered
                          ? "opacity-100 translate-y-0 delay-[300ms]"
                          : "opacity-0 translate-y-4 pointer-events-none"
                      }`}
                    >
                      {isMapo ? (
                        <div className="flex items-center gap-2 text-indigo-300 text-sm">
                          <Play size={14} />
                          <span>클릭하여 시뮬레이션 시작</span>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-500">
                          서비스 준비 중
                        </span>
                      )}
                    </div>
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
    num: "01",
    title: "카니발리제이션(자기잠식) 분석",
    desc: "같은 브랜드 기존 매장과의 영향권 중첩을 계산하여 매출 잠식률을 산출합니다. \"3호점을 내면 1호점 매출이 얼마나 깎이는가?\"에 대한 정량적 답을 제시합니다.",
  },
  {
    num: "02",
    title: "간접 경쟁(대체재) 분석",
    desc: "치킨집의 경쟁상대는 옆 치킨집만이 아닙니다. 피자·족발·배달 야식 등 소비 카테고리 전체의 경쟁 강도를 가중치 기반으로 반영합니다.",
  },
  {
    num: "03",
    title: "What-if 시나리오 시뮬레이션",
    desc: "경쟁 매장 진입, 최저임금 변화, 임대료 상승 등 조건을 변경하면 즉시 재시뮬레이션합니다. 미래의 불확실성을 데이터로 대비하세요.",
  },
  {
    num: "04",
    title: "12개월 시간 축 예측",
    desc: "단순 스냅샷이 아닌, 12개월간의 매출 추이·경쟁 반응·생존 확률을 시계열로 예측합니다.",
  },
  {
    num: "05",
    title: "법률 리스크 AI 검토 (RAG)",
    desc: "가맹사업법 영업지역 보호, 상가임대차보호법 위반 여부를 AI가 자동으로 검토하여 법적 리스크를 사전에 차단합니다.",
  },
];

const COMPARISONS = [
  { old: "현재 상권 스냅샷만 제공", arrow: "→", now: "12개월 미래 예측 시뮬레이션" },
  { old: "같은 업종 경쟁만 분석", arrow: "→", now: "간접 경쟁(대체재)까지 반영" },
  { old: "자기잠식 분석 불가", arrow: "→", now: "카니발리제이션 정량 산출" },
  { old: "컨설팅 비용 수천만 원", arrow: "→", now: "AI 기반 즉시 분석" },
  { old: "정적 리포트 1회 제공", arrow: "→", now: "What-if 무제한 재시뮬레이션" },
  { old: "법률 리스크 수동 검토", arrow: "→", now: "RAG 기반 자동 법률 검토" },
];

const DATA_SOURCES = [
  "소상공인시장진흥공단",
  "서울 생활인구 (KT)",
  "통계청 SGIS",
  "국토부 실거래가",
  "공정위 정보공개서",
  "서울 상권분석 (golmok)",
  "Naver DataLab",
];

const ROADMAP = [
  { phase: "NOW", label: "서울시 마포구 16개 행정동 분석 지원" },
  { phase: "NEXT", label: "서울 전체 25개 구 확장 + 프랜차이즈 브랜드 DB 고도화" },
  { phase: "FUTURE", label: "전국 단위 확장 + 실시간 매출 데이터 연동 + B2B SaaS 출시" },
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
            <span className="text-sm font-bold tracking-wider text-[#e2e8f0]">
              SPOTTER
            </span>
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
            기존 상권분석 도구는{" "}
            <span className="text-[#818cf8] font-bold text-2xl md:text-3xl">
              '지금'
            </span>
            만 보여줍니다.
          </p>

          <div className="flex flex-col gap-4 my-10">
            {[
              "이 자리에 매장을 내면, 1년 뒤 매출은 얼마일까?",
              "같은 브랜드 3호점이 1호점 매출을 얼마나 잡아먹을까?",
              "옆에 경쟁 매장이 들어오면, 내 생존 확률은?",
            ].map((q, i) => (
              <div
                key={i}
                className="border-l-2 border-indigo-500 pl-6 py-2"
                style={{ animationDelay: `${i * 150 + 300}ms` }}
              >
                <p className="text-xl md:text-2xl font-medium text-[#e2e8f0]/80 italic">
                  "{q}"
                </p>
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
                <h4 className="text-xl font-bold text-[#e2e8f0] mb-3 relative z-10">
                  {f.title}
                </h4>
                <p className="text-[#9ca3af] leading-relaxed relative z-10">
                  {f.desc}
                </p>
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
                <span className="text-[#3a3633] font-mono mx-6 shrink-0">
                  {c.arrow}
                </span>
                <span className="text-indigo-400 font-bold text-lg flex-1 text-right">
                  {c.now}
                </span>
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
                    <p className="text-[#e2e8f0] leading-relaxed">
                      {r.label}
                    </p>
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
            <span className="text-sm font-bold tracking-wider text-[#e2e8f0]">
              SPOTTER
            </span>
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
            style={{ animation: "fadeSlideIn 1s ease-out" }}
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
              AI 기반 프랜차이즈 상권분석 시뮬레이터 프로젝트에 대한 상세한
              코드와 기획 문서는 아래 워크스페이스에서 확인하실 수 있습니다.
            </p>
          </div>

          {/* Right — Bento Box */}
          <div className="lg:col-span-7 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Card 1: Workspace — full width */}
            <div
              className="group/card md:col-span-2 relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: "fadeSlideIn 1s ease-out 100ms both" }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
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
                        "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
                    }}
                  />
                  <a
                    href="https://github.com/Himidea-AI/Final_Project"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                  >
                    <div className="flex items-center gap-3">
                      <GitFork size={18} className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors" />
                      <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">GitHub</span>
                    </div>
                    <ExternalLink size={14} className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors" />
                  </a>
                </div>
                <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                  <div
                    className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                    style={{
                      background:
                        "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
                    }}
                  />
                  <a
                    href="https://www.notion.so/333ac2a0181b802b807cf7de2447b890"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                  >
                    <div className="flex items-center gap-3">
                      <ExternalLink size={18} className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors" />
                      <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">Notion</span>
                    </div>
                    <ExternalLink size={14} className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors" />
                  </a>
                </div>
                <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                  <div
                    className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                    style={{
                      background:
                        "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
                    }}
                  />
                  <a
                    href="https://www.figma.com/board/lkjvfmKP4FU5XWBAyWR52a/%EC%A0%9C%EB%AA%A9-%EC%97%86%EC%9D%8C?node-id=0-1&p=f&t=ZITF88ooGHZ2rrHV-0"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                  >
                    <div className="flex items-center gap-3">
                      <ExternalLink size={18} className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors" />
                      <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">Figma</span>
                    </div>
                    <ExternalLink size={14} className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors" />
                  </a>
                </div>
                <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                  <div
                    className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                    style={{
                      background:
                        "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
                    }}
                  />
                  <a
                    href="https://bat981120.atlassian.net/jira/software/projects/IM3/boards/2"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                  >
                    <div className="flex items-center gap-3">
                      <ExternalLink size={18} className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors" />
                      <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">Jira</span>
                    </div>
                    <ExternalLink size={14} className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors" />
                  </a>
                </div>
              </div>
              </div>
            </div>

            {/* Card 2: Team Info */}
            <div
              className="group/card relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: "fadeSlideIn 1s ease-out 200ms both" }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
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
              style={{ animation: "fadeSlideIn 1s ease-out 300ms both" }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
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
              style={{ animation: "fadeSlideIn 1s ease-out 400ms both" }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
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
   runSim() → runSimulation() + analyzeLocation() 동시 호출
   응답 → SimResult로 변환 → UI 바인딩
   USE_MOCK=true 시 현실적 Mock 데이터 반환 (2.5초 딜레이)
   API 실패 시 fallback Mock 표시 (에러에도 화면 유지)

   [팀원 참고 — B1/A1]
   SimulationOutput.comparison 배열 → 동별 비교 테이블 데이터
   SimulationOutput.legal_risks 배열 → AI 인사이트 법률 경고
   AnalysisResult.data.market_report → 7개 항목별 차트 데이터
*/

function SimulatorDashboard({
  reportState,
  setReportState,
}: {
  reportState: string;
  setReportState: (s: "idle" | "loading" | "result") => void;
}) {
  const [radius, setRadius] = useState(500);
  const [budget, setBudget] = useState(200);
  const [weighted, setWeighted] = useState(true);
  const [loadingText, setLoadingText] = useState("INITIALIZING AI ENGINE...");
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  const [chartView, setChartView] = useState<"daily" | "monthly">("daily");
  const [tableView, setTableView] = useState<"cannibalization" | "neighborhoods">("cannibalization");
  const [isDownloadOpen, setIsDownloadOpen] = useState(false);
  const [selectedGu] = useState("마포구");
  const [selectedDongs, setSelectedDongs] = useState<string[]>(
    () => [...DONG_DATA["마포구"]]
  );
  const [dongDropdownOpen, setDongDropdownOpen] = useState(false);

  // [Frontend Mockup] 백엔드 연동 보류 — SimulationInput 확장 후 페이로드 매핑 필요
  const [businessType, setBusinessType] = useState("커피-음료");
  const [businessTypeOpen, setBusinessTypeOpen] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [storeArea, setStoreArea] = useState(15); // 평
  const [targetPrice, setTargetPrice] = useState("5to10k");
  const [operatingHours, setOperatingHours] = useState<string[]>(["점심", "저녁"]);
  const [initialCapital, setInitialCapital] = useState(5000); // 만원

  // [v8.0/v8.1] Drill-down Drawer + 테이블 행 확장 + 정렬 상태
  const [activeDrawer, setActiveDrawer] = useState<DrawerKey>(null);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortDir(sortDir === "asc" ? "desc" : "asc");
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
      setExpandedRow(null); // 정렬 변경 시 펼침 초기화
    },
    [sortKey, sortDir]
  );

  // 테이블 뷰 변경 시 정렬/펼침 초기화 헬퍼
  const handleTableViewChange = useCallback(
    (view: "cannibalization" | "neighborhoods") => {
      setTableView(view);
      setSortKey(null);
      setExpandedRow(null);
    },
    []
  );

  // 정렬된 행 데이터 (Mock)
  const sortedCannRows = sortRows(CANNIBALIZATION_ROWS, sortKey, sortDir);
  const sortedNeighborhoodRows = sortRows(NEIGHBORHOOD_ROWS, sortKey, sortDir);

  // 오늘 날짜 (리포트 생성 시점)
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, "0");
  const dd = String(today.getDate()).padStart(2, "0");
  const reportMonthLabel = `${yyyy}. ${mm}.`;
  const reportFullDate = `${yyyy}.${mm}.${dd}`;

  // [v12.0] PDF/Excel 다운로드용 ref + 로딩 상태
  const pdfTemplateRef = useRef<HTMLDivElement>(null);
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);

  const handleDownloadPDF = useCallback(async () => {
    if (!pdfTemplateRef.current) return;
    setIsDownloadOpen(false);
    setIsGeneratingPDF(true);

    try {
      const template = pdfTemplateRef.current;
      const pages = Array.from(template.children) as HTMLElement[];

      const pdf = new jsPDF("p", "mm", "a4");
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();

      for (let i = 0; i < pages.length; i++) {
        const canvas = await html2canvas(pages[i], {
          scale: 2,
          useCORS: true,
          backgroundColor: "#ffffff",
          logging: false,
        });
        const imgData = canvas.toDataURL("image/png");
        if (i > 0) pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, 0, pdfWidth, pdfHeight);
      }

      const dateStr = reportFullDate.replace(/\./g, "");
      const districtName = selectedDongs[0] || "연남동";
      pdf.save(`SPOTTER_마포구_${districtName}_${dateStr}.pdf`);
    } catch (error) {
      console.error("PDF Generation Failed:", error);
      alert("PDF 생성 중 오류가 발생했습니다.");
    } finally {
      setIsGeneratingPDF(false);
    }
  }, [reportFullDate, selectedDongs]);

  const handleDownloadExcel = useCallback(() => {
    setIsDownloadOpen(false);
    const districtName = selectedDongs[0] || "연남동";

    const wb = XLSX.utils.book_new();

    // Sheet 1: 요약
    const summary: (string | number)[][] = [
      ["SPOTTER · AI Franchise Intelligence Report"],
      [],
      ["분석 대상", `마포구 ${districtName}`],
      ["생성 일시", reportFullDate],
      ["Document ID", `SPTR-${Date.now().toString().slice(-8)}`],
      [],
      ["KPI 요약"],
      ["지표", "값", "트렌드"],
      ["예상 월 매출 (추정)", `₩ ${((simResult?.revenue ?? 3240) * 10000).toLocaleString()}`, "+12.5%"],
      ["상권 종합 매력도", `${simResult?.score ?? 87} / 100`, "+5.2 Pts"],
      ["일평균 유동인구", "42,105 명", "-2.4%"],
      ["카니발리제이션 위험", `${simResult?.riskLevel ?? "Low"} (12%)`, "안전 권역"],
      [],
      ["7 Core Metrics (레이더 차트)"],
      ["항목", "점수"],
      ...(simResult?.chartData ?? CHART_DATA).map((d) => [d.label, d.value]),
    ];
    const ws1 = XLSX.utils.aoa_to_sheet(summary);
    ws1["!cols"] = [{ wch: 25 }, { wch: 25 }, { wch: 15 }];
    XLSX.utils.book_append_sheet(wb, ws1, "요약");

    // Sheet 2: 가맹점 간섭도
    const cann: (string | number)[][] = [
      ["가맹점명", "거리", "예상 매출 하락", "상태"],
      ...CANNIBALIZATION_ROWS.map((r) => [r.name, r.distance, r.impact, r.status]),
    ];
    const ws2 = XLSX.utils.aoa_to_sheet(cann);
    ws2["!cols"] = [{ wch: 20 }, { wch: 12 }, { wch: 15 }, { wch: 12 }];
    XLSX.utils.book_append_sheet(wb, ws2, "가맹점 간섭도");

    // Sheet 3: 행정동 비교
    const neighborhoods: (string | number)[][] = [
      ["행정동", "AI 점수", "생존율", "예상 BEP"],
      ...NEIGHBORHOOD_ROWS.map((r) => [r.name, r.score, r.survival, r.bep]),
    ];
    const ws3 = XLSX.utils.aoa_to_sheet(neighborhoods);
    ws3["!cols"] = [{ wch: 15 }, { wch: 12 }, { wch: 12 }, { wch: 15 }];
    XLSX.utils.book_append_sheet(wb, ws3, "행정동 비교");

    // Sheet 4: AI 인사이트
    const insights: (string | number)[][] = [
      ["SPOTTER AI 인사이트 — LangGraph Multi-Agent"],
      [],
      ["Severity", "Title", "Description"],
      [
        "ADVISORY",
        "저녁 시간대 매출 집중형",
        "18시 이후 유동인구가 급증. 야간 메뉴 강화를 권장합니다.",
      ],
      [
        "CRITICAL",
        "법률 리스크 경고 (Legal Node)",
        simResult?.recommendation ||
          "상가임대차보호법 위반 사례 존재 권역. 최근 3년 평균 임대료 인상률이 5%를 초과하여 계약 갱신 시 법적 분쟁 리스크가 감지되었습니다.",
      ],
      [
        "OPPORTUNITY",
        "2030 여성 타겟 구역",
        "SNS 친화적 인테리어 도입 시 수익 창출 확률 34% 증가.",
      ],
    ];
    const ws4 = XLSX.utils.aoa_to_sheet(insights);
    ws4["!cols"] = [{ wch: 12 }, { wch: 30 }, { wch: 60 }];
    XLSX.utils.book_append_sheet(wb, ws4, "AI 인사이트");

    const dateStr = reportFullDate.replace(/\./g, "");
    XLSX.writeFile(wb, `SPOTTER_마포구_${districtName}_${dateStr}.xlsx`);
  }, [reportFullDate, selectedDongs, simResult]);

  const toggleOperatingHour = useCallback((hour: string) => {
    setOperatingHours((prev) =>
      prev.includes(hour) ? prev.filter((h) => h !== hour) : [...prev, hour]
    );
  }, []);

  // 결과 화면 진입 시 스크롤을 맨 위로 리셋 (리포트 최상단부터 보이도록)
  const dashboardRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (reportState === "result" && dashboardRef.current) {
      dashboardRef.current.scrollTop = 0;
    }
  }, [reportState]);

  // 브라우저 뒤로가기 가로채기 — result 상태에서 뒤로가기 누르면 페이지 이탈 대신 idle로 복귀
  useEffect(() => {
    if (reportState !== "result") return;
    // 가짜 history 엔트리 추가 → 뒤로가기 시 popstate 발생
    window.history.pushState({ simResult: true }, "");
    const handlePopState = () => {
      setReportState("idle");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
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
    setReportState("loading");
    try {
      const [simRes, analysisRes] = await Promise.all([
        runSimulation({
          business_type: "cafe",
          brand_name: "",
          target_district: selectedDongs[0] || "서교동",
          existing_stores: [],
          initial_investment: budget * 10000,
          monthly_rent: budget * 10000,
          simulation_months: 12,
          scenarios: [],
        }),
        analyzeLocation({
          business_type: "cafe",
          brand_name: "",
          target_district: selectedDongs[0] || "서교동",
          existing_stores: [],
          initial_investment: budget * 10000,
          monthly_rent: budget * 10000,
          simulation_months: 12,
          scenarios: [],
        }),
      ]);

      const mr = analysisRes.data?.market_report;
      const topComp = simRes.comparison?.[0];
      const topRisk = simRes.legal_risks?.[0];

      setSimResult({
        score: topComp?.score ?? 87,
        revenue: topComp?.revenue ?? 3240,
        riskLevel: topRisk?.risk_level ?? "LOW",
        recommendation: simRes.ai_recommendation || "",
        chartData: mr
          ? [
              { label: "유동인구", value: mr.floating_population },
              { label: "임대료", value: mr.rent_index },
              { label: "경쟁강도", value: mr.competition_intensity },
              { label: "매출추정", value: mr.estimated_revenue },
              { label: "생존율", value: mr.survival_rate },
              { label: "성장성", value: mr.growth_potential },
              { label: "접근성", value: mr.accessibility },
            ]
          : CHART_DATA,
      });
      setReportState("result");
    } catch (err) {
      console.error("Simulation failed:", err);
      // Fallback — 에러 시에도 결과 화면 표시 (Mock 수준)
      setSimResult({
        score: 87,
        revenue: 3240,
        riskLevel: "HIGH",
        recommendation: "API 연결 실패 — Mock 데이터를 표시합니다.",
        chartData: CHART_DATA,
      });
      setReportState("result");
    }
  }, [setReportState, selectedDongs, budget]);

  // Loading streaming text
  useEffect(() => {
    if (reportState !== "loading") return;
    const texts = [
      "FETCHING KT TELECOM DATA...",
      "ANALYZING CANNIBALIZATION RATE...",
      "CALCULATING RENT-TO-REVENUE RATIO...",
      "RUNNING WHAT-IF SCENARIOS...",
      "CROSS-CHECKING LEGAL RISKS...",
      "GENERATING 12-MONTH FORECAST...",
    ];
    let i = 0;
    const interval = setInterval(() => {
      setLoadingText(texts[i % texts.length]);
      i++;
    }, 400);
    return () => clearInterval(interval);
  }, [reportState]);

  // Dark theme only
  const textPrimary = "text-[#e2e8f0]";
  const textSecondary = "text-[#9ca3af]";
  const accent = "text-[#818cf8]";
  const accentBg = "bg-[#818cf8]";
  const panel = "bg-[#2c2825] border-[#3a3633] shadow-2xl";
  const inputTrack = "accent-[#818cf8]";

  return (
    <div ref={dashboardRef} className="relative z-10 h-full w-full bg-[#1e1b18] overflow-y-auto custom-scrollbar">
      {/* Top bar */}
      <div className="sticky top-0 z-30 flex items-center px-8 py-4 mt-14 bg-[#1e1b18]/80 backdrop-blur-xl">
        <span className={`text-xs font-medium tracking-wider ${textSecondary}`}>
          마포구 시뮬레이터
        </span>
      </div>

      {/* Dashboard body */}
      <div className="flex flex-col lg:flex-row gap-6 p-8 max-w-7xl mx-auto">
        {/* Left panel — Controls (result 상태일 땐 숨김 → 우측 리포트가 full-width로 확장) */}
        <div className={`lg:w-[380px] shrink-0 rounded-2xl border p-6 transition-all duration-700 ${panel} ${reportState === "result" ? "hidden" : ""}`}>
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
              <label className={`text-xs font-medium ${textSecondary}`}>
                분석 대상
              </label>
            </div>

            {/* 구 — 고정 (explore에서 선택된 구, 변경 불가) */}
            <div className="mb-2 px-3 py-2.5 rounded-lg border border-[#3a3633] bg-[#1e1b18]/50 flex items-center justify-between">
              <span className="text-sm text-[#e2e8f0]">{selectedGu}</span>
              <span className="text-[10px] text-[#9ca3af] uppercase tracking-wider opacity-70">선택됨</span>
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
                    dongDropdownOpen ? "rotate-90" : ""
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
                      ? "전체 해제"
                      : "전체 선택"}
                  </button>
                  {DONG_DATA[selectedGu].map((dong) => {
                    const checked = selectedDongs.includes(dong);
                    return (
                      <button
                        key={dong}
                        onClick={() => toggleDong(dong)}
                        className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                          checked
                            ? "text-[#e2e8f0] hover:bg-[#3a3633]"
                            : "text-[#666666] hover:bg-[#3a3633] hover:text-[#9ca3af]"
                        }`}
                      >
                        <div
                          className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                            checked
                              ? "bg-[#818cf8] border-[#818cf8]"
                              : "border-[#3a3633] bg-transparent"
                          }`}
                        >
                          {checked && (
                            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                              <path d="M1.5 4L3 5.5L6.5 2" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
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
              <label className={`text-xs font-medium ${textSecondary}`}>
                업종
              </label>
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
                    businessTypeOpen ? "rotate-90" : ""
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
                          ? "text-[#818cf8] bg-[#818cf8]/10"
                          : "text-[#9ca3af] hover:text-[#e2e8f0] hover:bg-[#3a3633]"
                      }`}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ─────────── 분석 조건 (기존 sliders) ─────────── */}
          <div className="pt-5 border-t border-[#3a3633]">
            {/* Radius slider */}
            <div className="mb-6">
              <div className="flex justify-between mb-2">
                <label className={`text-xs font-medium ${textSecondary}`}>
                  상권 반경
                </label>
                <span className={`text-xs font-mono ${accent}`}>{radius}m</span>
              </div>
              <input
                type="range"
                min={100}
                max={1500}
                value={radius}
                onChange={(e) => setRadius(Number(e.target.value))}
                className={`w-full h-1.5 rounded-full appearance-none cursor-pointer ${inputTrack} bg-[#3a3633]`}
              />
              <div className={`flex justify-between text-[10px] mt-1 ${textSecondary}`}>
                <span>100m</span>
                <span>1500m</span>
              </div>
            </div>

            {/* Budget slider */}
            <div className="mb-6">
              <div className="flex justify-between mb-2">
                <label className={`text-xs font-medium ${textSecondary}`}>
                  임대료 예산
                </label>
                <span className={`text-xs font-mono ${accent}`}>{budget}만원</span>
              </div>
              <input
                type="range"
                min={50}
                max={1000}
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                className={`w-full h-1.5 rounded-full appearance-none cursor-pointer ${inputTrack} bg-[#3a3633]`}
              />
              <div className={`flex justify-between text-[10px] mt-1 ${textSecondary}`}>
                <span>50만</span>
                <span>1000만</span>
              </div>
            </div>

            {/* Toggle switch */}
            <div className="mb-2">
              <div className="flex items-center justify-between">
                <label className={`text-xs font-medium ${textSecondary}`}>
                  유동인구 가중치
                </label>
                <button
                  onClick={() => setWeighted(!weighted)}
                  className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${
                    weighted ? accentBg : "bg-[#3a3633]"
                  }`}
                >
                  <div
                    className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${
                      weighted ? "translate-x-[22px]" : "translate-x-0.5"
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
                <Settings size={13} className="text-[#9ca3af] group-hover:text-[#818cf8] transition-colors" />
                <span className={`text-xs font-medium ${textSecondary} group-hover:text-[#e2e8f0] transition-colors`}>
                  더 정확한 분석을 원하시나요?
                </span>
              </span>
              <ChevronDown
                size={14}
                className={`text-[#9ca3af] transition-transform duration-300 ${
                  showAdvanced ? "rotate-180" : ""
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
              showAdvanced ? "max-h-[1200px] opacity-100 mt-5" : "max-h-0 opacity-0 mt-0"
            }`}
          >
            <div className="p-4 rounded-xl border border-[#3a3633] bg-[#1e1b18]/50 space-y-6">
              {/* 1. 매장 면적 */}
              <div>
                <div className="flex justify-between mb-2">
                  <label className={`text-xs font-medium ${textSecondary}`}>
                    매장 면적
                  </label>
                  <span className={`text-xs font-mono ${accent}`}>{storeArea}평</span>
                </div>
                <input
                  type="range"
                  min={5}
                  max={100}
                  value={storeArea}
                  onChange={(e) => setStoreArea(Number(e.target.value))}
                  className={`w-full h-1.5 rounded-full appearance-none cursor-pointer ${inputTrack} bg-[#3a3633]`}
                />
                <div className={`flex justify-between text-[10px] mt-1 ${textSecondary}`}>
                  <span>5평</span>
                  <span>100평</span>
                </div>
              </div>

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
                            ? "bg-[#818cf8]/15 border-[#818cf8] text-[#818cf8]"
                            : "bg-transparent border-[#3a3633] text-[#9ca3af] hover:border-[#818cf8]/50 hover:text-[#e2e8f0]"
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
                  <label className={`text-xs font-medium ${textSecondary}`}>
                    주 타겟 시간대
                  </label>
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
                            ? "bg-[#818cf8]/15 border-[#818cf8] text-[#818cf8]"
                            : "bg-transparent border-[#3a3633] text-[#9ca3af] hover:border-[#818cf8]/50 hover:text-[#e2e8f0]"
                        }`}
                      >
                        {hour}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 4. 초기 자본금 */}
              <div>
                <div className="flex justify-between mb-2">
                  <label className={`text-xs font-medium ${textSecondary}`}>
                    초기 자본금
                  </label>
                  <span className={`text-xs font-mono ${accent}`}>
                    {initialCapital >= 10000
                      ? `${(initialCapital / 10000).toFixed(1)}억`
                      : `${initialCapital}만`}
                  </span>
                </div>
                <input
                  type="range"
                  min={1000}
                  max={50000}
                  step={500}
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(Number(e.target.value))}
                  className={`w-full h-1.5 rounded-full appearance-none cursor-pointer ${inputTrack} bg-[#3a3633]`}
                />
                <div className={`flex justify-between text-[10px] mt-1 ${textSecondary}`}>
                  <span>1천만</span>
                  <span>5억</span>
                </div>
              </div>

              <p className={`text-[10px] ${textSecondary} opacity-50 italic pt-2 border-t border-[#3a3633]/50`}>
                * 권리금/보증금 제외, 인테리어·초기 운영비 기준
              </p>
            </div>
          </div>

          {/* ─────────── RUN SIMULATION (맨 아래) ─────────── */}
          <button
            onClick={runSim}
            disabled={reportState === "loading"}
            className={`w-full mt-6 py-3.5 rounded-xl font-bold text-sm tracking-wider flex items-center justify-center gap-2 transition-all duration-300 ${
              reportState === "loading"
                ? "opacity-50 cursor-not-allowed"
                : "hover:scale-[1.02] active:scale-[0.98]"
            } bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:from-[#4f46e5] hover:to-[#6366f1]`}
          >
            <Play size={16} />
            RUN SIMULATION
          </button>
        </div>

        {/* Right panel — Visualization */}
        <div className={`flex-1 rounded-2xl border p-6 min-h-[500px] transition-all duration-700 ${panel}`}>
          {reportState === "idle" && (
            <div className="h-full flex flex-col items-center justify-center gap-4">
              <div
                className={`w-16 h-16 rounded-2xl flex items-center justify-center ${
                  "bg-[#1e1b18]"
                }`}
              >
                <BarChart3 size={28} className={textSecondary} />
              </div>
              <p className={`text-sm ${textSecondary}`}>
                조건을 설정하고 시뮬레이션을 실행하세요
              </p>
            </div>
          )}

          {reportState === "loading" && (
            <div className="h-full flex flex-col items-center justify-center">
              <div className="relative w-24 h-24 mb-8">
                {/* Double spinner */}
                <div className="absolute inset-0 border-4 border-[#3a3633] border-t-[#818cf8] rounded-full animate-[spin_2s_linear_infinite]" />
                <div className="absolute inset-2 border-4 border-[#3a3633] border-b-[#818cf8] rounded-full animate-[spin_3s_linear_infinite_reverse]" />
              </div>

              <div className="flex flex-col items-center gap-2">
                <p className={`font-mono text-xl font-black tracking-[0.2em] uppercase ${accent}`}>
                  PROCESSING DATA
                </p>
                <div className="px-4 py-2 mt-2 bg-black/10 rounded-md border border-[#3a3633]/30 backdrop-blur-sm flex items-center gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                  <p className={`font-mono text-xs tracking-widest ${textSecondary}`}>
                    [ {loadingText} ]
                  </p>
                </div>
              </div>
            </div>
          )}

          {reportState === "result" && (
            <div className="absolute inset-0 z-40 bg-[#1e1b18] text-[#e2e8f0] font-sans p-4 md:p-6 pt-28 md:pt-32 overflow-y-auto custom-scrollbar flex flex-col pb-12">
              <div className="max-w-[1600px] w-full mx-auto flex flex-col gap-6">

                {/* Header & Nav */}
                <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-4 shrink-0">
                  <div>
                    <div className="flex items-center gap-2 mb-1"><Zap className="w-5 h-5 text-indigo-400" /><h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">상권 분석 리포트</h1></div>
                    <p className="text-[#9ca3af] text-sm">서울특별시 마포구 {selectedDongs[0] || "연남동"} 일대 시뮬레이션 결과</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button className="flex items-center gap-2 px-3 py-1.5 border border-[#3a3633] bg-[#2c2825] hover:bg-[#3a3633] rounded-md text-xs font-medium transition-colors"><Calendar className="w-3.5 h-3.5 text-[#9ca3af]" /> {reportMonthLabel}</button>
                    <div className="relative">
                      <button
                        onClick={() => setIsDownloadOpen(!isDownloadOpen)}
                        disabled={isGeneratingPDF}
                        className="flex items-center gap-2 px-3 py-2 bg-transparent border border-indigo-500/60 text-indigo-400 hover:bg-indigo-500/10 hover:border-indigo-500 rounded-lg text-[11px] font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Download className="w-3.5 h-3.5" />
                        {isGeneratingPDF ? "생성 중..." : "다운로드"}
                        <ChevronDown className="w-3 h-3 ml-0.5 opacity-70" />
                      </button>
                      {isDownloadOpen && !isGeneratingPDF && (
                        <>
                          <div className="fixed inset-0 z-40" onClick={() => setIsDownloadOpen(false)} />
                          <div className="absolute right-0 mt-2 w-48 bg-[#1e1b18] border border-[#3a3633] rounded-lg shadow-2xl py-1.5 z-50 flex flex-col gap-0.5">
                            <button onClick={handleDownloadPDF} className="w-full text-left px-3 py-2 text-xs text-white hover:bg-[#2c2825] flex items-center gap-2 transition-colors group">
                              <FileText className="w-3.5 h-3.5 text-indigo-400 group-hover:scale-110 transition-transform" /> PDF 리포트 <span className="text-[10px] text-[#9ca3af] ml-auto">보고용</span>
                            </button>
                            <button onClick={handleDownloadExcel} className="w-full text-left px-3 py-2 text-xs text-[#9ca3af] hover:text-white hover:bg-[#2c2825] flex items-center gap-2 transition-colors group">
                              <Database className="w-3.5 h-3.5 text-indigo-400 group-hover:scale-110 transition-transform" /> Raw Data <span className="text-[10px] text-[#d1d5db] ml-auto">XLSX</span>
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* 4 Stats Cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
                  <StatCard onClick={() => setActiveDrawer("revenue")} title="예상 월 매출 (추정)" value={`₩ ${((simResult?.revenue ?? 3240) * 10000).toLocaleString()}`} trend="+12.5%" trendUp={true} icon={<BarChart3 />} sparkline="M 0 20 Q 10 5, 20 15 T 40 10 T 60 25 T 80 5 T 100 0" />
                  <StatCard onClick={() => setActiveDrawer("attractiveness")} title="상권 종합 매력도" value={`${simResult?.score ?? 87} / 100`} trend="+5.2 Pts" trendUp={true} icon={<Crosshair />} sparkline="M 0 25 Q 15 20, 30 10 T 60 15 T 80 5 T 100 0" />
                  <StatCard onClick={() => setActiveDrawer("traffic")} title="일평균 유동인구" value="42,105 명" trend="-2.4%" trendUp={false} icon={<Users />} sparkline="M 0 5 Q 15 10, 30 20 T 60 15 T 80 25 T 100 30" />
                  <StatCard onClick={() => setActiveDrawer("cannibalization")} title="카니발리제이션 위험" value={`${simResult?.riskLevel ?? "Low"} (12%)`} trend="안전 권역" trendUp={true} icon={<AlertTriangle className="text-indigo-400" />} sparkline="M 0 30 Q 20 25, 40 28 T 80 25 T 100 30" />
                </div>

                {/* Main Dashboard Body */}
                <div className="flex flex-col lg:flex-row gap-6">
                  {/* Left Column */}
                  <div className="lg:flex-[2] flex flex-col gap-6">
                    {/* Chart */}
                    <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 pb-10 shadow-xl flex flex-col h-[320px]">
                      <div className="flex justify-between items-end mb-4">
                        <div>
                          <h2 className="text-sm font-bold text-white">{chartView === "daily" ? "시간대별 유동인구 및 매출 (24H)" : "LSTM 12개월 매출 추이 예측 (12M)"}</h2>
                          <p className="text-[11px] text-[#9ca3af]">{chartView === "daily" ? "경쟁점 데이터 및 배후세대 동선 분석 기준" : "AI 엔진을 통한 향후 1년간의 매출 예측값"}</p>
                        </div>
                        <div className="flex bg-[#1e1b18] rounded-md border border-[#3a3633] p-0.5">
                          <button onClick={() => setChartView("daily")} className={`px-3 py-1 text-[10px] font-bold rounded transition-colors ${chartView === "daily" ? "bg-[#3a3633] text-indigo-400" : "text-[#9ca3af] hover:text-white"}`}>24H 분석</button>
                          <button onClick={() => setChartView("monthly")} className={`px-3 py-1 text-[10px] font-bold rounded transition-colors ${chartView === "monthly" ? "bg-[#3a3633] text-indigo-400" : "text-[#9ca3af] hover:text-white"}`}>12M 예측</button>
                        </div>
                      </div>
                      <div onClick={() => setActiveDrawer("traffic")} className="flex-1 relative w-full flex items-end cursor-pointer group/chart hover:bg-[#818cf8]/[0.03] rounded-lg transition-colors">
                        <svg viewBox="0 0 1000 300" className="absolute inset-0 w-full h-full pb-5 pl-2 overflow-visible group-hover/chart:[&_path]:drop-shadow-[0_0_4px_rgba(129,140,248,0.4)] transition-all" preserveAspectRatio="none">
                          {chartView === "daily" ? (
                            <>
                              <path d="M 0 280 C 100 280, 150 200, 250 180 C 350 160, 400 250, 500 240 C 600 230, 700 80, 800 100 C 900 120, 950 200, 1000 220 L 1000 300 L 0 300 Z" fill="url(#grayGradient)" opacity="0.3" />
                              <path d="M 0 280 C 100 280, 150 200, 250 180 C 350 160, 400 250, 500 240 C 600 230, 700 80, 800 100 C 900 120, 950 200, 1000 220" fill="none" stroke="#a3a3a3" strokeWidth="3" />
                              <path d="M 0 290 C 150 290, 200 150, 300 120 C 400 90, 450 200, 550 180 C 650 160, 750 40, 850 50 C 950 60, 980 150, 1000 160 L 1000 300 L 0 300 Z" fill="url(#indigoGradient)" opacity="0.4" />
                              <path d="M 0 290 C 150 290, 200 150, 300 120 C 400 90, 450 200, 550 180 C 650 160, 750 40, 850 50 C 950 60, 980 150, 1000 160" fill="none" stroke="#818cf8" strokeWidth="4" />
                            </>
                          ) : (
                            <>
                              <path d="M 0 150 L 90 140 L 181 160 L 272 120 L 363 110 L 454 90 L 545 100 L 636 70 L 727 60 L 818 80 L 909 50 L 1000 40 L 1000 300 L 0 300 Z" fill="url(#indigoGradient)" opacity="0.3" />
                              <path d="M 0 150 L 90 140 L 181 160 L 272 120 L 363 110 L 454 90 L 545 100 L 636 70 L 727 60 L 818 80 L 909 50 L 1000 40" fill="none" stroke="#818cf8" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                            </>
                          )}
                          <defs>
                            <linearGradient id="indigoGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#818cf8" stopOpacity="0.8" /><stop offset="100%" stopColor="#818cf8" stopOpacity="0" /></linearGradient>
                            <linearGradient id="grayGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#a3a3a3" stopOpacity="0.5" /><stop offset="100%" stopColor="#a3a3a3" stopOpacity="0" /></linearGradient>
                          </defs>
                        </svg>
                        <div className="absolute -bottom-3 left-0 w-full flex justify-between text-[10px] text-[#d1d5db] font-mono pl-2">
                          {chartView === "daily" ? <><span>06:00</span><span>10:00</span><span>14:00</span><span>18:00</span><span>22:00</span><span>02:00</span></> : <><span>1M</span><span>3M</span><span>6M</span><span>9M</span><span>12M</span></>}
                        </div>
                      </div>
                    </div>

                    {/* Table */}
                    <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl shadow-xl flex flex-col flex-1">
                      <div className="p-5 border-b border-[#3a3633] flex justify-between items-center">
                        <h2 className="text-sm font-bold text-white">상세 데이터 테이블</h2>
                        <div className="flex bg-[#1e1b18] rounded-md border border-[#3a3633] p-0.5">
                          <button onClick={() => handleTableViewChange("cannibalization")} className={`px-3 py-1 text-[10px] font-bold rounded transition-colors ${tableView === "cannibalization" ? "bg-[#3a3633] text-indigo-400" : "text-[#9ca3af] hover:text-white"}`}>가맹점 간섭도</button>
                          <button onClick={() => handleTableViewChange("neighborhoods")} className={`px-3 py-1 text-[10px] font-bold rounded transition-colors ${tableView === "neighborhoods" ? "bg-[#3a3633] text-indigo-400" : "text-[#9ca3af] hover:text-white"}`}>행정동 비교</button>
                        </div>
                      </div>
                      <div className="flex-1">
                        <table className="w-full text-left border-collapse">
                          <thead className="sticky top-0 bg-[#1e1b18]/90 backdrop-blur-sm z-10">
                            <tr className="text-[11px] font-mono text-[#9ca3af] uppercase tracking-wider">
                              {tableView === "cannibalization" ? (
                                <>
                                  <th className="p-3 pl-5 font-medium"><SortHeader label="가맹점명" sortField="name" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} /></th>
                                  <th className="p-3 font-medium"><SortHeader label="거리" sortField="distance" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} /></th>
                                  <th className="p-3 font-medium"><SortHeader label="예상 매출 하락" sortField="impact" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} /></th>
                                  <th className="p-3 font-medium"><SortHeader label="상태" sortField="status" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} /></th>
                                </>
                              ) : (
                                <>
                                  <th className="p-3 pl-5 font-medium"><SortHeader label="행정동" sortField="name" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} /></th>
                                  <th className="p-3 font-medium"><SortHeader label="AI 점수" sortField="score" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} /></th>
                                  <th className="p-3 font-medium"><SortHeader label="생존율" sortField="survival" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} /></th>
                                  <th className="p-3 font-medium"><SortHeader label="예상 BEP" sortField="bep" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} /></th>
                                </>
                              )}
                            </tr>
                          </thead>
                          <tbody className="text-xs divide-y divide-[#3a3633]">
                            {tableView === "cannibalization"
                              ? sortedCannRows.map((row, i) => (
                                  <TableRow
                                    key={row.name}
                                    index={i}
                                    expanded={expandedRow === i}
                                    onToggle={() => setExpandedRow(expandedRow === i ? null : i)}
                                    icon={<Store className="w-3.5 h-3.5" />}
                                    col1={row.name}
                                    col2={row.distance}
                                    col3={row.impact}
                                    status={row.status}
                                  />
                                ))
                              : sortedNeighborhoodRows.map((row, i) => (
                                  <TableRow
                                    key={row.name}
                                    index={i}
                                    expanded={expandedRow === i}
                                    onToggle={() => setExpandedRow(expandedRow === i ? null : i)}
                                    icon={<MapPin className="w-3.5 h-3.5" />}
                                    col1={row.name}
                                    col2={row.score}
                                    col3={row.survival}
                                    status={row.bep}
                                  />
                                ))}
                          </tbody>
                        </table>
                      </div>
                      {/* Footer — 빈 공간을 채우는 메타 정보 */}
                      <div className="px-5 py-3 border-t border-[#3a3633] flex justify-between items-center text-[10px] font-mono text-[#9ca3af]">
                        <span>총 4건 · {tableView === "cannibalization" ? "가맹점 간섭도 분석" : "행정동 비교 분석"}</span>
                        <span className="opacity-70">UPDATED {reportFullDate}</span>
                      </div>
                    </div>
                  </div>

                  {/* Right Column */}
                  <div className="lg:flex-[1] flex flex-col gap-6">
                    {/* Radar Chart */}
                    <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-xl flex flex-col items-center justify-center">
                      <div className="w-full text-left mb-2">
                        <h2 className="text-sm font-bold text-white">상권 종합 지표 분석 (7 Core Metrics)</h2>
                        <p className="text-[11px] text-indigo-400">에이전트 노드 분석 결과 통합 데이터</p>
                      </div>
                      <div className="relative w-[180px] h-[180px] my-2">
                        <svg viewBox="0 0 200 200" className="w-full h-full overflow-visible">
                          <polygon points="100,40 147,63 158,113 126,154 74,154 42,113 53,63" fill="#1e1b18" stroke="#3a3633" strokeWidth="1" />
                          <polygon points="100,70 123.5,81.5 129,106.5 113,127 87,127 71,106.5 76.5,81.5" fill="none" stroke="#3a3633" strokeWidth="1" strokeDasharray="2 2" />
                          <line x1="100" y1="100" x2="100" y2="40" stroke="#3a3633" /><line x1="100" y1="100" x2="147" y2="63" stroke="#3a3633" /><line x1="100" y1="100" x2="158" y2="113" stroke="#3a3633" /><line x1="100" y1="100" x2="126" y2="154" stroke="#3a3633" /><line x1="100" y1="100" x2="74" y2="154" stroke="#3a3633" /><line x1="100" y1="100" x2="42" y2="113" stroke="#3a3633" /><line x1="100" y1="100" x2="53" y2="63" stroke="#3a3633" />
                          <polygon points="100,50 140,70 145,110 115,140 85,130 60,105 70,75" fill="rgba(99,102,241,0.4)" stroke="#818cf8" strokeWidth="2" className="drop-shadow-[0_0_8px_rgba(99,102,241,0.6)]" />
                          <circle cx="100" cy="50" r="3" fill="#fff" /><circle cx="140" cy="70" r="3" fill="#fff" /><circle cx="145" cy="110" r="3" fill="#fff" /><circle cx="115" cy="140" r="3" fill="#fff" /><circle cx="85" cy="130" r="3" fill="#fff" /><circle cx="60" cy="105" r="3" fill="#fff" /><circle cx="70" cy="75" r="3" fill="#fff" />
                          <text onClick={() => setActiveDrawer("attractiveness")} className="cursor-pointer hover:fill-[#818cf8] transition-colors" x="100" y="32" fill="#e5e5e5" fontSize="10" fontWeight="bold" textAnchor="middle">유동인구</text>
                          <text onClick={() => setActiveDrawer("attractiveness")} className="cursor-pointer hover:fill-[#818cf8] transition-colors" x="157" y="60" fill="#a3a3a3" fontSize="10" textAnchor="start">매출</text>
                          <text onClick={() => setActiveDrawer("attractiveness")} className="cursor-pointer hover:fill-[#818cf8] transition-colors" x="168" y="117" fill="#a3a3a3" fontSize="10" textAnchor="start">성장성</text>
                          <text onClick={() => setActiveDrawer("attractiveness")} className="cursor-pointer hover:fill-[#818cf8] transition-colors" x="133" y="166" fill="#a3a3a3" fontSize="10" textAnchor="middle">생존율</text>
                          <text onClick={() => setActiveDrawer("attractiveness")} className="cursor-pointer hover:fill-[#818cf8] transition-colors" x="67" y="166" fill="#a3a3a3" fontSize="10" textAnchor="middle">임대료</text>
                          <text onClick={() => setActiveDrawer("attractiveness")} className="cursor-pointer hover:fill-[#818cf8] transition-colors" x="32" y="117" fill="#a3a3a3" fontSize="10" textAnchor="end">경쟁강도</text>
                          <text onClick={() => setActiveDrawer("attractiveness")} className="cursor-pointer hover:fill-[#818cf8] transition-colors" x="43" y="60" fill="#a3a3a3" fontSize="10" textAnchor="end">접근성</text>
                        </svg>
                      </div>
                    </div>

                    {/* Insights */}
                    <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-xl flex flex-col flex-1">
                      {/* Header with dynamic counter */}
                      <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-bold text-white">SPOTTER AI 인사이트</h2>
                        <span className="font-mono text-[9px] uppercase tracking-widest text-[#818cf8] bg-[#818cf8]/10 border border-[#818cf8]/30 px-2 py-0.5 rounded-full">
                          3 INSIGHTS
                        </span>
                      </div>
                      <div className="space-y-3">
                        <InsightCard
                          severity="advisory"
                          onClick={() => setActiveDrawer("insight_traffic")}
                          icon={<TrendingUp className="w-4 h-4 text-indigo-400" />}
                          title="저녁 시간대 매출 집중형"
                          desc="18시 이후 유동인구가 급증. 야간 메뉴 강화를 권장합니다."
                        />
                        <InsightCard
                          severity="critical"
                          onClick={() => setActiveDrawer("insight_legal")}
                          icon={<Scale className="w-4 h-4 text-rose-500" />}
                          title="법률 리스크 경고 (Legal Node)"
                          desc={simResult?.recommendation || "상가임대차보호법 위반 사례 존재 권역. 최근 3년 평균 임대료 인상률이 5%를 초과하여 계약 갱신 시 법적 분쟁 리스크가 감지되었습니다."}
                        />
                        <InsightCard
                          severity="opportunity"
                          onClick={() => setActiveDrawer("insight_target")}
                          icon={<Users className="w-4 h-4 text-indigo-400" />}
                          title="2030 여성 타겟 구역"
                          desc="SNS 친화적 인테리어 도입 시 수익 창출 확률 34% 증가."
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* [v8.0] Drill-down Drawer — KPI/차트 클릭 시 우측에서 슬라이드 인 */}
      <DetailDrawer
        isOpen={!!activeDrawer}
        onClose={() => setActiveDrawer(null)}
        drawerKey={activeDrawer}
      />

      {/* [v12.0] Hidden A4 PDF Template — html2canvas 캡처용 (화면 밖) */}
      <HiddenPDFTemplate
        ref={pdfTemplateRef}
        districtFull={`마포구 ${selectedDongs[0] || "연남동"}`}
        stats={[
          { title: "예상 월 매출 (추정)", value: `₩ ${((simResult?.revenue ?? 3240) * 10000).toLocaleString()}`, trend: "+12.5%" },
          { title: "상권 종합 매력도", value: `${simResult?.score ?? 87} / 100`, trend: "+5.2 Pts" },
          { title: "일평균 유동인구", value: "42,105 명", trend: "-2.4%" },
          { title: "카니발리제이션 위험", value: `${simResult?.riskLevel ?? "Low"} (12%)`, trend: "안전 권역" },
        ]}
        cannibalizationRows={CANNIBALIZATION_ROWS}
        neighborhoodRows={NEIGHBORHOOD_ROWS}
        insights={[
          {
            severity: "advisory",
            title: "저녁 시간대 매출 집중형",
            desc: "18시 이후 유동인구가 급증. 야간 메뉴 강화를 권장합니다.",
          },
          {
            severity: "critical",
            title: "법률 리스크 경고 (Legal Node)",
            desc:
              simResult?.recommendation ||
              "상가임대차보호법 위반 사례 존재 권역. 최근 3년 평균 임대료 인상률이 5%를 초과하여 계약 갱신 시 법적 분쟁 리스크가 감지되었습니다.",
          },
          {
            severity: "opportunity",
            title: "2030 여성 타겟 구역",
            desc: "SNS 친화적 인테리어 도입 시 수익 창출 확률 34% 증가.",
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


function GlobalLimelightNav() {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, opacity: 0 });
  const navRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // B2B 실무 시나리오 메뉴 구성 (HQ Command Center)
  const navItems: { icon: React.ReactElement; label: string; hasNoti?: boolean }[] = [
    { icon: <Folder />, label: "보관함 / 파이프라인" },
    { icon: <Bell />, label: "알림 (승인 대기 등)", hasNoti: true },
    { icon: <Settings />, label: "HQ 설정 (브랜드 튜닝)" },
    { icon: <User />, label: "내 워크스페이스" },
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

  return (
    <div
      className="relative flex items-center bg-[#2c2825] border border-[#3a3633] rounded-full h-10 px-2 shadow-sm overflow-hidden hidden md:flex"
      onMouseLeave={() => setHoverIndex(null)}
    >
      {/* 호버 조명 효과 (인디고 테마 유지) */}
      <div
        className="absolute top-0 z-10 pointer-events-none flex flex-col items-center transition-all duration-300 ease-[cubic-bezier(0.25,1,0.5,1)]"
        style={{ left: `${indicatorStyle.left}px`, transform: "translateX(-50%)", opacity: indicatorStyle.opacity }}
      >
        <div className="w-6 h-[2px] bg-[#818cf8] rounded-b-full shadow-[0_0_8px_#818cf8]" />
        <div
          className="w-12 h-10 bg-[#818cf8]/20"
          style={{ clipPath: "polygon(25% 0%, 75% 0%, 100% 100%, 0% 100%)" }}
        />
      </div>

      {navItems.map((item, index) => (
        <button
          key={index}
          ref={(el) => { navRefs.current[index] = el; }}
          onClick={() => setActiveIndex(index)}
          onMouseEnter={() => setHoverIndex(index)}
          className="relative z-20 flex items-center justify-center h-full px-3 text-[#9ca3af] hover:text-[#e2e8f0] transition-colors group"
          title={item.label}
        >
          {React.cloneElement(item.icon, {
            className: `w-4 h-4 transition-all duration-300 ${
              targetIndex === index
                ? "text-[#818cf8] scale-110 drop-shadow-[0_0_5px_rgba(129,140,248,0.5)]"
                : "scale-100 group-hover:scale-110"
            }`,
          } as React.HTMLAttributes<HTMLElement>)}

          {/* 🔴 실시간 알림 Ping 뱃지 */}
          {item.hasNoti && (
            <span className="absolute top-2 right-2 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
            </span>
          )}
        </button>
      ))}
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
  insights: { severity: "critical" | "advisory" | "opportunity"; title: string; desc: string }[];
  reportDate: string;
}

// 인디고 SPOTTER 로고 SVG 경로 (Light 테마 버전 — #6366f1)
const SPOTTER_LOGO_PATHS = (
  <>
    <path d="M18.5147 0C15.4686 0 12.5473 1.21005 10.3934 3.36396L3.36396 10.3934C1.21005 12.5473 0 15.4686 0 18.5147C0 24.8579 5.14214 30 11.4853 30C14.5314 30 17.4527 28.7899 19.6066 26.636L24.4689 21.7737C24.469 21.7738 24.4689 21.7736 24.4689 21.7737L38.636 7.6066C39.6647 6.57791 41.0599 6 42.5147 6C44.9503 6 47.0152 7.58741 47.7311 9.78407L52.2022 5.31296C50.1625 2.11834 46.586 0 42.5147 0C39.4686 0 36.5473 1.21005 34.3934 3.36396L15.364 22.3934C14.3353 23.4221 12.9401 24 11.4853 24C8.45584 24 6 21.5442 6 18.5147C6 17.0599 6.57791 15.6647 7.6066 14.636L14.636 7.6066C15.6647 6.57791 17.0599 6 18.5147 6C20.9504 6 23.0152 7.58748 23.7311 9.78421L28.2023 5.31307C26.1626 2.1184 22.5861 0 18.5147 0Z" fill="#6366f1" />
    <path d="M39.364 22.3934C38.3353 23.4221 36.9401 24 35.4853 24C33.05 24 30.9853 22.413 30.2692 20.2167L25.7982 24.6877C27.838 27.8819 31.4143 30 35.4853 30C38.5314 30 41.4527 28.7899 43.6066 26.636L62.636 7.6066C63.6647 6.57791 65.0599 6 66.5147 6C69.5442 6 72 8.45584 72 11.4853C72 12.9401 71.4221 14.3353 70.3934 15.364L63.364 22.3934C62.3353 23.4221 60.9401 24 59.4853 24C57.0498 24 54.985 22.4127 54.269 20.2162L49.798 24.6873C51.8377 27.8818 55.4141 30 59.4853 30C62.5314 30 65.4527 28.7899 67.6066 26.636L74.636 19.6066C76.7899 17.4527 78 14.5314 78 11.4853C78 5.14214 72.8579 0 66.5147 0C63.4686 0 60.5473 1.21005 58.3934 3.36396L39.364 22.3934Z" fill="#6366f1" />
  </>
);

function PDFPageHeader({ pageNumber, totalPages, districtFull }: {
  pageNumber: number; totalPages: number; districtFull: string;
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
    const pageClass = "w-[794px] h-[1123px] p-12 bg-white text-slate-900 relative flex flex-col";
    const docId = `SPTR-${Date.now().toString().slice(-8)}`;

    const severityStyle = {
      critical: { dot: "bg-rose-500", bg: "bg-rose-50 border-rose-200" },
      advisory: { dot: "bg-[#6366f1]", bg: "bg-indigo-50 border-indigo-200" },
      opportunity: { dot: "bg-emerald-500", bg: "bg-emerald-50 border-emerald-200" },
    };

    return (
      <div
        ref={ref}
        className="absolute top-[-9999px] left-[-9999px] w-[794px] bg-white font-sans"
        style={{ fontFamily: "Pretendard, sans-serif" }}
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
            <div className="font-bold text-rose-500 text-sm tracking-[0.25em]">
              CONFIDENTIAL
            </div>
          </div>
        </div>

        {/* ─────────── Page 2: 종합 요약 + 차트 ─────────── */}
        <div className={pageClass}>
          <PDFPageHeader pageNumber={2} totalPages={TOTAL_PAGES} districtFull={districtFull} />

          <div className="flex-1 pt-8">
            <h2 className="text-[22px] font-black text-slate-900 mb-1">01. 상권 종합 요약</h2>
            <p className="text-xs text-slate-500 mb-6">Executive Summary · 핵심 KPI 및 시계열 분석</p>

            {/* KPI Grid */}
            <div className="grid grid-cols-4 gap-3 mb-8">
              {stats.map((s, i) => (
                <div key={i} className="border border-slate-200 bg-slate-50 p-4 rounded-lg">
                  <div className="text-[9px] text-slate-500 mb-2 uppercase tracking-wider">{s.title}</div>
                  <div className="text-[15px] font-black text-slate-900 leading-tight">{s.value}</div>
                  <div className="text-[9px] text-emerald-600 mt-1.5 font-mono">{s.trend}</div>
                </div>
              ))}
            </div>

            {/* Time Series Chart (Light Theme) */}
            <h3 className="text-sm font-bold mb-3 text-slate-900">시간대별 유동인구 및 매출 (24H)</h3>
            <div className="border border-slate-200 bg-slate-50 rounded-lg p-5 h-[220px] mb-6 relative">
              <svg viewBox="0 0 1000 300" className="absolute inset-5 w-[calc(100%-40px)] h-[calc(100%-40px)]" preserveAspectRatio="none">
                <path d="M 0 280 C 100 280, 150 200, 250 180 C 350 160, 400 250, 500 240 C 600 230, 700 80, 800 100 C 900 120, 950 200, 1000 220 L 1000 300 L 0 300 Z" fill="url(#pdfGrayGrad)" opacity="0.4" />
                <path d="M 0 280 C 100 280, 150 200, 250 180 C 350 160, 400 250, 500 240 C 600 230, 700 80, 800 100 C 900 120, 950 200, 1000 220" fill="none" stroke="#94a3b8" strokeWidth="3" />
                <path d="M 0 290 C 150 290, 200 150, 300 120 C 400 90, 450 200, 550 180 C 650 160, 750 40, 850 50 C 950 60, 980 150, 1000 160 L 1000 300 L 0 300 Z" fill="url(#pdfIndigoGrad)" opacity="0.35" />
                <path d="M 0 290 C 150 290, 200 150, 300 120 C 400 90, 450 200, 550 180 C 650 160, 750 40, 850 50 C 950 60, 980 150, 1000 160" fill="none" stroke="#6366f1" strokeWidth="4" />
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
            <h3 className="text-sm font-bold mb-3 text-slate-900">상권 종합 지표 분석 (7 Core Metrics)</h3>
            <div className="border border-slate-200 bg-slate-50 rounded-lg p-5 flex items-center justify-center">
              <svg viewBox="0 0 200 200" width="240" height="240">
                <polygon points="100,40 147,63 158,113 126,154 74,154 42,113 53,63" fill="#ffffff" stroke="#cbd5e1" strokeWidth="1" />
                <polygon points="100,70 123.5,81.5 129,106.5 113,127 87,127 71,106.5 76.5,81.5" fill="none" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="2 2" />
                <line x1="100" y1="100" x2="100" y2="40" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="147" y2="63" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="158" y2="113" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="126" y2="154" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="74" y2="154" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="42" y2="113" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="53" y2="63" stroke="#cbd5e1" />
                <polygon points="100,50 140,70 145,110 115,140 85,130 60,105 70,75" fill="rgba(99,102,241,0.25)" stroke="#6366f1" strokeWidth="2" />
                <circle cx="100" cy="50" r="3" fill="#6366f1" />
                <circle cx="140" cy="70" r="3" fill="#6366f1" />
                <circle cx="145" cy="110" r="3" fill="#6366f1" />
                <circle cx="115" cy="140" r="3" fill="#6366f1" />
                <circle cx="85" cy="130" r="3" fill="#6366f1" />
                <circle cx="60" cy="105" r="3" fill="#6366f1" />
                <circle cx="70" cy="75" r="3" fill="#6366f1" />
                <text x="100" y="32" fill="#1e293b" fontSize="10" fontWeight="bold" textAnchor="middle">유동인구</text>
                <text x="157" y="60" fill="#64748b" fontSize="10" textAnchor="start">매출</text>
                <text x="168" y="117" fill="#64748b" fontSize="10" textAnchor="start">성장성</text>
                <text x="133" y="166" fill="#64748b" fontSize="10" textAnchor="middle">생존율</text>
                <text x="67" y="166" fill="#64748b" fontSize="10" textAnchor="middle">임대료</text>
                <text x="32" y="117" fill="#64748b" fontSize="10" textAnchor="end">경쟁강도</text>
                <text x="43" y="60" fill="#64748b" fontSize="10" textAnchor="end">접근성</text>
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
              <p className="text-xs text-slate-500 mb-4">Cannibalization Analysis · 반경 내 동일 브랜드 영향도</p>
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
                            r.status === "Safe"
                              ? "bg-emerald-50 text-emerald-600 border-emerald-200"
                              : "bg-slate-100 text-slate-600 border-slate-300"
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
              <p className="text-xs text-slate-500 mb-4">Neighborhood Comparison · 인근 동 AI 점수 / 생존율 / 손익분기점</p>
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                    <th className="py-2.5 font-medium">행정동</th>
                    <th className="py-2.5 font-medium">AI 점수</th>
                    <th className="py-2.5 font-medium">생존율</th>
                    <th className="py-2.5 font-medium">예상 BEP</th>
                  </tr>
                </thead>
                <tbody>
                  {neighborhoodRows.map((r, i) => (
                    <tr key={i} className="border-b border-slate-200">
                      <td className="py-3 font-medium text-slate-900">{r.name}</td>
                      <td className="py-3 font-mono text-slate-900">{r.score}</td>
                      <td className="py-3 font-mono text-slate-900">{r.survival}</td>
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
            <p className="text-xs text-slate-500 mb-6">LangGraph Multi-Agent Analysis · 에이전트 노드별 인사이트</p>

            <div className="space-y-4">
              {insights.map((insight, i) => {
                const style = severityStyle[insight.severity];
                return (
                  <div key={i} className={`border rounded-lg p-5 ${style.bg}`}>
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="text-[14px] font-bold text-slate-900 flex-1">{insight.title}</h3>
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
                market_analyst, population_analyst, legal_advisor, financial_insight 4개 노드의 통합 분석 결과를 포함하며,
                KT 통신사 셀룰러 데이터, 공공데이터(상가정보·인구통계·임대시세), 그리고 A2 봉환 팀의 법률 RAG 시스템
                (14개 영역 3,775 청크)을 교차 검증하여 도출되었습니다.
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
  }
);
HiddenPDFTemplate.displayName = "HiddenPDFTemplate";

/* ═══════════════════════════════════════════════════════
   DetailDrawer (v8.0) — KPI/차트 클릭 시 우측에서 슬라이드 인
   ═══════════════════════════════════════════════════════ */
function DetailDrawer({
  isOpen,
  onClose,
  drawerKey,
}: {
  isOpen: boolean;
  onClose: () => void;
  drawerKey: DrawerKey;
}) {
  const data = drawerKey ? mockDetailData[drawerKey] : null;

  return (
    <>
      {/* Backdrop Overlay */}
      <div
        className={`fixed inset-0 z-[100] bg-[#1e1b18]/60 backdrop-blur-sm transition-opacity duration-500 ${
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <div
        className={`fixed top-0 right-0 w-full md:w-[480px] h-full bg-[#2c2825] border-l border-[#3a3633] z-[101] shadow-2xl flex flex-col transition-transform duration-[800ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
          isOpen ? "translate-x-0" : "translate-x-full"
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
                  {data.aiReasoning || "해당 지표에 대한 상세 분석 알고리즘 로그입니다."}
                </p>
              </div>

              {/* 메타 데이터 */}
              {(data.confidence || data.rank || data.trend || data.peakTime || data.mainTarget || data.warning) && (
                <div className="bg-[#1e1b18] p-5 rounded-xl border border-[#3a3633] mb-4 space-y-3">
                  <h3 className="text-xs font-bold text-[#818cf8] tracking-widest uppercase mb-3">
                    핵심 지표
                  </h3>
                  {data.confidence && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-[#9ca3af]">신뢰도</span>
                      <span className="text-sm font-bold text-[#e2e8f0] font-mono">{data.confidence}</span>
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
                      <span className="text-sm font-bold text-[#e2e8f0] font-mono">{data.peakTime}</span>
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
                      <span className="text-xs text-rose-400 leading-relaxed block">{data.warning}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Detailed Chart Placeholder */}
              <div className="w-full h-48 bg-[#1e1b18] border border-[#3a3633] rounded-xl flex items-center justify-center">
                <span className="text-[#3a3633] font-mono text-xs tracking-[0.3em]">DETAILED CHART AREA</span>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function StatCard({ title, value, trend, trendUp, icon, sparkline, onClick }: {
  title: string; value: string; trend: string; trendUp: boolean;
  icon: React.ReactElement; sparkline: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className="bg-[#2c2825] border border-[#3a3633] p-6 rounded-xl flex flex-col justify-between gap-3 group cursor-pointer hover:border-[#818cf8] hover:shadow-[0_0_20px_rgba(129,140,248,0.2)] transition-all min-h-[130px]"
    >
      <div className="flex justify-between items-start">
        <p className="text-[#9ca3af] text-xs font-medium">{title}</p>
        <div className="text-[#9ca3af] opacity-50 group-hover:opacity-100 group-hover:text-indigo-400 transition-colors">
          {React.cloneElement(icon, { className: "w-4 h-4" } as React.HTMLAttributes<HTMLElement>)}
        </div>
      </div>
      <div>
        <h3 className="text-xl md:text-2xl font-black text-white tracking-tight mb-1">{value}</h3>
        <div className="flex items-center justify-between">
          <span className={`text-[10px] font-bold flex items-center gap-0.5 ${trendUp ? "text-emerald-500" : "text-rose-500"}`}>
            {trendUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />} {trend}
          </span>
          <svg viewBox="0 0 100 30" className="w-12 h-4 overflow-visible opacity-50 group-hover:opacity-100 transition-opacity">
            <path d={sparkline} fill="none" stroke={trendUp ? "#10b981" : "#f43f5e"} strokeWidth="2" strokeLinecap="round" />
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
  sortDir: "asc" | "desc";
  onSort: (key: string) => void;
}) {
  const isActive = sortKey === sortField;
  return (
    <span
      onClick={() => onSort(sortField)}
      className={`inline-flex items-center gap-1 cursor-pointer transition-colors select-none ${
        isActive ? "text-[#818cf8]" : "hover:text-[#e2e8f0]"
      }`}
    >
      {label}
      {isActive ? (
        sortDir === "asc" ? (
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

function TableRow({ icon, col1, col2, col3, status, expanded, onToggle }: {
  icon: React.ReactNode; col1: string; col2: string; col3: string; status: string;
  index?: number; expanded?: boolean; onToggle?: () => void;
}) {
  const getStatusColor = (s: string) => {
    if (s === "Safe") return "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
    if (s === "Warning") return "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
    if (s.includes("개월")) return "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
    return "bg-[#1e1b18] text-[#9ca3af] border-[#3a3633]";
  };
  return (
    <>
      <tr
        onClick={onToggle}
        className={`cursor-pointer transition-colors group ${
          expanded ? "bg-[#818cf8]/[0.06]" : "hover:bg-[#3a3633]/50"
        }`}
      >
        <td className="p-3 pl-5 font-medium text-[#e2e8f0]">
          <span className="inline-flex items-center gap-2">
            <ChevronRight
              size={12}
              className={`text-[#9ca3af] transition-transform duration-300 ${
                expanded ? "rotate-90 text-[#818cf8]" : ""
              }`}
            />
            <span className="text-[#9ca3af] group-hover:text-indigo-400 transition-colors">{icon}</span>
            {col1}
          </span>
        </td>
        <td className="p-3 text-[#9ca3af] font-mono">{col2}</td>
        <td className="p-3 font-mono font-bold text-white">{col3}</td>
        <td className="p-3">
          <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full border whitespace-nowrap ${getStatusColor(status)}`}>
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
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#9ca3af]">상권 겹침</span>
                <div className="bg-[#2c2825] rounded-lg border border-[#3a3633] p-3 flex items-center justify-center">
                  <svg viewBox="0 0 120 70" className="w-full max-w-[160px] h-16">
                    <circle cx="42" cy="35" r="22" fill="rgba(129,140,248,0.2)" stroke="#818cf8" strokeWidth="1.5" />
                    <circle cx="78" cy="35" r="22" fill="rgba(244,63,94,0.2)" stroke="#f43f5e" strokeWidth="1.5" />
                    <text x="42" y="38" fontSize="6" fill="#818cf8" textAnchor="middle" fontWeight="bold">신규</text>
                    <text x="78" y="38" fontSize="6" fill="#f43f5e" textAnchor="middle" fontWeight="bold">기존</text>
                    <text x="60" y="38" fontSize="5" fill="#e2e8f0" textAnchor="middle" opacity="0.6">∩</text>
                  </svg>
                </div>
              </div>

              {/* 2. 시간대별 영향도 */}
              <div className="flex flex-col gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#9ca3af]">시간대별 영향도</span>
                <div className="bg-[#2c2825] rounded-lg border border-[#3a3633] p-3 flex flex-col gap-1.5 text-[10px] font-mono">
                  <div className="flex justify-between"><span className="text-[#9ca3af]">오전 (06-11)</span><span className="text-emerald-400">-0.4%</span></div>
                  <div className="flex justify-between"><span className="text-[#9ca3af]">점심 (11-14)</span><span className="text-rose-400">-2.1%</span></div>
                  <div className="flex justify-between"><span className="text-[#9ca3af]">저녁 (17-21)</span><span className="text-rose-400">-3.4%</span></div>
                  <div className="flex justify-between"><span className="text-[#9ca3af]">심야 (21-02)</span><span className="text-emerald-400">-0.8%</span></div>
                </div>
              </div>

              {/* 3. Counterfactual */}
              <div className="flex flex-col gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#9ca3af]">Counterfactual</span>
                <div className="bg-[#2c2825] rounded-lg border border-[#3a3633] p-3 flex-1 flex flex-col justify-center gap-1">
                  <p className="text-[10px] text-[#9ca3af] leading-relaxed">
                    이 매장이 없었다면
                  </p>
                  <p className="text-lg font-black text-[#818cf8] font-mono leading-none">
                    +18.4%
                  </p>
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

function InsightCard({ icon, title, desc, severity = "advisory", onClick }: {
  icon: React.ReactNode; title: string; desc: string;
  severity?: "critical" | "advisory" | "opportunity";
  onClick?: () => void;
}) {
  const severityStyle = {
    critical: { dot: "bg-rose-500", label: "CRITICAL" },
    advisory: { dot: "bg-[#818cf8]", label: "ADVISORY" },
    opportunity: { dot: "bg-emerald-500", label: "OPPORTUNITY" },
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
          onClick={(e) => e.stopPropagation()}
          className="p-1 rounded hover:bg-[#818cf8]/10 hover:text-[#818cf8] text-[#9ca3af] transition-colors"
          aria-label="유용함"
        >
          <ThumbsUp className="w-3 h-3" />
        </button>
        <button
          onClick={(e) => e.stopPropagation()}
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
   - reportState: Simulator idle/loading/result 상태
   - isAppLoaded: 프리로더 완료 여부

   [글로벌 헤더]
   - 인트로 제외 모든 씬에 공통 표시
   - 좌: 로고+BACK / 우: SkyThemeToggle + GlobalLimelightNav
   - ※ AccordionGallery는 자체 3열 헤더를 사용 (중앙 인디케이터 포함)

   [프리로더]
   - 앱 최초 진입 시 3초간 5축 자이로스코프 홀로그램
   - 100% → warp-out 트랜지션 → main-scene-in → isAppLoaded=true → DOM 제거
*/

/** 현재 경로 → scene 이름 매핑 */
function pathToScene(pathname: string): "intro" | "about" | "joinus" | "accordion" | "simulator" | "contact" | "hq" | "login" {
  if (pathname === "/about") return "about";
  if (pathname === "/joinus") return "joinus";
  if (pathname === "/explore") return "accordion";
  if (pathname === "/simulator") return "simulator";
  if (pathname === "/contact") return "contact";
  if (pathname === "/hq") return "hq";
  if (pathname === "/login") return "login";
  return "intro";
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const scene = pathToScene(location.pathname);

  const [isTransitioning, setIsTransitioning] = useState(false);
  const [reportState, setReportState] = useState<"idle" | "loading" | "result">(
    "idle"
  );
  const [activeMenuIndex, setActiveMenuIndex] = useState(2);
  const [hoveredDistrictIdx, setHoveredDistrictIdx] = useState<number | null>(
    null
  );

  // Preloader
  const [loadProgress, setLoadProgress] = useState(0);
  const [isAppLoaded, setIsAppLoaded] = useState(false);
  const [loadLogs, setLoadLogs] = useState<string[]>([]);

  useEffect(() => {
    setLoadLogs(["[SYSTEM] KERNEL BOOT SEQUENCE INITIATED..."]);
    const duration = 3000;
    const interval = 30;
    const steps = duration / interval;
    let currentStep = 0;

    const timer = setInterval(() => {
      currentStep++;
      const p = Math.min(100, Math.floor((currentStep / steps) * 100));
      setLoadProgress(p);

      if (p === 15) setLoadLogs((prev) => [...prev, "[API] ESTABLISHING 3D SPATIAL CONNECTION..."]);
      if (p === 35) setLoadLogs((prev) => [...prev, "[ENGINE] AGGREGATING FRANCHISE DATA..."]);
      if (p === 60) setLoadLogs((prev) => [...prev, "[DATA] CALCULATING RISK ALGORITHMS..."]);
      if (p === 85) setLoadLogs((prev) => [...prev, "[UI] RENDERING HOLOGRAM DASHBOARD..."]);
      if (p === 100) setLoadLogs((prev) => [...prev, "[SYSTEM] SPOTTER ENGINE ONLINE."]);

      if (currentStep >= steps) {
        clearInterval(timer);
        setTimeout(() => setIsAppLoaded(true), 1700);
      }
    }, interval);

    return () => clearInterval(timer);
  }, []);

  /** 암전 트랜지션 + 라우팅 */
  const transitionTo = useCallback(
    (next: "intro" | "about" | "joinus" | "accordion" | "simulator" | "contact") => {
      setIsTransitioning(true);
      setTimeout(() => {
        const pathMap: Record<string, string> = {
          intro: "/",
          about: "/about",
          joinus: "/joinus",
          accordion: "/explore",
          simulator: "/simulator",
          contact: "/contact",
        };
        const path = pathMap[next] || "/";
        navigate(path);
        setReportState("idle");
        setTimeout(() => setIsTransitioning(false), 100);
      }, 800);
    },
    [navigate]
  );

  return (
    <div
      className="w-screen h-screen overflow-hidden select-none bg-background text-foreground"
      style={{
        animation: isAppLoaded
          ? "none"
          : "main-scene-in 1.5s cubic-bezier(0.19, 1, 0.22, 1) 0.5s forwards",
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
      <NetworkBackground
        isTransitioning={isTransitioning}
        scene={scene}
        theme="dark"
      />

      {/* Route-based scenes */}
      <Routes>
        <Route
          path="/"
          element={
            <IntroScene
              activeMenuIndex={activeMenuIndex}
              setActiveMenuIndex={setActiveMenuIndex}
              onAboutClick={() => transitionTo("about")}
              onJoinUsClick={() => transitionTo("joinus")}
              onSimulatorClick={() => transitionTo("accordion")}
              onContactClick={() => transitionTo("contact")}
            />
          }
        />
        <Route
          path="/about"
          element={
            <AboutPage onBack={() => transitionTo("intro")} />
          }
        />
        <Route
          path="/joinus"
          element={
            <JoinUsPage onBack={() => transitionTo("intro")} />
          }
        />
        <Route
          path="/explore"
          element={
            <AccordionGallery
              hoveredIdx={hoveredDistrictIdx}
              setHoveredIdx={setHoveredDistrictIdx}
              onMapoClick={() => transitionTo("simulator")}
              onLogoClick={() => transitionTo("intro")}
            />
          }
        />
        <Route
          path="/contact"
          element={
            <ContactPage onBack={() => transitionTo("intro")} />
          }
        />
        <Route
          path="/simulator"
          element={
            <SimulatorDashboard
              reportState={reportState}
              setReportState={setReportState}
            />
          }
        />
        <Route path="/hq" element={<HQCommandCenter />} />
        <Route path="/login" element={<LoginPage />} />
      </Routes>

      {/* Global header — all scenes except intro */}
      {scene !== "intro" && !isTransitioning && (
        <header className="fixed top-0 left-0 w-full h-24 border-b border-[#3a3633] flex items-center px-8 md:px-16 justify-between bg-[#1e1b18]/90 backdrop-blur-md z-50 transition-colors duration-500">
          <div className="flex items-center gap-4">
            <button
              onClick={() => transitionTo("intro")}
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
                if (scene === "simulator" && reportState === "result") {
                  window.history.back();
                  return;
                }
                transitionTo(scene === "simulator" ? "accordion" : "intro");
              }}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors duration-300"
            >
              <ChevronRight size={14} className="rotate-180" />
              BACK
            </button>
          </div>
          <div className="flex items-center gap-4 md:gap-6">
            <GlobalLimelightNav />
          </div>
        </header>
      )}

      {/* Transition overlay */}
      <div
        className={`fixed inset-0 z-50 bg-black pointer-events-none transition-opacity duration-[800ms] ${
          isTransitioning ? "opacity-100" : "opacity-0"
        }`}
      />

      {/* 3D Hologram Preloader */}
      {!isAppLoaded && (
        <div
          className="absolute inset-0 z-[99999] bg-[#1e1b18] flex flex-col items-center justify-center"
          style={{
            animation:
              loadProgress === 100
                ? "warp-out 1.2s cubic-bezier(0.19, 1, 0.22, 1) 0.5s forwards"
                : "none",
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
              <svg viewBox="0 0 200 200" className="absolute w-[100%] h-[100%] opacity-40" style={{ transform: "rotateX(70deg) rotateY(10deg) rotateZ(0deg)", animation: "gyro-1 12s linear infinite" }}>
                <circle cx="100" cy="100" r="95" fill="none" stroke="#818cf8" strokeWidth="0.5" strokeDasharray="2 6" />
                <circle cx="100" cy="100" r="90" fill="none" stroke="#818cf8" strokeWidth="2" strokeDasharray="10 40 30 20" />
              </svg>

              {/* Ring 2 */}
              <svg viewBox="0 0 200 200" className="absolute w-[85%] h-[85%] opacity-60" style={{ transform: "rotateX(50deg) rotateY(60deg) rotateZ(0deg)", animation: "gyro-2 9s linear infinite" }}>
                <circle cx="100" cy="100" r="85" fill="none" stroke="#6366f1" strokeWidth="3" strokeDasharray="60 30 10 30" strokeLinecap="round" />
                <circle cx="100" cy="15" r="5" fill="#818cf8" />
              </svg>

              {/* Ring 3 */}
              <svg viewBox="0 0 200 200" className="absolute w-[70%] h-[70%] opacity-70" style={{ transform: "rotateX(50deg) rotateY(-60deg) rotateZ(0deg)", animation: "gyro-3 15s linear infinite" }}>
                <circle cx="100" cy="100" r="75" fill="none" stroke="#a5b4fc" strokeWidth="1" strokeDasharray="4 8" />
                <circle cx="100" cy="100" r="70" fill="none" stroke="#818cf8" strokeWidth="1.5" strokeDasharray="40 80" />
              </svg>

              {/* Ring 4 */}
              <svg viewBox="0 0 200 200" className="absolute w-[95%] h-[95%] opacity-80" style={{ transform: "rotateX(20deg) rotateY(80deg) rotateZ(0deg)", animation: "gyro-4 6s linear infinite" }}>
                <circle cx="100" cy="100" r="88" fill="none" stroke="#a5b4fc" strokeWidth="1" style={{ filter: "drop-shadow(0 0 8px #a5b4fc)" }} />
                <circle cx="100" cy="12" r="3" fill="#ffffff" />
                <circle cx="100" cy="188" r="3" fill="#ffffff" />
              </svg>

              {/* Ring 5 */}
              <svg viewBox="0 0 200 200" className="absolute w-[115%] h-[115%] opacity-30" style={{ transform: "rotateX(80deg) rotateY(-30deg) rotateZ(0deg)", animation: "gyro-5 20s linear infinite" }}>
                <circle cx="100" cy="100" r="98" fill="none" stroke="#818cf8" strokeWidth="1" strokeDasharray="4 16" />
                <circle cx="100" cy="100" r="94" fill="none" stroke="#6366f1" strokeWidth="0.5" />
              </svg>

              {/* Center percentage */}
              <div
                className="absolute flex flex-col items-center justify-center pointer-events-none"
                style={{ animation: "energy-pulse 2s ease-in-out infinite" }}
              >
                <span className="font-black text-6xl md:text-8xl text-indigo-400 tracking-tighter leading-none">
                  {loadProgress}
                  <span className="text-3xl md:text-4xl text-indigo-400/60 ml-1">
                    %
                  </span>
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
                  className={
                    idx === loadLogs.length - 1
                      ? "text-indigo-400 font-bold"
                      : ""
                  }
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
  );
}
