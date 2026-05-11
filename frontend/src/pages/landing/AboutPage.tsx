/**
 * AboutPage — 프로젝트 소개 에디토리얼 (UI/UX 고도화 v2 — EnginePage 톤 통일).
 * Hero / 5 Differentiators / Comparison / Data & Roadmap.
 *
 * 헤더는 App.tsx 의 global header 가 제공 (scene !== 'intro' 일 때 fixed h-20).
 * 본문만 렌더.
 */

import { Quote } from 'lucide-react';

interface Feature {
  num: string;
  category: string;
  title: string;
  desc: string;
  metric: { label: string; value: string };
}

const FEATURES: Feature[] = [
  {
    num: '01',
    category: 'Spatial Simulation',
    title: '카니발리제이션(자기잠식) 분석',
    desc: '같은 브랜드 기존 매장과의 영향권 중첩을 계산하여 매출 잠식률을 산출합니다. "3호점을 내면 1호점 매출이 얼마나 깎이는가?"에 대한 정량적 답을 제시합니다.',
    metric: { label: 'Output', value: '잠식률 % 정량' },
  },
  {
    num: '02',
    category: 'Cross-Category',
    title: '간접 경쟁(대체재) 분석',
    desc: '치킨집의 경쟁상대는 옆 치킨집만이 아닙니다. 피자·족발·배달 야식 등 소비 카테고리 전체의 경쟁 강도를 가중치 기반으로 반영합니다.',
    metric: { label: 'Coverage', value: '10+ 대체재 카테고리' },
  },
  {
    num: '03',
    category: 'What-if Engine',
    title: 'What-if 시나리오 시뮬레이션',
    desc: '경쟁 매장 진입, 최저임금 변화, 임대료 상승 등 조건을 변경하면 즉시 재시뮬레이션합니다. 미래의 불확실성을 데이터로 대비하세요.',
    metric: { label: 'Variables', value: '6 lever × 무제한' },
  },
  {
    num: '04',
    category: 'Time-Series ML',
    title: '12개월 시간 축 예측',
    desc: '단순 스냅샷이 아닌, 12개월간의 매출 추이·경쟁 반응·생존 확률을 시계열로 예측합니다.',
    metric: { label: 'Horizon', value: '4Q · 신뢰구간 95%' },
  },
  {
    num: '05',
    category: 'Legal RAG',
    title: '법률 리스크 AI 검토',
    desc: '가맹사업법 영업지역 보호, 상가임대차보호법 위반 여부를 AI가 자동으로 검토하여 법적 리스크를 사전에 차단합니다.',
    metric: { label: 'Output', value: 'PASS / CAUTION / VIOLATION' },
  },
];

interface Comparison {
  old: string;
  now: string;
}

const COMPARISONS: Comparison[] = [
  { old: '현재 상권 스냅샷만 제공', now: '12개월 미래 예측 시뮬레이션' },
  { old: '같은 업종 경쟁만 분석', now: '간접 경쟁(대체재)까지 반영' },
  { old: '자기잠식 분석 불가', now: '카니발리제이션 정량 산출' },
  { old: '컨설팅 비용 수천만 원', now: 'AI 기반 즉시 분석' },
  { old: '정적 리포트 1회 제공', now: 'What-if 무제한 재시뮬레이션' },
  { old: '법률 리스크 수동 검토', now: 'RAG 기반 자동 법률 검토' },
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
    sources: ['서울 상권분석 (golmok)', '서울 상권 변화 지수', '소상공인시장진흥공단'],
  },
  {
    category: '부동산 · 임대',
    freshness: '월 단위',
    sources: ['국토부 실거래가', '공시지가'],
  },
  {
    category: '트렌드 · 거시',
    freshness: '주 단위',
    sources: ['Naver DataLab', '한국은행 ECOS', '공정위 정보공개서'],
  },
];

interface RoadmapPhase {
  phase: string;
  status: 'live' | 'next' | 'future';
  scope: string;
  label: string;
  metric: string;
}

