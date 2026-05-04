/**
 * EnginePage — SPOTTER 의 엔진 (Multi-Agent + ML) 소개 에디토리얼.
 * 헤더는 App.tsx 의 global header 가 제공 (scene !== 'intro' 일 때 fixed h-20).
 * 본문만 렌더.
 *
 * 구조:
 *  - Hero: "The Engine Behind SPOTTER"
 *  - § Multi-Agent Layer: 9 페르소나 (frontend/src/assets/agents/*.png 활용)
 *  - § ML Models: TCN / LightGBM+TCN / SHAP / Emerging / ABM / RAG
 *  - § Data Sources: 공공데이터 19+ 출처
 */

import marketIcon from '../../assets/agents/market.png';
import populationIcon from '../../assets/agents/population.png';
import legalIcon from '../../assets/agents/legal.png';
import rankingIcon from '../../assets/agents/ranking.png';
import inflowIcon from '../../assets/agents/inflow.png';
import synthesisIcon from '../../assets/agents/synthesis.png';
import demographicIcon from '../../assets/agents/demographic.png';
import trendIcon from '../../assets/agents/trend.png';
import competitorIcon from '../../assets/agents/competitor.png';

const AGENTS: { name: string; role: string; iconSrc: string }[] = [
  {
    name: 'Market Analyst',
    role: '상권 지형·경쟁 강도·임대 인덱스 분석. HHI / 다양도 / 500m 반경 매장 분포.',
    iconSrc: marketIcon,
  },
  {
    name: 'Population Analyst',
    role: '생활인구·유동 패턴·연령 분포. 24시간대 패턴 + 분기별 거주 인구 변화.',
    iconSrc: populationIcon,
  },
  {
    name: 'Legal Risk',
    role: '가맹사업법 / 상가임대차보호법 / 학교환경위생정화구역 RAG 기반 자동 검토.',
    iconSrc: legalIcon,
  },
  {
    name: 'District Ranking',
    role: '16동 5지표 정량 비교 + winner / top_3 선정. 업종 적합도 점수화.',
    iconSrc: rankingIcon,
  },
  {
    name: 'Inflow Analyst',
    role: '지하철 접근성·시간대별 유입·교통 hub 보정. 출점 적합 spot score 산출.',
    iconSrc: inflowIcon,
  },
  {
    name: 'Demographic Depth',
    role: '소득 수준·가구 구조·고령 비율. 본부 영업팀의 페르소나 매칭 핵심 자료.',
    iconSrc: demographicIcon,
  },
  {
    name: 'Trend Forecaster',
    role: 'Naver DataLab 검색 트렌드·ECOS 거시 지표·상권 change_ix 결합 12개월 예측.',
    iconSrc: trendIcon,
  },
  {
    name: 'Competitor Intel',
    role: '브랜드별 카니발리제이션·차별화 포지션·동일 업종 폐업률 추세.',
    iconSrc: competitorIcon,
  },
  {
    name: 'Synthesis',
    role: '8 에이전트 출력 통합 → 본부 영업팀이 의사결정에 쓸 자연어 종합 판단.',
    iconSrc: synthesisIcon,
  },
];

const ML_MODELS: { name: string; tag: string; desc: string }[] = [
  {
    name: 'TCN — Temporal Convolutional Network',
    tag: '매출 4분기 예측',
    desc: '동×업종 시계열을 4분기 매출(점단·신뢰구간 상하한) 로 예측. 점포당 매출 환산.',
  },
  {
    name: 'LightGBM + TCN Ensemble',
    tag: '폐업 위험도',
    desc: 'Stage 1 산업 prior(LightGBM) × Stage 2 시계열 위험도(TCN) ensemble. 0~1 정규화.',
  },
  {
    name: 'SHAP Explainability',
    tag: 'ML 해석가능성',
    desc: '각 위험도 예측의 기여 요인을 자연어 인사이트로 변환. 본부 영업팀 페르소나에 맞춰 차트 X.',
  },
  {
    name: 'Emerging Classifier',
    tag: '상권 조기감지',
    desc: '서울시 공식 change_ix(LL/LH/HL/HH) + anomaly score. 신흥/정상/쇠퇴 3단계 신호등.',
  },
  {
    name: 'ABM — Agent Based Modeling',
    tag: 'What-if 시뮬레이션',
    desc: '브랜드 진입·임대료·최저임금 변화 시나리오를 행위자 기반으로 동적 시뮬.',
  },
  {
    name: 'RAG — Retrieval Augmented Generation',
    tag: '법률 검토',
    desc: '가맹사업법·상가임대차 분쟁 사례 DB 를 LLM 이 retrieval → 위반/주의 자동 판단.',
  },
];

