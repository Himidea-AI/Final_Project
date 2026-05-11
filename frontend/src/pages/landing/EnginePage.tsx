/**
 * EnginePage — SPOTTER 의 엔진 (Multi-Agent + ML) 소개 에디토리얼.
 * 헤더는 App.tsx 의 global header 가 제공 (scene !== 'intro' 일 때 fixed h-20).
 * 본문만 렌더.
 *
 * 구조:
 *  - Hero: "The Engine Behind SPOTTER"
 *  - § Multi-Agent Layer: 9 페르소나 인터랙티브 row
 *      hover 시 typewriter 로 실시간 시뮬 로그 popup (터미널 톤)
 *      — 한 번 hover 한 아이콘은 status dot 점등으로 "online" 시각화
 *  - § ML Models: TCN / LightGBM+TCN / SHAP / Emerging / ABM / RAG
 *  - § Data Sources: 공공데이터 19+ 출처
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import marketIcon from '../../assets/agents/market.png';
import populationIcon from '../../assets/agents/population.png';
import legalIcon from '../../assets/agents/legal.png';
import rankingIcon from '../../assets/agents/ranking.png';
import inflowIcon from '../../assets/agents/inflow.png';
import synthesisIcon from '../../assets/agents/synthesis.png';
import demographicIcon from '../../assets/agents/demographic.png';
import trendIcon from '../../assets/agents/trend.png';
import competitorIcon from '../../assets/agents/competitor.png';

interface Agent {
  name: string;
  jobtitle: string;
  iconSrc: string;
  /** popup status dot + ring glow color */
  color: string;
  /** typewriter 로 출력될 시뮬 로그 — backend 실 동작에 맞춘 도메인 메시지 */
  log: string;
}

const AGENTS: Agent[] = [
  {
    name: 'Market Spotter',
    jobtitle: '상권 분석 에이전트',
    iconSrc: marketIcon,
    color: '#f97316', // Vivid Orange — light bg 에서도 잘 보이고 Amber(legal) 와 hue 분리
    log: `> [SCAN] 반경 500m 동일업종 12개 매장 탐지
> [METRIC] HHI 0.18 / 다양도 0.82 (분산형 상권)
> [STATUS] Market Spotter: "경쟁 강도 중간 — 차별화 진입 가능"`,
  },
  {
    name: 'Population Spotter',
    jobtitle: '생활인구 에이전트',
    iconSrc: populationIcon,
    color: '#3b82f6',
    log: `> [INGEST] 마포 16동 시간대별 생활인구 24h 로드
> [ANALYZE] 피크 12-13시 / 18-20시 이중 봉우리
> [STATUS] Population Spotter: "Dual peak 패턴 — 카페/F&B 적합"`,
  },
  {
    name: 'Legal Spotter',
    jobtitle: '법률 리스크 에이전트',
    iconSrc: legalIcon,
    color: '#FBBF24',
    log: `> [QUERY] 가맹사업법 영업지역 보호 RAG 검색
> [SCAN] 학교환경위생정화구역 200m 거리 측정
> [STATUS] Legal Spotter: "주류업 caution / 일반업종 안전"`,
  },
  {
    name: 'Ranking Spotter',
    jobtitle: '동별 랭킹 에이전트',
    iconSrc: rankingIcon,
    color: '#8b5cf6',
    log: `> [COMPUTE] 16동 5지표 정량 비교 시작
> [RANK] winner=서교동 / top_3 산출 완료
> [STATUS] Ranking Spotter: "출점 우선순위 정렬 완료"`,
  },
  {
    name: 'Inflow Spotter',
    jobtitle: '유입 분석 에이전트',
    iconSrc: inflowIcon,
    color: '#06b6d4',
    log: `> [LOOKUP] 지하철 6개 노선 60+ 역 거리 측정
> [SCORE] spot 별 접근성 + 경쟁밀도 가중합 산출
> [STATUS] Inflow Spotter: "best vacancy 감지 — 적합도 87/100"`,
  },
  {
    name: 'Demographic Spotter',
    jobtitle: '인구 페르소나 에이전트',
    iconSrc: demographicIcon,
    color: '#FB7185',
    log: `> [PROFILE] KOSIS 가구 구조 + 소득 수준 매칭
> [SEGMENT] 30대 여성 직장인 비중 41%
> [STATUS] Demographic Spotter: "타겟 페르소나 매칭 완료"`,
  },
  {
    name: 'Trend Spotter',
    jobtitle: '트렌드 예측 에이전트',
    iconSrc: trendIcon,
    color: '#34D399',
    log: `> [SYNC] Naver DataLab + ECOS 거시 지표 수집
> [FORECAST] 12개월 change_ix +6.4% 상승 예측
> [STATUS] Trend Spotter: "신흥 상권 신호 감지"`,
  },
  {
    name: 'Competitor Spotter',
    jobtitle: '경쟁 정보 에이전트',
    iconSrc: competitorIcon,
    color: '#ef4444',
    log: `> [SCAN] 동일 브랜드 카니발리제이션 거리 분석
> [DIFF] 차별화 포지션 4개 기회 / 2개 리스크 도출
> [STATUS] Competitor Spotter: "기존 매장 -3% 잠식 예측"`,
  },
  {
    name: 'Synthesis Spotter',
    jobtitle: '종합 판단 에이전트',
    iconSrc: synthesisIcon,
    color: '#002CD1', // brand primary Deep Blue — 종합 판단(최상위) 에 brand 색 부여
    log: `> [INGEST] 8 에이전트 출력 통합 시작
> [SYNTH] 본부 영업팀 결정용 자연어 종합 판단 생성
> [STATUS] Synthesis Spotter: "GO 권고 — 신뢰도 0.84"`,
  },
];