const ROADMAP: RoadmapPhase[] = [
  {
    phase: 'NOW',
    status: 'live',
    scope: 'β 운영 중',
    label: '마포구 16개 행정동 분석 + 프랜차이즈 본부 영업팀 SaaS β 운영',
    metric: '1구 · 16동',
  },
  {
    phase: 'NEXT',
    status: 'next',
    scope: 'Q3 2026',
    label: '서울 전체 25개 구 확장 + 프랜차이즈 브랜드 DB 고도화',
    metric: '25구 · 423동',
  },
  {
    phase: 'FUTURE',
    status: 'future',
    scope: '2027+',
    label: '전국 단위 확장 + 실시간 매출 데이터 연동 + 글로벌 확장',
    metric: '전국 · API 연동',
  },
];

interface HeroMetric {
  value: string;
  label: string;
  sub: string;
}

const HERO_METRICS: HeroMetric[] = [
  { value: '5', label: 'Differentiators', sub: '기존 도구와 본질적 차이' },
  { value: '6', label: 'Comparison', sub: '구버전 → SPOTTER' },
  { value: 'B2B', label: 'Persona', sub: '프랜차이즈 본부 영업팀' },
  { value: 'β', label: 'Stage', sub: '마포 → 서울 25구 확장' },
];

/** 섹션 헤더 라벨 — § 마커 + 가로 라인 + 우측 메타 (EnginePage 와 동일 톤) */
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

