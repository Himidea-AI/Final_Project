/**
 * AboutPage — 프로젝트 소개 에디토리얼 랜딩 (App.tsx에서 추출, Phase C Round 1).
 * Hero / 5가지 차별점 / 비교표 / 데이터 + 로드맵.
 */

import { ChevronRight } from 'lucide-react';

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

/* ═══════════════════════════════════════════════════════
   About Page — 프로젝트 소개 에디토리얼 랜딩
   ═══════════════════════════════════════════════════════
   - Section 1: Hero (문제 정의 + "SPOTTER는 여기서 시작합니다")
   - Section 2: 5가지 차별점 (워터마크 넘버링)
   - Section 3: 기존 서비스 비교표 (취소선 vs 앰버 강조)
   - Section 4: 7개 공공데이터 배지 + NOW/NEXT/FUTURE 로드맵
*/

export default function AboutPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="absolute inset-0 z-20 overflow-y-auto bg-card/95 backdrop-blur-sm text-foreground pb-32 custom-scrollbar">
      {/* Header */}
      <div className="fixed top-0 left-0 w-full h-24 border-b border-border/50 flex items-center px-8 md:px-16 bg-card/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.svg" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-foreground">SPOTTER</span>
          </button>
          <span className="text-border">/</span>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-8 md:px-16 pt-24">
        {/* ── Section 1: Hero ── */}
        <section className="min-h-[80vh] flex flex-col justify-center animate-[fadeSlideIn_1s_ease-out]">
          <p className="text-lg md:text-xl text-muted-foreground mb-6 tracking-wide">
            기존 상권분석 도구는{' '}
            <span className="text-primary font-bold text-2xl md:text-3xl">'지금'</span>만
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
                className="border-l-2 border-primary pl-6 py-2"
                style={{ animationDelay: `${i * 150 + 300}ms` }}
              >
                <p className="text-xl md:text-2xl font-medium text-foreground/80 italic">"{q}"</p>
              </div>
            ))}
          </div>

          <h2 className="text-3xl md:text-5xl font-black mt-10 tracking-tight leading-tight">
            <span className="text-primary">SPOTTER</span>는
            <br />
            여기서 시작합니다.
          </h2>
        </section>

        {/* ── Section 2: What We Do Differently ── */}
        <section className="py-24">
          <div className="flex items-center gap-4 mb-16">
            <div className="w-12 h-px bg-primary" />
            <h3 className="text-xs font-mono tracking-[0.3em] text-muted-foreground uppercase">
              What We Do Differently
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
            {FEATURES.map((f) => (
              <div key={f.num} className="relative pl-2 pt-6">
                <span className="font-mono text-5xl md:text-7xl font-black text-border absolute -top-6 -left-4 opacity-50 z-0 select-none">
                  {f.num}
                </span>
                <h4 className="text-xl font-bold text-foreground mb-3 relative z-10">{f.title}</h4>
                <p className="text-muted-foreground leading-relaxed relative z-10">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Section 3: Comparison ── */}
        <section className="py-24">
          <div className="flex items-center gap-4 mb-16">
            <div className="w-12 h-px bg-primary" />
            <h3 className="text-xs font-mono tracking-[0.3em] text-muted-foreground uppercase">
              Compared to Existing Solutions
            </h3>
          </div>

          <div className="flex flex-col">
            {COMPARISONS.map((c, i) => (
              <div
                key={i}
                className="flex justify-between items-center py-4 border-b border-border/50"
              >
                <span className="text-muted-foreground line-through decoration-border flex-1 text-sm">
                  {c.old}
                </span>
                <span className="text-border font-mono mx-6 shrink-0">{c.arrow}</span>
                <span className="text-primary font-bold text-lg flex-1 text-right">{c.now}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Section 4: Data & Roadmap ── */}
        <section className="py-24">
          {/* Data sources */}
          <div className="mb-20">
            <div className="flex items-center gap-4 mb-10">
              <div className="w-12 h-px bg-primary" />
              <h3 className="text-xs font-mono tracking-[0.3em] text-muted-foreground uppercase">
                Data &amp; Trust
              </h3>
            </div>
            <p className="text-muted-foreground mb-6 text-sm">
              7개 공공데이터 API 기반 — 신뢰할 수 있는 데이터만 사용합니다.
            </p>
            <div className="flex flex-wrap gap-3">
              {DATA_SOURCES.map((src) => (
                <span
                  key={src}
                  className="px-4 py-2 rounded-full border border-border bg-card text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors cursor-default"
                >
                  {src}
                </span>
              ))}
            </div>
          </div>

          {/* Roadmap */}
          <div>
            <div className="flex items-center gap-4 mb-10">
              <div className="w-12 h-px bg-primary" />
              <h3 className="text-xs font-mono tracking-[0.3em] text-muted-foreground uppercase">
                Roadmap
              </h3>
            </div>
            <div className="flex flex-col gap-8">
              {ROADMAP.map((r, i) => (
                <div key={i} className="flex items-start gap-6">
                  <span className="font-mono text-primary w-24 shrink-0 text-sm font-bold pt-0.5">
                    {r.phase}
                  </span>
                  <div className="flex items-start gap-4">
                    <div className="mt-2 w-2 h-2 rounded-full bg-primary shrink-0" />
                    <p className="text-foreground leading-relaxed">{r.label}</p>
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