interface MlModel {
  name: string;
  tag: string;
  desc: string;
  /** 카드 하단 정량 메트릭 chip — 모델별 핵심 수치 3개 */
  metrics: { label: string; value: string }[];
  /** 학습 데이터 규모 / 업데이트 주기 */
  pipeline: string;
}

const ML_MODELS: MlModel[] = [
  {
    name: 'TCN',
    tag: '매출 4분기 예측',
    desc: '동×업종 시계열을 4분기 매출(점단·신뢰구간 상하한) 로 예측. 점포당 매출 환산.',
    metrics: [
      { label: 'Horizon', value: '4Q' },
      { label: 'Coverage', value: '서울 16동 × 10업종' },
      { label: 'Output', value: 'p50 + 95% CI' },
    ],
    pipeline: 'TimeSeries · Quarterly retrain',
  },
  {
    name: 'LightGBM + TCN Ensemble',
    tag: '폐업 위험도',
    desc: 'Stage 1 산업 prior(LightGBM) × Stage 2 시계열 위험도(TCN) ensemble. 0~1 정규화.',
    metrics: [
      { label: 'Stage', value: '2-tier' },
      { label: 'Output', value: '0.0 ~ 1.0' },
      { label: 'Threshold', value: '0.6 = danger' },
    ],
    pipeline: 'Tabular + TimeSeries · Monthly refresh',
  },
  {
    name: 'SHAP',
    tag: 'ML 해석가능성',
    desc: '각 위험도 예측의 기여 요인을 자연어 인사이트로 변환. 본부 영업팀 페르소나에 맞춰 차트 X.',
    metrics: [
      { label: 'Layer', value: 'Post-hoc' },
      { label: 'Output', value: 'Top 5 driver' },
      { label: 'Format', value: '자연어 인사이트' },
    ],
    pipeline: 'Tree explainer · per-prediction',
  },
  {
    name: 'Emerging Classifier',
    tag: '상권 조기감지',
    desc: '서울시 공식 change_ix(LL/LH/HL/HH) + anomaly score. 신흥/정상/쇠퇴 3단계 신호등.',
    metrics: [
      { label: 'Tier', value: 'LL / LH / HL / HH' },
      { label: 'Score', value: '0.0 ~ 1.0' },
      { label: 'Source', value: '서울시 공식 stage' },
    ],
    pipeline: 'Hybrid rule + anomaly · Quarterly',
  },
  {
    name: 'ABM',
    tag: 'What-if 시뮬레이션',
    desc: '브랜드 진입·임대료·최저임금 변화 시나리오를 행위자 기반으로 동적 시뮬.',
    metrics: [
      { label: 'Agents', value: '점포 + 소비자' },
      { label: 'Variables', value: '6 lever' },
      { label: 'Scenarios', value: 'Optimistic / Base / Pessimistic' },
    ],
    pipeline: 'Mesa · on-demand sim',
  },
  {
    name: 'RAG',
    tag: '법률 검토',
    desc: '가맹사업법·상가임대차 분쟁 사례 DB 를 LLM 이 retrieval → 위반/주의 자동 판단.',
    metrics: [
      { label: 'Corpus', value: '가맹사업법 + 상가임대차' },
      { label: 'Retriever', value: 'Hybrid BM25+vector' },
      { label: 'Output', value: 'PASS / CAUTION / VIOLATION' },
    ],
    pipeline: 'Vector DB · weekly sync',
  },
];