export default function AboutPage(_: { onBack?: () => void }) {
  const buildVersion = 'v3.8.2';
  const lastSync = new Date().toISOString().slice(0, 10);

  return (
    <div className="absolute inset-0 z-20 overflow-y-auto bg-background text-foreground pb-32 custom-scrollbar">
      {/* Subtle dot grid texture */}
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
            ▎About SPOTTER
          </p>
          <p className="text-lg md:text-xl text-muted-foreground mb-3 tracking-wide">
            기존 상권분석 도구는{' '}
            <span className="text-primary font-bold text-2xl md:text-3xl">'지금'</span>만
            보여줍니다.
          </p>
          <h1 className="text-5xl md:text-7xl font-black tracking-tighter leading-[0.95] mt-6 mb-10 uppercase">
            We forecast
            <br />
            <span className="text-primary">what comes next.</span>
          </h1>

          {/* 인용구 카드 — 3 question */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-12">
            {[
              '이 자리에 매장을 내면, 1년 뒤 매출은 얼마일까?',
              '같은 브랜드 3호점이 1호점 매출을 얼마나 잡아먹을까?',
              '옆에 경쟁 매장이 들어오면, 내 생존 확률은?',
            ].map((q, i) => (
              <div
                key={i}
                className="rounded-2xl border border-border bg-secondary p-5 transition-colors hover:border-primary/40"
              >
                <Quote className="text-primary/40 mb-3" size={18} strokeWidth={2} />
                <p className="text-sm md:text-base font-medium text-foreground leading-relaxed break-keep">
                  {q}
                </p>
              </div>
            ))}
          </div>

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

        {/* ── § 01 What We Do Differently ── */}
        <section className="py-16 animate-[fadeSlideIn_1.2s_ease-out]">
          <SectionLabel label="01 · What We Do Differently" meta="5 differentiators" />
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            기존 도구가 못 하는 5가지
          </h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            상권 스냅샷이 아닌 정량 시뮬레이션 — 매출·경쟁·생존을 시계열로 예측하고, 의사결정에 직접
            인용 가능한 근거 형태로 제공합니다.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {FEATURES.map((f) => (
              <div
                key={f.num}
                className="group relative rounded-2xl border border-border bg-secondary p-6 transition-all hover:border-primary/40 hover:shadow-lg"
              >
                {/* 우상단 sequential index */}
                <div className="absolute right-5 top-5 text-[0.5625rem] font-mono tabular-nums text-muted-foreground/70">
                  D / {f.num}
                </div>
                <div className="mb-3">
                  <div className="text-xs font-mono uppercase tracking-widest text-primary mb-2">
                    ▎{f.category}
                  </div>
                  <h3 className="text-lg md:text-xl font-black tracking-tight text-foreground">
                    {f.title}
                  </h3>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed break-keep mb-5">
                  {f.desc}
                </p>
                {/* metric chip — 단일 정량 신호 */}
                <div className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
                  <span className="text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
                    {f.metric.label}
                  </span>
                  <span className="text-[0.75rem] font-black tabular-nums text-foreground">
                    {f.metric.value}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── § 02 Comparison ── */}
        <section className="py-16 animate-[fadeSlideIn_1.4s_ease-out]">
          <SectionLabel label="02 · Compared to Existing" meta="6 row diff" />
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            구버전 → SPOTTER
          </h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            기존 컨설팅·리포트·BI 도구가 제공하던 결과 형태와 SPOTTER 의 출력 형태를 한 눈에 비교.
          </p>
          <div className="rounded-2xl border border-border bg-card overflow-hidden">
            {/* 헤더 row */}
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-6 px-6 py-3 border-b border-border bg-secondary/60">
              <span className="text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
                기존 도구
              </span>
              <span className="w-6" />
              <span className="text-[0.5625rem] font-mono uppercase tracking-widest text-primary text-right">
                SPOTTER
              </span>
            </div>
            {COMPARISONS.map((c, i) => (
              <div
                key={i}
                className="grid grid-cols-[1fr_auto_1fr] items-center gap-6 px-6 py-4 border-b border-border/50 last:border-b-0 transition-colors hover:bg-secondary/30"
              >
                <span className="text-sm text-muted-foreground line-through decoration-border/60 break-keep">
                  {c.old}
                </span>
                <span className="font-mono text-xs text-border shrink-0">→</span>
                <span className="text-sm md:text-base font-bold text-primary break-keep text-right">
                  {c.now}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* ── § 03 Data & Trust ── */}
        <section className="py-16 animate-[fadeSlideIn_1.6s_ease-out]">
          <SectionLabel label="03 · Data & Trust" meta="public sources only" />
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            검증된 공공데이터만 사용합니다
          </h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            모든 추론은 카테고리별 freshness 와 출처가 추적 가능한 공공데이터 + 행정안전부 표준 코드
            기반.
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

        {/* ── § 04 Roadmap ── */}
        <section className="py-16 animate-[fadeSlideIn_1.8s_ease-out]">
          <SectionLabel label="04 · Roadmap" meta="Mapo β → 서울 → 전국" />
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">확장 계획</h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            마포 16동 β 운영을 거쳐 서울 25개 구 → 전국으로 점진 확장. 본부 영업팀의 실 사용 피드백
            기반 우선순위.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {ROADMAP.map((r) => {
              const isLive = r.status === 'live';
              const dotColor = isLive
                ? 'bg-success'
                : r.status === 'next'
                  ? 'bg-primary'
                  : 'bg-muted-foreground/40';
              const badgeStyle = isLive
                ? 'border-success/30 bg-success/10 text-success'
                : r.status === 'next'
                  ? 'border-primary/30 bg-primary/10 text-primary'
                  : 'border-border bg-secondary text-muted-foreground';
              return (
                <div
                  key={r.phase}
                  className="relative rounded-2xl border border-border bg-card p-6 transition-colors hover:border-primary/40"
                >
                  {/* phase 마커 */}
                  <div className="flex items-center gap-2 mb-4">
                    <span className={`relative flex h-2 w-2`}>
                      {isLive && (
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
                      )}
                      <span className={`relative inline-flex h-2 w-2 rounded-full ${dotColor}`} />
                    </span>
                    <span className="text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
                      Phase
                    </span>
                  </div>
                  <h3 className="text-2xl font-black tracking-tighter text-foreground">
                    {r.phase}
                  </h3>
                  <span
                    className={`inline-block mt-2 rounded-full border px-2.5 py-0.5 text-[0.5625rem] font-black uppercase tracking-widest ${badgeStyle}`}
                  >
                    {r.scope}
                  </span>
                  <p className="mt-4 text-sm text-foreground leading-relaxed break-keep">
                    {r.label}
                  </p>
                  <div className="mt-4 pt-4 border-t border-border/60 text-[0.625rem] font-mono uppercase tracking-widest text-muted-foreground">
                    {r.metric}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── Footer signature ── */}
        <footer className="mt-12 pt-8 border-t border-border/60">
          <div className="flex flex-wrap items-center justify-between gap-3 text-[0.625rem] font-mono uppercase tracking-widest text-muted-foreground">
            <span>▎SPOTTER · About</span>
            <span>
              build {buildVersion} · {lastSync}
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