const DATA_SOURCES = [
  '소상공인시장진흥공단',
  '서울 생활인구 (KT)',
  '서울 상권분석 (golmok)',
  '서울 상권 변화 지수',
  '통계청 SGIS',
  '국토부 실거래가',
  '공정위 정보공개서',
  'Naver DataLab',
  '한국은행 ECOS',
  '서울 따릉이',
  '서울 지하철 승하차',
];

export default function EnginePage(_: { onBack?: () => void }) {
  return (
    <div className="absolute inset-0 z-20 overflow-y-auto bg-background text-foreground pb-32 custom-scrollbar">
      <div className="max-w-6xl mx-auto px-8 md:px-16 pt-20">
        {/* ── Hero ── */}
        <section className="lg:min-h-[60vh] flex flex-col justify-center py-16 lg:py-0 animate-[fadeSlideIn_1s_ease-out]">
          <p className="text-lg md:text-xl text-muted-foreground mb-6 tracking-wide">
            데이터 기반 의사결정의 무게는,
          </p>
          <h1 className="text-5xl md:text-7xl font-black tracking-tighter leading-[0.95] mb-8 uppercase">
            The Engine
            <br />
            <span className="text-primary">Behind SPOTTER</span>
          </h1>
          <p className="text-base md:text-lg text-muted-foreground max-w-2xl break-keep leading-relaxed">
            9 멀티 에이전트가 의사결정 레이어를, 6 종 ML 모델이 정량 예측 레이어를 담당합니다.
            <br />
            서울 19+ 공공데이터를 기반으로 학습·추론하며, 본부 영업팀의 출점 결정에 정량 근거를
            제공합니다.
          </p>
        </section>

        {/* ── § Multi-Agent Layer ── */}
        <section className="py-16 animate-[fadeSlideIn_1.2s_ease-out]">
          <div className="mb-10 flex items-center gap-4">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-border" />
            <span className="text-[0.625rem] font-mono uppercase tracking-[0.25em] text-muted-foreground">
              § Multi-Agent Layer · 9
            </span>
            <div className="h-px flex-1 bg-gradient-to-l from-transparent via-border to-border" />
          </div>
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            의사결정을 분담하는 9 에이전트
          </h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            LangGraph 기반 병렬 실행. 각 에이전트는 단일 책임 범위 안에서 자기 도메인 데이터를
            해석하고, Synthesis 가 8 출력을 통합해 종합 판단을 산출합니다.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {AGENTS.map((a) => (
              <div
                key={a.name}
                className="group rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-lg"
              >
                <div className="flex items-center gap-3 mb-3">
                  <img
                    src={a.iconSrc}
                    alt=""
                    className="h-10 w-10 rounded-full object-cover ring-1 ring-border"
                    loading="lazy"
                  />
                  <div className="text-sm font-black tracking-tight text-foreground">{a.name}</div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed break-keep">{a.role}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── § ML Models ── */}
        <section className="py-16 animate-[fadeSlideIn_1.4s_ease-out]">
          <div className="mb-10 flex items-center gap-4">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-border" />
            <span className="text-[0.625rem] font-mono uppercase tracking-[0.25em] text-muted-foreground">
              § ML Models · 6
            </span>
            <div className="h-px flex-1 bg-gradient-to-l from-transparent via-border to-border" />
          </div>
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            정량 예측 레이어
          </h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            매출·폐업·상권 변화·법률 리스크 — 본부 영업팀이 의심 없이 인용할 수 있는 수준의 정량
            엔진을 직접 학습·튜닝했습니다.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {ML_MODELS.map((m) => (
              <div key={m.name} className="rounded-2xl border border-border bg-card p-6">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <div className="text-base font-black tracking-tight text-foreground">
                    {m.name}
                  </div>
                  <span className="shrink-0 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-[0.625rem] font-black uppercase tracking-widest text-primary">
                    {m.tag}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed break-keep">{m.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── § Data Sources ── */}
        <section className="py-16 animate-[fadeSlideIn_1.6s_ease-out]">
          <div className="mb-10 flex items-center gap-4">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-border" />
            <span className="text-[0.625rem] font-mono uppercase tracking-[0.25em] text-muted-foreground">
              § Data Pipeline · 19+
            </span>
            <div className="h-px flex-1 bg-gradient-to-l from-transparent via-border to-border" />
          </div>
          <h2 className="text-3xl md:text-4xl font-black tracking-tighter mb-3">
            서울 공공데이터 19+ 출처
          </h2>
          <p className="text-sm text-muted-foreground mb-10 max-w-2xl break-keep leading-relaxed">
            모든 추론은 공공데이터 + 행정안전부 표준 코드 기반. 학습 시점 freshness · 출처 추적
            가능.
          </p>
          <div className="flex flex-wrap gap-2">
            {DATA_SOURCES.map((d) => (
              <span
                key={d}
                className="inline-flex items-center rounded-full border border-border bg-secondary px-4 py-2 text-xs font-bold text-foreground/80"
              >
                {d}
              </span>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