interface DataGroup {
  category: string;
  freshness: string;
  sources: string[];
}

const DATA_GROUPS: DataGroup[] = [
  {
    category: '인구 · 페르소나',
    freshness: '월 단위',
    sources: ['서울 생활인구 (KT)', '통계청 SGIS', 'KOSIS 가구구조'],
  },
  {
    category: '상권 · 매출',
    freshness: '분기',
    sources: [
      '서울 상권분석 (golmok)',
      '서울 상권 변화 지수',
      '소상공인시장진흥공단',
      '서울 카드매출',
    ],
  },
  {
    category: '부동산 · 임대',
    freshness: '월 단위',
    sources: ['국토부 실거래가', '공실률 매물', '공시지가'],
  },
  {
    category: '트렌드 · 거시',
    freshness: '주 단위',
    sources: ['Naver DataLab', '한국은행 ECOS', '공정위 정보공개서'],
  },
  {
    category: '교통 · 접근성',
    freshness: '월 단위',
    sources: ['서울 지하철 승하차', '서울 따릉이', '버스 정류장 OD'],
  },
];

interface HeroMetric {
  value: string;
  label: string;
  sub: string;
}

const HERO_METRICS: HeroMetric[] = [
  { value: '9', label: 'Agents', sub: 'LangGraph 병렬 실행' },
  { value: '6', label: 'ML Models', sub: '시계열 + 분류 + 해석' },
  { value: '19+', label: 'Data Sources', sub: '서울 공공데이터 통합' },
  { value: '16', label: '동 Coverage', sub: '마포구 → 서울 25구 확장' },
];

/**
 * AgentRoster — 9 에이전트 인터랙티브 row.
 * hover → typewriter popup (터미널 톤). hover 안 한 아이콘은 grayscale.
 * 한 번 hover 한 아이콘은 status dot 점등 (online indicator).
 */
function AgentRoster() {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [hasBeenHovered, setHasBeenHovered] = useState<boolean[]>(
    new Array(AGENTS.length).fill(false),
  );
  const [typedText, setTypedText] = useState('');
  const typewriterTimeoutRef = useRef<number | null>(null);

  const startTypewriter = useCallback((text: string) => {
    if (typewriterTimeoutRef.current !== null) {
      window.clearTimeout(typewriterTimeoutRef.current);
    }
    setTypedText('');

    let i = 0;
    const type = () => {
      if (i <= text.length) {
        setTypedText(text.slice(0, i));
        i++;
        typewriterTimeoutRef.current = window.setTimeout(type, 22);
      }
    };
    type();
  }, []);

  const stopTypewriter = useCallback(() => {
    if (typewriterTimeoutRef.current !== null) {
      window.clearTimeout(typewriterTimeoutRef.current);
      typewriterTimeoutRef.current = null;
    }
    setTypedText('');
  }, []);

  const handleMouseEnter = useCallback(
    (index: number) => {
      setHoveredIndex(index);
      setHasBeenHovered((prev) => {
        if (prev[index]) return prev;
        const next = [...prev];
        next[index] = true;
        return next;
      });
      startTypewriter(AGENTS[index]!.log);
    },
    [startTypewriter],
  );

  const handleMouseLeave = useCallback(() => {
    setHoveredIndex(null);
    stopTypewriter();
  }, [stopTypewriter]);

  useEffect(() => {
    return () => {
      if (typewriterTimeoutRef.current !== null) {
        window.clearTimeout(typewriterTimeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="flex flex-wrap justify-center items-end gap-x-6 gap-y-10 py-8">
      {AGENTS.map((agent, index) => {
        const isHovered = hoveredIndex === index;
        const wasHovered = hasBeenHovered[index];
        return (
          <motion.div
            key={agent.name}
            className="relative flex flex-col items-center"
            onMouseEnter={() => handleMouseEnter(index)}
            onMouseLeave={handleMouseLeave}
            whileHover={{ scale: 1.08 }}
          >
            {/* 프로필 이미지 + ring glow */}
            <motion.div
              className="relative rounded-full p-1 cursor-pointer"
              animate={{
                boxShadow: isHovered
                  ? `0 0 28px ${agent.color}99`
                  : wasHovered
                    ? `0 0 12px ${agent.color}40`
                    : '0 0 0px transparent',
              }}
              transition={{ duration: 0.3 }}
            >
              <motion.img
                src={agent.iconSrc}
                alt={agent.name}
                className="w-20 h-20 md:w-24 md:h-24 rounded-full object-cover border-2"
                animate={{
                  borderColor: isHovered || wasHovered ? agent.color : 'var(--border)',
                  filter: isHovered ? 'grayscale(0%)' : 'grayscale(55%) opacity(0.85)',
                }}
                transition={{ duration: 0.3 }}
              />
              {/* status dot — hover 한번 거치면 online 점등 */}
              <div
                className="absolute bottom-1.5 right-1.5 w-3.5 h-3.5 rounded-full border-2 border-card transition-colors"
                style={{ backgroundColor: wasHovered ? agent.color : 'var(--muted)' }}
                aria-hidden
              />
            </motion.div>

            {/* 라벨 — 항상 표시 (작게) */}
            <div className="mt-3 text-center">
              <div className="text-[0.6875rem] font-black tracking-tight text-foreground">
                {agent.name}
              </div>
              <div className="text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground mt-0.5">
                {agent.jobtitle}
              </div>
            </div>

            {/* typewriter popup — 터미널 톤 (다크 카드, mono font) */}
            <AnimatePresence>
              {isHovered && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9, y: -6 }}
                  animate={{ opacity: 1, scale: 1, y: -16 }}
                  exit={{ opacity: 0, scale: 0.9, y: -6 }}
                  transition={{ duration: 0.22, type: 'spring', stiffness: 220, damping: 22 }}
                  className="absolute bottom-[calc(100%+1rem)] z-30 w-80 max-w-[80vw] rounded-xl border border-slate-700 bg-[#0a0f1a] p-5 shadow-2xl shadow-black/50"
                >
                  {/* popup 헤더 */}
                  <div className="flex items-center gap-3 mb-3 pb-3 border-b border-slate-700/60">
                    <span
                      className="inline-block w-2 h-2 rounded-full animate-ping"
                      style={{ backgroundColor: agent.color }}
                    />
                    <div className="min-w-0">
                      <div className="text-sm font-black text-white tracking-tight">
                        {agent.name}
                      </div>
                      <div className="text-[0.625rem] text-slate-400 mt-0.5">{agent.jobtitle}</div>
                    </div>
                  </div>
                  {/* typewriter 로그 */}
                  <div className="h-24 overflow-hidden whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-emerald-400">
                    {typedText}
                    <span className="opacity-70 animate-pulse">_</span>
                  </div>
                  {/* 꼬리표 */}
                  <div className="absolute left-1/2 -translate-x-1/2 -bottom-2 w-4 h-4 bg-[#0a0f1a] border-b border-r border-slate-700 rotate-45" />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        );
      })}
    </div>
  );
}

/** 섹션 헤더 라벨 — § 마커 + 카운트 + 가로 라인 + 우측 메타 */
function SectionLabel({ label, meta }: { label: string; meta?: string }) {
  return (
    <div className="mb-8 flex items-center gap-4">
      <span className="text-[0.625rem] font-mono uppercase tracking-[0.25em] text-primary">
        ▎{label}
      </span>
      <div className="h-px flex-1 bg-gradient-to-r from-border via-border to-transparent" />
      {meta && (
        <span className="shrink-0 text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
          {meta}
        </span>
      )}
    </div>
  );
}

export default function EnginePage(_: { onBack?: () => void }) {
  // 빌드 메타 — 페이지 신뢰감용. 실 build version 은 vite env 가 있으면 거기서.
  const buildVersion = 'v3.8.2';
  const lastSync = new Date().toISOString().slice(0, 10);

  return (
    <div className="absolute inset-0 z-20 overflow-y-auto bg-background text-foreground pb-32 custom-scrollbar">
      {/* Subtle dot grid — 전문성 텍스처. 메인 컨텐츠 위에 absolute fixed bg. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.035]"
        style={{
          backgroundImage:
            'radial-gradient(currentColor 1px, transparent 1px), radial-gradient(currentColor 1px, transparent 1px)',
          backgroundSize: '40px 40px, 40px 40px',
          backgroundPosition: '0 0, 20px 20px',
          color: 'var(--foreground)',
        }}
      />

      <div className="relative max-w-6xl mx-auto px-8 md:px-16 pt-20">
        {/* ── Hero ── */}
        <section className="py-16 animate-[fadeSlideIn_1s_ease-out]">
          <p className="text-xs font-mono uppercase tracking-[0.3em] text-primary mb-4">
            ▎The Engine
          </p>
          <h1 className="text-5xl md:text-7xl font-black tracking-tighter leading-[0.95] mb-6 uppercase">
            Behind every
            <br />
            <span className="text-primary">spot we choose.</span>
          </h1>
          <p className="text-base md:text-lg text-muted-foreground max-w-2xl break-keep leading-relaxed mb-12">
            9 멀티 에이전트가 의사결정 레이어를, 6 종 ML 모델이 정량 예측 레이어를 담당합니다. 서울
            19+ 공공데이터를 기반으로 학습·추론하며, 본부 영업팀의 출점 결정에 정량 근거를
            제공합니다.
          </p>

          {/* Hero metric strip — 좌(label + sub) / 우(큰 숫자값) 좌우 분할 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {HERO_METRICS.map((m) => (
              <div
                key={m.label}
                className="rounded-2xl border border-border bg-secondary p-5 flex items-center justify-between gap-3 transition-colors hover:border-primary/40"
              >
                <div className="min-w-0">
                  <div className="text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
                    {m.label}
                  </div>
                  <div className="mt-1.5 text-[0.6875rem] text-muted-foreground break-keep leading-snug">
                    {m.sub}
                  </div>
                </div>
                <div className="shrink-0 text-4xl md:text-5xl font-black tabular-nums tracking-tighter text-foreground leading-none">
                  {m.value}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── § ML Models ── */}
        <section className="py-16 animate-[fadeSlideIn_1.2s_ease-out]">
          <SectionLabel label="01 · ML Models" meta="Forecast · Risk · Explain" />
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            정량 예측 레이어
          </h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            매출·폐업·상권 변화·법률 리스크 — 본부 영업팀이 의심 없이 인용할 수 있는 수준의 정량
            엔진을 직접 학습·튜닝했습니다.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {ML_MODELS.map((m, idx) => (
              <div
                key={m.name}
                className="group relative rounded-2xl border border-border bg-secondary p-6 transition-all hover:border-primary/40 hover:shadow-lg"
              >
                {/* 좌상단 sequential index — 모델 카드별 순서 시각화 */}
                <div className="absolute right-5 top-5 text-[0.5625rem] font-mono tabular-nums text-muted-foreground/70">
                  M / {String(idx + 1).padStart(2, '0')}
                </div>
                <div className="mb-3">
                  <div className="text-xs font-mono uppercase tracking-widest text-primary mb-2">
                    ▎{m.tag}
                  </div>
                  <h3 className="text-xl font-black tracking-tight text-foreground">{m.name}</h3>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed break-keep mb-5">
                  {m.desc}
                </p>
                {/* 정량 메트릭 chip 3개 */}
                <div className="grid grid-cols-3 gap-2 mb-4">
                  {m.metrics.map((metric) => (
                    <div
                      key={metric.label}
                      className="rounded-lg border border-border bg-card px-3 py-2"
                    >
                      <div className="text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
                        {metric.label}
                      </div>
                      <div className="mt-1 text-[0.75rem] font-black tabular-nums text-foreground truncate">
                        {metric.value}
                      </div>
                    </div>
                  ))}
                </div>
                {/* pipeline footer */}
                <div className="flex items-center gap-2 pt-3 border-t border-border/60 text-[0.625rem] font-mono uppercase tracking-widest text-muted-foreground">
                  <span className="inline-block h-1 w-1 rounded-full bg-primary/60" />
                  <span>{m.pipeline}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── § Multi-Agent Layer ── */}
        <section className="py-16 animate-[fadeSlideIn_1.4s_ease-out]">
          <SectionLabel label="02 · Multi-Agent Layer" meta="LangGraph · 9 nodes" />
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            의사결정을 분담하는 9 에이전트
          </h2>
          <p className="text-sm text-muted-foreground mb-6 max-w-2xl break-keep leading-relaxed">
            LangGraph 기반 병렬 실행. 각 에이전트는 단일 책임 범위 안에서 자기 도메인 데이터를
            해석하고, Synthesis 가 8 출력을 통합해 종합 판단을 산출합니다.
          </p>
          <p className="text-xs font-mono uppercase tracking-widest text-primary mb-2">
            {'>'} Hover an agent to view live simulation log
          </p>
          <AgentRoster />
        </section>

        {/* ── § Data Sources — 카테고리 grouping ── */}
        <section className="py-16 animate-[fadeSlideIn_1.6s_ease-out]">
          <SectionLabel label="03 · Data Pipeline" meta="19+ public sources" />
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            서울 공공데이터 19+ 출처
          </h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            모든 추론은 공공데이터 + 행정안전부 표준 코드 기반. 카테고리별 freshness 와 출처 추적
            가능.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {DATA_GROUPS.map((g) => (
              <div
                key={g.category}
                className="rounded-2xl border border-border bg-card p-5 transition-colors hover:border-primary/40"
              >
                <div className="flex items-center justify-between gap-3 mb-4">
                  <div className="text-sm font-black tracking-tight text-foreground">
                    {g.category}
                  </div>
                  <span className="shrink-0 rounded-full border border-success/30 bg-success/10 px-2.5 py-0.5 text-[0.5625rem] font-black uppercase tracking-widest text-success">
                    sync · {g.freshness}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {g.sources.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-medium text-foreground/80"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Footer signature ── */}
        <footer className="mt-12 pt-8 border-t border-border/60">
          <div className="flex flex-wrap items-center justify-between gap-3 text-[0.625rem] font-mono uppercase tracking-widest text-muted-foreground">
            <span>▎SPOTTER · Multi-Agent + ML Engine</span>
            <span>
              build {buildVersion} · {lastSync}
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
