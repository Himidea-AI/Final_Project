/**
 * HiddenPDFTemplate (v13.0) — mode-aware PDF 템플릿.
 *
 * 화면에는 보이지 않고 (absolute top-[-9999px]) html2canvas 캡처 전용.
 * 각 페이지는 794x1123 고정 → jsPDF로 페이지별 변환.
 *
 * mode:
 *  - 'foresee' : ML 예측 PDF (매출/폐업/세그먼트/유동/BEP/SHAP, 7페이지)
 *  - 'ai'      : AI 분석 PDF (종합/랭킹/법률/트렌드/인구/근거, 8페이지)
 *  - 'abm'     : ABM 시뮬 PDF (KPI/자기잠식/동별/시나리오, 5페이지)
 *  - 'legacy'  : 구 통합 템플릿 (호환 유지)
 *
 * recharts는 html2canvas 캡처 호환성이 떨어지므로 모든 차트는 SVG inline 또는
 * div+%width 막대로 직접 그린다. 기존 KPI grid 스타일과 일관.
 */

import { forwardRef } from 'react';
import { formatDocumentId } from '../../types/simulationHistory';
import type { CustomerSegment, ShapFeatureItem } from '../../types';
import type { ForeseePdfData, AiPdfData, AbmPdfData } from '../../utils/pdfPropsBuilder';

/* ═══════════════════════════════════════════════════════
   상세 데이터 테이블 — 정렬 가능한 row data (legacy mode)
   ═══════════════════════════════════════════════════════ */
export interface CannRow {
  [key: string]: string;
  name: string;
  distance: string;
  impact: string;
  status: string;
}
export interface NeighborhoodRow {
  [key: string]: string;
  name: string;
  score: string;
  closureRate: string;
  bep: string;
}

export type PdfMode = 'foresee' | 'ai' | 'abm' | 'legacy';

interface HiddenPDFTemplateProps {
  mode?: PdfMode;
  districtFull: string;
  reportDate: string;
  /** 저장된 이력 ID(BIGINT) — null이면 "SPTR-DRAFT-…" 표시. Saved면 "SPTR-000142" 같은 정식 번호. */
  savedHistoryId?: number | null;

  /** legacy mode 전용 */
  stats?: { title: string; value: string; trend: string }[];
  cannibalizationRows?: CannRow[];
  neighborhoodRows?: NeighborhoodRow[];
  insights?: { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[];
  /** legacy mode customer_revenue P1-C 타겟 고객 매출 분석 — null 이면 PDF 페이지 자체 생략 */
  customerSegment?: CustomerSegment | null;

  /** foresee mode 전용 */
  foresee?: ForeseePdfData;
  /** ai mode 전용 */
  ai?: AiPdfData;
  /** abm mode 전용 */
  abm?: AbmPdfData;
}

// SPOTTER 로고 SVG 경로 (Light 테마 — Deep Blue #002cd1)
const SPOTTER_LOGO_PATHS = (
  <>
    <path
      d="M18.5147 0C15.4686 0 12.5473 1.21005 10.3934 3.36396L3.36396 10.3934C1.21005 12.5473 0 15.4686 0 18.5147C0 24.8579 5.14214 30 11.4853 30C14.5314 30 17.4527 28.7899 19.6066 26.636L24.4689 21.7737C24.469 21.7738 24.4689 21.7736 24.4689 21.7737L38.636 7.6066C39.6647 6.57791 41.0599 6 42.5147 6C44.9503 6 47.0152 7.58741 47.7311 9.78407L52.2022 5.31296C50.1625 2.11834 46.586 0 42.5147 0C39.4686 0 36.5473 1.21005 34.3934 3.36396L15.364 22.3934C14.3353 23.4221 12.9401 24 11.4853 24C8.45584 24 6 21.5442 6 18.5147C6 17.0599 6.57791 15.6647 7.6066 14.636L14.636 7.6066C15.6647 6.57791 17.0599 6 18.5147 6C20.9504 6 23.0152 7.58748 23.7311 9.78421L28.2023 5.31307C26.1626 2.1184 22.5861 0 18.5147 0Z"
      fill="#002cd1"
    />
    <path
      d="M39.364 22.3934C38.3353 23.4221 36.9401 24 35.4853 24C33.05 24 30.9853 22.413 30.2692 20.2167L25.7982 24.6877C27.838 27.8819 31.4143 30 35.4853 30C38.5314 30 41.4527 28.7899 43.6066 26.636L62.636 7.6066C63.6647 6.57791 65.0599 6 66.5147 6C69.5442 6 72 8.45584 72 11.4853C72 12.9401 71.4221 14.3353 70.3934 15.364L63.364 22.3934C62.3353 23.4221 60.9401 24 59.4853 24C57.0498 24 54.985 22.4127 54.269 20.2162L49.798 24.6873C51.8377 27.8818 55.4141 30 59.4853 30C62.5314 30 65.4527 28.7899 67.6066 26.636L74.636 19.6066C76.7899 17.4527 78 14.5314 78 11.4853C78 5.14214 72.8579 0 66.5147 0C63.4686 0 60.5473 1.21005 58.3934 3.36396L39.364 22.3934Z"
      fill="#002cd1"
    />
  </>
);

const PAGE_CLASS = 'w-[794px] h-[1123px] p-12 bg-white text-slate-900 relative flex flex-col';

/* ═══════════════════════════════════════════════════════
   숫자 포맷 헬퍼 — 큰 금액을 좁은 KPI 박스에 맞게 축약
   ═══════════════════════════════════════════════════════ */
/** 원 단위 큰 숫자를 한국형 만/억 단위로 축약. 1,234,567 → "123.5만". */
function formatCompactWon(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${sign}${(abs / 10_000).toFixed(1)}만`;
  return `${sign}${Math.round(abs).toLocaleString('ko-KR')}`;
}

/** 백만원 단위 표기 (M). 36,000,000 → "₩36.0M". */
function formatMillionWon(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `₩${(value / 1_000_000).toFixed(1)}M`;
}

/** 부호 포함 퍼센트. 0.082 → "+8.2%" / -0.05 → "-5.0%" */
function formatSignedPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

function PDFPageHeader({
  pageNumber,
  totalPages,
  districtFull,
  modeLabel,
}: {
  pageNumber: number;
  totalPages: number;
  districtFull: string;
  modeLabel?: string;
}) {
  return (
    <div className="flex justify-between items-center border-b border-slate-200 pb-4">
      <div className="flex items-center gap-2.5">
        <svg width="36" height="14" viewBox="0 0 78 30" fill="none">
          {SPOTTER_LOGO_PATHS}
        </svg>
        <span className="text-[0.8125rem] font-black tracking-[0.18em] text-slate-900">
          SPOTTER
        </span>
        <span className="text-[0.625rem] text-slate-400 ml-1">
          / {districtFull}
          {modeLabel ? ` · ${modeLabel}` : ' 상권 분석 리포트'}
        </span>
      </div>
      <span className="text-[0.625rem] text-slate-400 font-mono tracking-wider">
        PAGE {pageNumber} / {totalPages}
      </span>
    </div>
  );
}

function PDFPageFooter({ reportDate }: { reportDate: string }) {
  return (
    <div className="text-[0.5625rem] text-slate-400 font-mono border-t border-slate-200 pt-3 flex justify-between tracking-wider">
      <span>© PROJECT SPOTTER · CONFIDENTIAL</span>
      <span>GENERATED {reportDate}</span>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   공용 표지 페이지
   ═══════════════════════════════════════════════════════ */
function CoverPage({
  districtFull,
  reportDate,
  docId,
  subtitle,
  badge,
}: {
  districtFull: string;
  reportDate: string;
  docId: string;
  subtitle: string;
  badge: string;
}) {
  return (
    <div className={PAGE_CLASS}>
      <div className="flex-1 flex flex-col items-center justify-center">
        <svg width="200" height="78" viewBox="0 0 78 30" fill="none" className="mb-10">
          {SPOTTER_LOGO_PATHS}
        </svg>
        <p className="text-black font-mono text-[0.6875rem] tracking-[0.3em] border border-black px-5 py-1.5 rounded-full bg-white mb-16">
          {badge}
        </p>
        <h1 className="text-[2.75rem] font-black text-slate-900 text-center leading-[1.2] tracking-tight">
          {districtFull}
          <br />
          {subtitle}
        </h1>
        <p className="text-sm text-slate-500 mt-6 tracking-wide">
          SPOTTER AI · LangGraph Multi-Agent
        </p>
      </div>

      <div className="flex justify-between items-end font-mono text-[0.625rem] text-slate-500 pt-6 border-t border-slate-200">
        <div className="space-y-1.5">
          <p className="tracking-wider">GENERATED · {reportDate}</p>
          <p className="tracking-wider">REQUESTED BY · SPOTTER-HQ</p>
          <p className="tracking-wider">DOCUMENT ID · {docId}</p>
        </div>
        <div className="font-bold text-black text-sm tracking-[0.25em]">CONFIDENTIAL</div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   공용 막대 차트 — div+%width 방식 (html2canvas 안전)
   ═══════════════════════════════════════════════════════ */
function HorizontalBarRow({
  label,
  valueText,
  ratio,
  color = '#002cd1',
  labelWidth = 'w-20',
}: {
  label: string;
  valueText: string;
  ratio: number; // 0~1
  color?: string;
  labelWidth?: string;
}) {
  const w = Math.max(0, Math.min(100, Math.round(ratio * 100)));
  return (
    <div className="flex items-center gap-2">
      <div className={`${labelWidth} shrink-0 text-[0.625rem] text-slate-700`}>{label}</div>
      <div className="relative flex-1 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full" style={{ width: `${w}%`, background: color }} />
      </div>
      <div className="w-16 shrink-0 text-right text-[0.625rem] font-mono text-slate-700">
        {valueText}
      </div>
    </div>
  );
}

function VerticalBarChart({
  bars,
  height = 140,
}: {
  bars: { label: string; value: number; valueText?: string; color?: string }[];
  height?: number;
}) {
  const maxV = Math.max(0.01, ...bars.map((b) => Math.max(0, b.value)));
  return (
    <div className="flex items-end gap-2" style={{ height }}>
      {bars.map((b, i) => {
        const h = Math.max(2, Math.round((Math.max(0, b.value) / maxV) * (height - 30)));
        return (
          <div key={i} className="flex-1 flex flex-col items-center justify-end">
            <div className="text-[0.5625rem] font-mono text-slate-600 mb-1">
              {b.valueText ?? b.value.toLocaleString('ko-KR')}
            </div>
            <div
              className="w-full rounded-t"
              style={{ height: h, background: b.color ?? '#002cd1' }}
            />
            <div className="text-[0.5625rem] text-slate-500 mt-1.5 tracking-wider">{b.label}</div>
          </div>
        );
      })}
    </div>
  );
}

function SignedBarRow({
  label,
  signedText,
  ratio,
  positive,
}: {
  label: string;
  signedText: string;
  ratio: number; // 0~1 절댓값 비율
  positive: boolean;
}) {
  const w = Math.max(0, Math.min(100, Math.round(ratio * 100)));
  const color = positive ? '#059669' : '#e11d48';
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <div className="w-32 shrink-0 text-[0.625rem] text-slate-700 truncate" title={label}>
        {label}
      </div>
      <div className="relative flex-1 h-3 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full" style={{ width: `${w}%`, background: color }} />
      </div>
      <div
        className="w-24 shrink-0 text-right text-[0.625rem] font-mono font-bold"
        style={{ color }}
      >
        {signedText}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   라인 차트 (SVG inline) — html2canvas 호환
   ═══════════════════════════════════════════════════════ */
function LineChart({
  values,
  width = 600,
  height = 120,
  color = '#002cd1',
  fill = 'rgba(0,44,209,0.10)',
  highlightIndex,
  zeroLine = false,
  labels,
  valueTexts,
}: {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  fill?: string;
  highlightIndex?: number;
  zeroLine?: boolean;
  /** X축 라벨 (예: ['Q1','Q2','Q3','Q4']) — 있으면 SVG 하단에 렌더 */
  labels?: string[];
  /** 각 점 위 값 라벨 (예: ['12.3M','13.5M']) — 있으면 점 위에 작은 텍스트 */
  valueTexts?: string[];
}) {
  if (values.length === 0) {
    return <div className="text-[0.625rem] text-slate-400">데이터 없음</div>;
  }
  const padX = 16;
  const padY = 8;
  const labelH = labels && labels.length > 0 ? 14 : 0;
  const valueH = valueTexts && valueTexts.length > 0 ? 12 : 0;
  const plotH = height - padY * 2 - labelH - valueH;
  const maxV = Math.max(...values, 0);
  const minV = Math.min(...values, 0);
  const range = maxV - minV || 1;
  const stepX = (width - padX * 2) / Math.max(1, values.length - 1);
  const yOf = (v: number) => padY + valueH + plotH - ((v - minV) / range) * plotH;
  const points = values.map((v, i) => `${padX + i * stepX},${yOf(v)}`).join(' ');
  const baseY = padY + valueH + plotH;
  const fillPath =
    `M${padX},${baseY} L` +
    points.split(' ').join(' L') +
    ` L${padX + (values.length - 1) * stepX},${baseY} Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {zeroLine && minV < 0 && maxV > 0 && (
        <line
          x1={padX}
          x2={width - padX}
          y1={yOf(0)}
          y2={yOf(0)}
          stroke="#cbd5e1"
          strokeDasharray="4 3"
          strokeWidth={1}
        />
      )}
      <path d={fillPath} fill={fill} />
      <polyline points={points} fill="none" stroke={color} strokeWidth={2} />
      {values.map((v, i) => (
        <circle
          key={i}
          cx={padX + i * stepX}
          cy={yOf(v)}
          r={i === highlightIndex ? 4 : 3}
          fill={i === highlightIndex ? '#002cd1' : color}
        />
      ))}
      {valueTexts &&
        valueTexts.map((t, i) => (
          <text
            key={`v-${i}`}
            x={padX + i * stepX}
            y={yOf(values[i]) - 6}
            textAnchor="middle"
            fontSize="9"
            fontWeight="700"
            fill="#0f172a"
          >
            {t}
          </text>
        ))}
      {labels &&
        labels.map((lab, i) => (
          <text
            key={`l-${i}`}
            x={padX + i * stepX}
            y={height - 2}
            textAnchor="middle"
            fontSize="9"
            fill="#64748b"
          >
            {lab}
          </text>
        ))}
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════
   도넛 차트 (SVG inline)
   ═══════════════════════════════════════════════════════ */
function DonutChart({
  segments,
  size = 120,
  thickness = 18,
}: {
  segments: { label: string; value: number; color: string }[];
  size?: number;
  thickness?: number;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  let acc = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#e2e8f0" strokeWidth={thickness} />
      {segments.map((seg, i) => {
        const len = (seg.value / total) * circ;
        const dasharray = `${len} ${circ - len}`;
        const dashoffset = -((acc / total) * circ);
        acc += seg.value;
        return (
          <circle
            key={i}
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={seg.color}
            strokeWidth={thickness}
            strokeDasharray={dasharray}
            strokeDashoffset={dashoffset}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        );
      })}
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════
   Stacked Bar (월별 비용 구조 등)
   ═══════════════════════════════════════════════════════ */
function StackedBarRow({
  label,
  segments,
  totalText,
}: {
  label: string;
  segments: { value: number; color: string }[];
  totalText?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <div className="w-20 shrink-0 text-[0.625rem] text-slate-700">{label}</div>
      <div className="relative flex-1 h-4 overflow-hidden rounded bg-slate-100 flex">
        {segments.map((seg, i) => (
          <div
            key={i}
            style={{ width: `${(seg.value / total) * 100}%`, background: seg.color }}
            className="h-full"
          />
        ))}
      </div>
      {totalText && (
        <div className="w-24 shrink-0 text-right text-[0.625rem] font-mono text-slate-700">
          {totalText}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Heatmap-like grid cell (값이 클수록 진한 색)
   ═══════════════════════════════════════════════════════ */
function HeatCell({
  value,
  max,
  baseColor = '0,44,209',
}: {
  value: number;
  max: number;
  baseColor?: string;
}) {
  const ratio = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const alpha = 0.15 + ratio * 0.7;
  return (
    <div
      className="text-[0.5rem] font-mono text-center py-1 rounded-sm"
      style={{
        background: `rgba(${baseColor},${alpha})`,
        color: ratio > 0.55 ? '#fff' : '#0f172a',
      }}
    >
      {value.toLocaleString('ko-KR')}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   소형 인포 카드 — 라벨 + 값 + 보조 텍스트
   ═══════════════════════════════════════════════════════ */
function MiniInfoCard({
  label,
  value,
  hint,
  accent = '#0f172a',
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="border border-slate-200 bg-white p-3 rounded-md">
      <div className="text-[0.5rem] text-slate-500 mb-1 uppercase tracking-wider">{label}</div>
      <div className="text-[0.8125rem] font-bold font-mono leading-tight" style={{ color: accent }}>
        {value}
      </div>
      {hint && <div className="text-[0.5rem] text-slate-500 mt-0.5">{hint}</div>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   섹션 헤더 (h3 + 부제 한 줄)
   ═══════════════════════════════════════════════════════ */
function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-2">
      <h3 className="text-[0.8125rem] font-bold text-slate-900">{title}</h3>
      {subtitle && <p className="text-[0.5625rem] text-slate-500 mt-0.5">{subtitle}</p>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Executive Summary 공용 페이지 — 표지 다음 1페이지
   - kpis: 4~6 카드 (라벨/값/보조설명)
   - verdict: 한줄 결론 (강조 박스)
   - bullets: 핵심 인사이트 3~5 bullet
   ═══════════════════════════════════════════════════════ */
interface ExecSummaryProps {
  pageNumber: number;
  totalPages: number;
  districtFull: string;
  reportDate: string;
  modeLabel: string;
  kpis: { label: string; value: string; sub?: string }[];
  verdict: string;
  bullets: { title: string; body: string }[];
}

function ExecutiveSummaryPage({
  pageNumber,
  totalPages,
  districtFull,
  reportDate,
  modeLabel,
  kpis,
  verdict,
  bullets,
}: ExecSummaryProps) {
  return (
    <div className={PAGE_CLASS}>
      <PDFPageHeader
        pageNumber={pageNumber}
        totalPages={totalPages}
        districtFull={districtFull}
        modeLabel={modeLabel}
      />
      <div className="flex-1 pt-6 flex flex-col gap-4">
        <div>
          <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">Executive Summary</h2>
          <p className="text-[0.625rem] text-slate-500">
            핵심 KPI · 한줄 결론 · 임원 의사결정 지원 요약
          </p>
        </div>

        {/* KPI 그리드 — 3 columns */}
        <div className="grid grid-cols-3 gap-2">
          {kpis.map((k, i) => (
            <div
              key={`exec-kpi-${i}`}
              className="border border-slate-200 rounded-md p-3 bg-white flex flex-col"
            >
              <div className="text-[0.5625rem] font-bold tracking-wider text-slate-500 uppercase">
                {k.label}
              </div>
              <div className="text-[1.125rem] font-black text-slate-900 mt-1 leading-tight">
                {k.value}
              </div>
              {k.sub && <div className="text-[0.5625rem] text-slate-500 mt-0.5">{k.sub}</div>}
            </div>
          ))}
        </div>

        {/* Verdict — 강조 박스 */}
        <div className="border-l-4 border-black bg-slate-50 p-4 rounded-r-md">
          <div className="text-[0.5625rem] font-bold tracking-[0.2em] text-slate-600 uppercase mb-1.5">
            한줄 결론
          </div>
          <div className="text-[0.875rem] font-bold text-slate-900 leading-snug">{verdict}</div>
        </div>

        {/* Bullets */}
        <div>
          <div className="text-[0.6875rem] font-bold text-slate-900 mb-2">핵심 인사이트</div>
          <div className="flex flex-col gap-2">
            {bullets.map((b, i) => (
              <div
                key={`exec-bullet-${i}`}
                className="flex gap-3 p-2.5 border border-slate-200 rounded-md bg-white"
              >
                <div className="flex-shrink-0 w-5 h-5 rounded-full bg-black text-white text-[0.625rem] font-black flex items-center justify-center">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[0.6875rem] font-bold text-slate-900">{b.title}</div>
                  <div
                    className="text-[0.625rem] text-slate-600 mt-0.5 leading-snug"
                    style={{ wordBreak: 'keep-all' }}
                  >
                    {b.body}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <PDFPageFooter reportDate={reportDate} />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   feature 한글 매핑 (closure_top_signals 등 영문 → 한글)
   ═══════════════════════════════════════════════════════ */
const FEATURE_KO_MAP: Record<string, string> = {
  flow_pop: '유동인구',
  rent: '임대료',
  rent_index: '임대료 지수',
  competition: '경쟁밀도',
  competition_density: '경쟁밀도',
  closure: '폐업률',
  age_30: '30대 비율',
  age_20: '20대 비율',
  resident_pop: '거주인구',
  income: '소득수준',
  trend: '산업 트렌드',
};
function featureKo(s: string): string {
  return FEATURE_KO_MAP[s] ?? s;
}

/* ═══════════════════════════════════════════════════════
   FORESEE PDF — 7 페이지
   ═══════════════════════════════════════════════════════ */
function ForeseePages({
  data,
  districtFull,
  reportDate,
  docId,
}: {
  data: ForeseePdfData;
  districtFull: string;
  reportDate: string;
  docId: string;
}) {
  // 페이지 활성/비활성 — 데이터 없으면 graceful skip (customer_segment 패턴)
  const showQuarterly = data.quarterly_projection.length > 0;
  const showClosure = data.closure_risk_score != null || data.closure_rate_recent != null;
  const showSegment = data.customer_segment != null;
  const showBep = data.bep_months != null || (data.profit_simulation?.length ?? 0) > 0;
  const showShap = data.shap_top.length > 0;
  const totalPages =
    1 + // cover
    1 + // exec summary
    (showQuarterly ? 1 : 0) +
    (showClosure ? 1 : 0) +
    (showSegment ? 1 : 0) +
    (showBep ? 1 : 0) +
    (showShap ? 1 : 0);

  let pageNum = 1;
  const headerProps = (n: number) => ({
    pageNumber: n,
    totalPages,
    districtFull,
    modeLabel: 'ML 예측 리포트',
  });

  // Executive Summary 콘텐츠 — Foresee 핵심 KPI 6 + verdict + bullets.
  const closureLevelKo: Record<string, string> = {
    safe: '안전',
    caution: '주의',
    danger: '위험',
    unknown: '미상',
  };
  const closureLabel = data.closure_risk_level
    ? closureLevelKo[data.closure_risk_level] || '—'
    : '—';
  const closureScoreText =
    data.closure_risk_score != null ? `${(data.closure_risk_score * 100).toFixed(1)}%` : '—';
  const yoyText =
    data.quarterly_kpi.length > 0 &&
    data.quarterly_kpi[data.quarterly_kpi.length - 1].yoy_pct != null
      ? formatSignedPercent(data.quarterly_kpi[data.quarterly_kpi.length - 1].yoy_pct)
      : '—';
  const shapTopFeature = data.shap_top.length > 0 ? featureKo(data.shap_top[0].feature) : '—';
  const execKpis = [
    {
      label: '예측 월 매출',
      value: formatCompactWon(data.predicted_monthly_revenue),
      sub: '동·업종 기반 LightGBM',
    },
    {
      label: '폐업 위험도',
      value: closureScoreText,
      sub: `등급 · ${closureLabel}`,
    },
    {
      label: 'BEP 회수',
      value: data.bep_months != null ? `${data.bep_months.toFixed(1)}개월` : '—',
      sub: '기준 시나리오',
    },
    {
      label: '영업 마진율',
      value: data.margin_rate != null ? `${(data.margin_rate * 100).toFixed(1)}%` : '—',
      sub: '비용 구조 기반',
    },
    {
      label: '4Q YoY 성장률',
      value: yoyText,
      sub: '전년 동분기 대비',
    },
    {
      label: '핵심 영향 요인',
      value: shapTopFeature,
      sub: 'SHAP 1순위',
    },
  ];
  const verdictText = (() => {
    const score = data.closure_risk_score;
    const margin = data.margin_rate;
    if (score != null && score >= 0.5) {
      return `${districtFull} 폐업 위험 ${closureScoreText} (${closureLabel}) — 리스크 완화 전 진입 보류 권고.`;
    }
    if (margin != null && margin < 0.05) {
      return `${districtFull} 마진율 ${(margin * 100).toFixed(1)}% — 단가/원가 구조 재검토 필요.`;
    }
    return `${districtFull} 예측 월매출 ${formatCompactWon(data.predicted_monthly_revenue)} · 폐업 위험 ${closureLabel} · BEP ${data.bep_months != null ? `${data.bep_months.toFixed(1)}개월` : '—'} 균형 조건 충족.`;
  })();
  const execBullets: { title: string; body: string }[] = [];
  if (data.closure_top_signal) {
    execBullets.push({
      title: '주요 폐업 신호',
      body: `${data.closure_top_signal} — 모니터링 우선 지표.`,
    });
  }
  if (data.shap_summary.length > 0) {
    execBullets.push({
      title: 'SHAP 요약',
      body: data.shap_summary.slice(0, 2).join(' / '),
    });
  }
  if (data.demographic_extra?.core_age) {
    execBullets.push({
      title: '핵심 고객층',
      body: `${data.demographic_extra.core_age}${data.demographic_extra.core_gender ? ` ${data.demographic_extra.core_gender}` : ''} · 평일/주말 비율 ${data.demographic_extra.weekday_weekend_ratio?.toFixed(2) ?? '—'}`,
    });
  }
  if (execBullets.length === 0) {
    execBullets.push({
      title: '데이터 보강 필요',
      body: '핵심 신호 데이터 부재 — 추가 수집 후 재분석 권고.',
    });
  }

  return (
    <>
      {/* Page 1: Cover */}
      <CoverPage
        districtFull={districtFull}
        reportDate={reportDate}
        docId={docId}
        subtitle="ML 예측 리포트"
        badge="SPOTTER FORESEE · ML PREDICTION REPORT"
      />

      {/* Page 2: Executive Summary */}
      {(() => {
        const n = ++pageNum;
        return (
          <ExecutiveSummaryPage
            key={`exec-foresee-${n}`}
            pageNumber={n}
            totalPages={totalPages}
            districtFull={districtFull}
            reportDate={reportDate}
            modeLabel="ML 예측 리포트"
            kpis={execKpis}
            verdict={verdictText}
            bullets={execBullets.slice(0, 4)}
          />
        );
      })()}

      {/* Page 3: 매출 예측 */}
      {showQuarterly &&
        (() => {
          const n = ++pageNum;
          return (
            <div key={`q-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">01. 매출 예측</h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Quarterly Revenue Forecast · LightGBM 회귀 + LSTM 잔차 보정 · 4분기
                  </p>
                </div>

                {/* 월매출 KPI 3개 */}
                <div className="grid grid-cols-3 gap-2">
                  <KpiCard
                    title="예측 월 매출"
                    value={
                      data.predicted_monthly_revenue != null
                        ? `₩${formatCompactWon(data.predicted_monthly_revenue)}`
                        : '—'
                    }
                    accent="#000000"
                  />
                  <KpiCard
                    title="Q1 분기 매출"
                    value={
                      data.quarterly_projection[0]?.revenue
                        ? `₩${(data.quarterly_projection[0].revenue / 1_000_000).toFixed(1)}M`
                        : '—'
                    }
                  />
                  <KpiCard
                    title="Q1→Q2 성장률"
                    value={(() => {
                      const a = data.quarterly_projection[0]?.revenue ?? 0;
                      const b = data.quarterly_projection[1]?.revenue ?? 0;
                      if (!a) return '—';
                      const g = ((b - a) / a) * 100;
                      return `${g >= 0 ? '+' : ''}${g.toFixed(1)}%`;
                    })()}
                    accent="#000000"
                  />
                </div>

                {/* 분기별 꺾은선 차트 (사용자 요청 2026-05-10 — 막대 → 라인) */}
                <div>
                  <SectionHeader title="분기별 매출 (4분기)" subtitle="단위: 백만원" />
                  <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                    <LineChart
                      values={data.quarterly_projection
                        .slice(0, 4)
                        .map((q) => q.revenue / 1_000_000)}
                      labels={data.quarterly_projection.slice(0, 4).map((q) => `Q${q.quarter}`)}
                      valueTexts={data.quarterly_projection
                        .slice(0, 4)
                        .map((q) => `₩${(q.revenue / 1_000_000).toFixed(1)}M`)}
                      width={680}
                      height={150}
                      color="#000000"
                      fill="rgba(0,0,0,0.06)"
                    />
                  </div>
                </div>

                {/* 분기별 KPI 표 */}
                {data.quarterly_kpi.length > 0 && (
                  <div>
                    <SectionHeader title="분기별 KPI" subtitle="매출 / 전분기 대비 증감률" />
                    <table className="w-full text-[0.625rem]">
                      <thead>
                        <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                          <th className="py-1.5 font-medium">분기</th>
                          <th className="py-1.5 font-medium text-right">매출</th>
                          <th className="py-1.5 font-medium text-right">방문수</th>
                          <th className="py-1.5 font-medium text-right">평균객단가</th>
                          <th className="py-1.5 font-medium text-right">QoQ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.quarterly_kpi.map((q, i) => (
                          <tr key={i} className="border-b border-slate-200">
                            <td className="py-1.5 font-medium text-slate-900">Q{q.quarter}</td>
                            <td className="py-1.5 font-mono text-slate-900 text-right">
                              ₩{q.revenue.toLocaleString('ko-KR')}
                            </td>
                            <td className="py-1.5 font-mono text-slate-600 text-right">
                              {q.visits != null ? q.visits.toLocaleString('ko-KR') : '—'}
                            </td>
                            <td className="py-1.5 font-mono text-slate-600 text-right">
                              {q.avg_ticket != null
                                ? `₩${q.avg_ticket.toLocaleString('ko-KR')}`
                                : '—'}
                            </td>
                            <td
                              className="py-1.5 font-mono font-bold text-right"
                              style={{
                                color: q.yoy_pct == null ? '#94a3b8' : '#000000',
                              }}
                            >
                              {q.yoy_pct == null
                                ? '—'
                                : `${q.yoy_pct >= 0 ? '+' : ''}${q.yoy_pct.toFixed(1)}%`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* 시나리오 비교 */}
                {(data.scenarios || data.scenarios_quarterly) && (
                  <div>
                    <SectionHeader title="시나리오 3종 비교" subtitle="낙관 / 기본 / 비관 분기별" />
                    {data.scenarios && (
                      <div className="grid grid-cols-3 gap-2 mb-2">
                        <ScenarioCard
                          label="낙관 (Q1)"
                          value={data.scenarios.optimistic}
                          color="#000000"
                        />
                        <ScenarioCard
                          label="기본 (Q1)"
                          value={data.scenarios.base}
                          color="#000000"
                        />
                        <ScenarioCard
                          label="비관 (Q1)"
                          value={data.scenarios.pessimistic}
                          color="#000000"
                        />
                      </div>
                    )}
                    {data.scenarios_quarterly && (
                      <table className="w-full text-[0.625rem]">
                        <thead>
                          <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                            <th className="py-1 font-medium">시나리오</th>
                            <th className="py-1 font-medium text-right">Q1</th>
                            <th className="py-1 font-medium text-right">Q2</th>
                            <th className="py-1 font-medium text-right">Q3</th>
                            <th className="py-1 font-medium text-right">Q4</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(
                            [
                              ['낙관', '#000000', data.scenarios_quarterly.optimistic],
                              ['기본', '#000000', data.scenarios_quarterly.base],
                              ['비관', '#000000', data.scenarios_quarterly.pessimistic],
                            ] as const
                          ).map(([label, color, arr], i) => (
                            <tr key={i} className="border-b border-slate-200">
                              <td className="py-1 font-bold" style={{ color }}>
                                {label}
                              </td>
                              {[0, 1, 2, 3].map((qi) => (
                                <td key={qi} className="py-1 font-mono text-slate-700 text-right">
                                  {arr[qi] != null ? `₩${(arr[qi] / 1_000_000).toFixed(1)}M` : '—'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}

                {/* 방법론 footnote */}
                <div className="mt-auto text-[0.5625rem] text-slate-500 leading-relaxed border-t border-slate-200 pt-2">
                  <span className="font-bold">방법론:</span> LightGBM 회귀 (CS×동×분기) + LSTM 잔차
                  보정. 학습 기간 2019Q1–2024Q4, RMSE ~9.2%. 예측 신뢰구간 80% 기본.
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {/* Page 3: 폐업 위험 */}
      {showClosure &&
        (() => {
          const n = ++pageNum;
          const recent = data.closure_rate_recent;
          const lvl = data.closure_risk_level ?? 'unknown';
          // 위험 등급 시각 — 색은 검정 톤, 강조는 굵기/외곽선/도트로.
          const lvlStyle =
            lvl === 'danger'
              ? { color: '#000000', bg: 'bg-slate-100 border-black', dot: '#000000' }
              : lvl === 'caution'
                ? { color: '#1f2937', bg: 'bg-slate-50 border-slate-800', dot: '#1f2937' }
                : { color: '#374151', bg: 'bg-white border-slate-300', dot: '#374151' };
          // 권고사항 — 위험 등급별
          const recoText =
            lvl === 'danger'
              ? '출점 보류 또는 입지 재선정 권장 — 동 평균 대비 위험 신호가 명확합니다.'
              : lvl === 'caution'
                ? '차별화 전략 필수 — 메뉴/가격대/시간대 정합성 점검 후 진입 검토.'
                : '진입 가능 — 모니터링 KPI 설정 후 정상 운영 시작 권장.';
          const benchMax = data.closure_benchmark
            ? Math.max(
                data.closure_benchmark.self_pct ?? 0,
                data.closure_benchmark.dong_avg_pct ?? 0,
                data.closure_benchmark.gu_avg_pct ?? 0,
                0.001,
              )
            : 0.001;
          const featMax = Math.max(
            0.001,
            ...data.closure_top_features.map((f) => Math.abs(f.contribution)),
          );
          return (
            <div key={`c-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    02. 폐업 위험 + 폐업률
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Closure Risk · LightGBM + TCN 앙상블 + 실측 누적 폐업률
                  </p>
                </div>

                {/* KPI 카드 — 위험도 점수 박스 제거 (사용자 요청 2026-05-10). */}
                <div className="grid grid-cols-2 gap-2">
                  <KpiCard
                    title="최근 4Q 평균 폐업률"
                    value={recent != null ? `${(recent * 100).toFixed(2)}%` : '—'}
                  />
                  <KpiCard title="LightGBM Top 신호" value={data.closure_top_signal ?? '—'} />
                </div>

                {/* feature contributions Top 5 */}
                {data.closure_top_features.length > 0 && (
                  <div>
                    <SectionHeader
                      title="LightGBM 기여 신호 Top 5"
                      subtitle="양수 = 위험 가산, 음수 = 위험 차감"
                    />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      {data.closure_top_features.map((f, i) => (
                        <SignedBarRow
                          key={i}
                          label={featureKo(f.feature)}
                          signedText={`${f.contribution >= 0 ? '+' : ''}${(f.contribution * 100).toFixed(1)}%`}
                          ratio={Math.abs(f.contribution) / featMax}
                          positive={f.contribution >= 0}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* 동/자치구/매장 비교 */}
                {data.closure_benchmark && (
                  <div>
                    <SectionHeader
                      title="폐업률 벤치마크"
                      subtitle="우리 매장 vs 동 평균 vs 자치구 평균"
                    />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      <VerticalBarChart
                        bars={[
                          {
                            label: '우리 매장',
                            value: data.closure_benchmark.self_pct ?? 0,
                            valueText:
                              data.closure_benchmark.self_pct != null
                                ? `${(data.closure_benchmark.self_pct * 100).toFixed(2)}%`
                                : '—',
                            color: '#002cd1',
                          },
                          {
                            label: '동 평균',
                            value: data.closure_benchmark.dong_avg_pct ?? 0,
                            valueText:
                              data.closure_benchmark.dong_avg_pct != null
                                ? `${(data.closure_benchmark.dong_avg_pct * 100).toFixed(2)}%`
                                : '—',
                            color: '#94a3b8',
                          },
                          {
                            label: '자치구 평균',
                            value: data.closure_benchmark.gu_avg_pct ?? 0,
                            valueText:
                              data.closure_benchmark.gu_avg_pct != null
                                ? `${(data.closure_benchmark.gu_avg_pct * 100).toFixed(2)}%`
                                : '—',
                            color: '#cbd5e1',
                          },
                        ]}
                        height={90}
                      />
                      <div className="text-[0.5625rem] text-slate-500 mt-2">
                        최대 {(benchMax * 100).toFixed(2)}% 기준 정규화.
                      </div>
                    </div>
                  </div>
                )}

                {/* 12개월 라인 차트 */}
                {data.closure_monthly.length > 0 && (
                  <div>
                    <SectionHeader title="12개월 폐업률 추이" subtitle="실측 누적 (B2 수지니)" />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      <LineChart
                        values={data.closure_monthly.slice(-12)}
                        width={620}
                        height={70}
                        color="#94a3b8"
                        fill="rgba(148,163,184,0.18)"
                      />
                    </div>
                  </div>
                )}

                {/* 위험 등급 매트릭스 + 권고 */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="border border-slate-200 bg-white rounded-md p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                      위험 등급 매트릭스
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full border border-black bg-white inline-block" />
                        <span className="text-[0.625rem] text-slate-700">safe (0~5%)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-slate-500 inline-block" />
                        <span className="text-[0.625rem] text-slate-700">caution (5~15%)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-black inline-block" />
                        <span className="text-[0.625rem] text-slate-700">danger (15%+)</span>
                      </div>
                    </div>
                    <div
                      className="mt-2 text-[0.5625rem] font-bold uppercase tracking-wider"
                      style={{ color: lvlStyle.color }}
                    >
                      현재: {lvl}
                    </div>
                  </div>
                  <div className={`border rounded-md p-3 ${lvlStyle.bg}`}>
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                      권고
                    </div>
                    <p
                      className="text-[0.625rem] leading-relaxed"
                      style={{ color: lvlStyle.color }}
                    >
                      {recoText}
                    </p>
                  </div>
                </div>

                <div className="mt-auto text-[0.5625rem] text-slate-500 leading-relaxed border-t border-slate-200 pt-2">
                  <span className="font-bold">방법론:</span> LightGBM(과거 패턴) + TCN(시계열 흐름)
                  앙상블 — Top features 는 LightGBM SHAP 기여도, 추이는 실측 누적.
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {/* Page 4: 고객 세그먼트 + 유동인구 */}
      {showSegment &&
        (() => {
          const n = ++pageNum;
          const cs = data.customer_segment!;
          // 요일별 — backend 미제공이므로 weekday_weekend_ratio 로 7요일 균등 추정
          const wweRatio = data.demographic_extra?.weekday_weekend_ratio ?? 1;
          const weekdayShare = wweRatio / (wweRatio + 1);
          const weekendShare = 1 / (wweRatio + 1);
          const weeklyBars = [
            { label: '월', value: weekdayShare / 5, color: '#cbd5e1' },
            { label: '화', value: weekdayShare / 5, color: '#cbd5e1' },
            { label: '수', value: weekdayShare / 5, color: '#cbd5e1' },
            { label: '목', value: weekdayShare / 5, color: '#cbd5e1' },
            { label: '금', value: weekdayShare / 5, color: '#cbd5e1' },
            { label: '토', value: weekendShare / 2, color: '#002cd1' },
            { label: '일', value: weekendShare / 2, color: '#002cd1' },
          ];
          return (
            <div key={`s-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    03. 고객 세그먼트 + 유동인구
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Customer Segmentation · 타겟 매출 + 유동인구 피크 + 요일/시간 분포
                  </p>
                </div>

                {/* KPI 4종 — 세그먼트 비율 / 타겟 매출 / 핵심 고객 / 매칭 점수 */}
                <div className="grid grid-cols-4 gap-2">
                  <MiniInfoCard
                    label="세그먼트 비율"
                    value={
                      typeof cs.segment_ratio === 'number'
                        ? `${(cs.segment_ratio * 100).toFixed(1)}%`
                        : '—'
                    }
                    accent="#000000"
                  />
                  <MiniInfoCard
                    label="타겟 매출"
                    value={formatMillionWon(cs.segment_sales)}
                    accent="#000000"
                  />
                  <MiniInfoCard
                    label="핵심 고객"
                    value={
                      data.demographic_extra?.core_age && data.demographic_extra?.core_gender
                        ? `${data.demographic_extra.core_age} ${data.demographic_extra.core_gender}`
                        : '—'
                    }
                  />
                  <MiniInfoCard
                    label="브랜드 매칭"
                    value={
                      data.demographic_extra?.brand_match_score != null
                        ? `${data.demographic_extra.brand_match_score}/100`
                        : '—'
                    }
                  />
                </div>

                {/* 프로필 narrative + 4분면 (연령×성별) */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      프로필 narrative
                    </div>
                    <p className="text-[0.625rem] text-slate-800 leading-relaxed">
                      {cs.profile_summary || '데이터 없음'}
                    </p>
                  </div>
                  <div className="rounded-md border border-slate-200 bg-white p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                      연령대 분포
                    </div>
                    <div className="space-y-1">
                      {(
                        [
                          ['10대', 'age_10_ratio'],
                          ['20대', 'age_20_ratio'],
                          ['30대', 'age_30_ratio'],
                          ['40대', 'age_40_ratio'],
                          ['50대', 'age_50_ratio'],
                          ['60대+', 'age_60_above_ratio'],
                        ] as const
                      ).map(([label, key]) => {
                        const v = cs.dimension_ratios?.[key] ?? 0;
                        return (
                          <HorizontalBarRow
                            key={key}
                            label={label}
                            valueText={`${(v * 100).toFixed(1)}%`}
                            ratio={v}
                            labelWidth="w-12"
                          />
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* 24시간 유동인구 */}
                {data.living_pop_quarter && (
                  <div>
                    <SectionHeader
                      title="24시간 유동인구 분포 (Q1)"
                      subtitle={`피크 ${String(data.living_pop_quarter.peak_time_zone).padStart(2, '0')}:00 · ${Math.round(data.living_pop_quarter.peak_pop).toLocaleString('ko-KR')}명`}
                    />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      <VerticalBarChart
                        bars={data.living_pop_quarter.all_hours
                          .slice(0, 24)
                          .map((h: { time_zone: number; predicted_pop: number }) => ({
                            label: String(h.time_zone).padStart(2, '0'),
                            value: h.predicted_pop,
                            valueText: '',
                            color:
                              h.time_zone === data.living_pop_quarter!.peak_time_zone
                                ? '#002cd1'
                                : '#cbd5e1',
                          }))}
                        height={80}
                      />
                    </div>
                  </div>
                )}

                {/* 요일별 분포 */}
                <div>
                  <SectionHeader
                    title="요일별 방문 분포"
                    subtitle={`평일/주말 비율 ${wweRatio.toFixed(2)} 기반 추정`}
                  />
                  <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                    <VerticalBarChart
                      bars={weeklyBars.map((b) => ({
                        ...b,
                        valueText: `${(b.value * 100).toFixed(1)}%`,
                      }))}
                      height={70}
                    />
                  </div>
                </div>

                {/* 타겟팅 권고 3 카드 */}
                <div className="grid grid-cols-3 gap-2 mt-auto">
                  <div className="border border-slate-300 bg-white rounded-md p-2.5">
                    <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                      채널
                    </div>
                    <p className="text-[0.5625rem] text-slate-700 leading-relaxed">
                      Instagram / 네이버 플레이스 — 핵심 고객 SNS 활동 시간대 광고 집중.
                    </p>
                  </div>
                  <div className="border border-slate-300 bg-white rounded-md p-2.5">
                    <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                      시간
                    </div>
                    <p className="text-[0.5625rem] text-slate-700 leading-relaxed">
                      {data.living_pop_quarter
                        ? `${String(data.living_pop_quarter.peak_time_zone).padStart(2, '0')}:00 전후 30분 집중 마케팅. 점심/저녁 피크 동시 운영.`
                        : '피크 시간대 데이터 없음 — 일반 외식업 12:00 / 19:00 권장.'}
                    </p>
                  </div>
                  <div className="border border-slate-300 bg-slate-50 rounded-md p-2.5">
                    <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                      메시지
                    </div>
                    <p className="text-[0.5625rem] text-slate-700 leading-relaxed">
                      {data.demographic_extra?.core_age && data.demographic_extra?.core_gender
                        ? `${data.demographic_extra.core_age} ${data.demographic_extra.core_gender} 페르소나 타겟 카피·비주얼·메뉴 최적화.`
                        : '핵심 고객 페르소나 정의 후 메시지 차별화 권장.'}
                    </p>
                  </div>
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {/* Page 5: BEP + 재무 시뮬 */}
      {showBep &&
        (() => {
          const n = ++pageNum;
          // 누적 손익에서 break-even 시점 (0 이상) 인덱스
          const bepIndex = data.cumulative_profit_monthly.findIndex((v) => v >= 0);
          return (
            <div key={`b-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    04. BEP + 재무 시뮬레이션
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Break-Even Point · 손익분기점 + 누적 손익 + 비용 구조 + 시나리오별 BEP
                  </p>
                </div>

                {/* KPI 4종 */}
                <div className="grid grid-cols-4 gap-2">
                  <KpiCard
                    title="BEP 도달"
                    value={data.bep_months != null ? `${data.bep_months}개월` : '—'}
                    accent="#000000"
                  />
                  <KpiCard
                    title="월 영업이익"
                    value={
                      data.profit_simulation?.[0]?.operating_profit != null
                        ? formatMillionWon(data.profit_simulation[0].operating_profit / 3)
                        : '—'
                    }
                    accent="#000000"
                  />
                  <KpiCard
                    title="이익률"
                    value={
                      data.margin_rate != null ? `${(data.margin_rate * 100).toFixed(1)}%` : '—'
                    }
                  />
                  <KpiCard
                    title="3년 ROI"
                    value={formatMillionWon(data.three_year_roi?.year3)}
                    accent="#000000"
                  />
                </div>

                {/* 누적 손익 라인 차트 */}
                {data.cumulative_profit_monthly.length > 0 && (
                  <div>
                    <SectionHeader
                      title="12개월 누적 손익"
                      subtitle={
                        bepIndex >= 0 ? `BEP 도달 시점: M${bepIndex + 1}` : '12개월 내 BEP 미달'
                      }
                    />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      <LineChart
                        values={data.cumulative_profit_monthly}
                        width={620}
                        height={90}
                        color="#002cd1"
                        fill="rgba(0,44,209,0.10)"
                        highlightIndex={bepIndex >= 0 ? bepIndex : undefined}
                        zeroLine
                      />
                    </div>
                  </div>
                )}

                {/* 비용 구조 stacked bar */}
                {data.cost_breakdown && (
                  <div>
                    <SectionHeader
                      title="월별 비용 구조"
                      subtitle="임대 / 인건 / 원재료 / 마케팅 (외식업 일반 비율 추정)"
                    />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3 space-y-1">
                      <StackedBarRow
                        label="비용 구성"
                        segments={[
                          { value: data.cost_breakdown.rent ?? 0, color: '#e11d48' },
                          { value: data.cost_breakdown.labor ?? 0, color: '#d97706' },
                          { value: data.cost_breakdown.cogs ?? 0, color: '#002cd1' },
                          { value: data.cost_breakdown.marketing ?? 0, color: '#059669' },
                        ]}
                        totalText={`₩${(
                          ((data.cost_breakdown.rent ?? 0) +
                            (data.cost_breakdown.labor ?? 0) +
                            (data.cost_breakdown.cogs ?? 0) +
                            (data.cost_breakdown.marketing ?? 0)) /
                          1_000_000
                        ).toFixed(1)}M`}
                      />
                      <div className="flex items-center gap-3 text-[0.5625rem] text-slate-600 mt-1">
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-sm bg-rose-600 inline-block" /> 임대 ₩
                          {((data.cost_breakdown.rent ?? 0) / 1_000_000).toFixed(1)}M
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-sm bg-amber-600 inline-block" /> 인건 ₩
                          {((data.cost_breakdown.labor ?? 0) / 1_000_000).toFixed(1)}M
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-sm bg-[#002cd1] inline-block" /> 원재료 ₩
                          {((data.cost_breakdown.cogs ?? 0) / 1_000_000).toFixed(1)}M
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-sm bg-emerald-600 inline-block" /> 마케팅
                          ₩{((data.cost_breakdown.marketing ?? 0) / 1_000_000).toFixed(1)}M
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* 시나리오별 BEP + 분기별 표 */}
                <div className="grid grid-cols-2 gap-2">
                  {data.bep_scenarios && (
                    <div>
                      <SectionHeader title="시나리오별 BEP" subtitle="개월" />
                      <div className="grid grid-cols-3 gap-2">
                        <KpiCard
                          title="낙관"
                          value={
                            data.bep_scenarios.optimistic != null
                              ? `${data.bep_scenarios.optimistic}M`
                              : '—'
                          }
                          accent="#000000"
                        />
                        <KpiCard
                          title="기본"
                          value={
                            data.bep_scenarios.base != null ? `${data.bep_scenarios.base}M` : '—'
                          }
                          accent="#000000"
                        />
                        <KpiCard
                          title="비관"
                          value={
                            data.bep_scenarios.pessimistic != null
                              ? `${data.bep_scenarios.pessimistic}M`
                              : '—'
                          }
                          accent="#000000"
                        />
                      </div>
                    </div>
                  )}
                  {data.three_year_roi && (
                    <div>
                      <SectionHeader title="3년 누적 ROI" subtitle="누적 영업이익" />
                      <div className="grid grid-cols-3 gap-2">
                        <MiniInfoCard
                          label="1년"
                          value={formatMillionWon(data.three_year_roi.year1)}
                          accent="#6b7280"
                        />
                        <MiniInfoCard
                          label="2년"
                          value={formatMillionWon(data.three_year_roi.year2)}
                          accent="#374151"
                        />
                        <MiniInfoCard
                          label="3년"
                          value={formatMillionWon(data.three_year_roi.year3)}
                          accent="#000000"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* 분기별 재무 시뮬 표 + 리스크 요인 */}
                {data.profit_simulation && data.profit_simulation.length > 0 && (
                  <div>
                    <SectionHeader title="분기별 재무 시뮬" />
                    <table className="w-full text-[0.625rem]">
                      <thead>
                        <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                          <th className="py-1.5 font-medium">분기</th>
                          <th className="py-1.5 font-medium text-right">매출</th>
                          <th className="py-1.5 font-medium text-right">비용</th>
                          <th className="py-1.5 font-medium text-right">영업이익</th>
                          <th className="py-1.5 font-medium text-right">마진</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.profit_simulation.map((p, i) => {
                          const margin = p.revenue > 0 ? (p.operating_profit / p.revenue) * 100 : 0;
                          return (
                            <tr key={i} className="border-b border-slate-200">
                              <td className="py-1.5 font-medium text-slate-900">Q{p.quarter}</td>
                              <td className="py-1.5 font-mono text-slate-900 text-right">
                                ₩{(p.revenue / 1_000_000).toFixed(1)}M
                              </td>
                              <td className="py-1.5 font-mono text-slate-700 text-right">
                                ₩{(p.cost / 1_000_000).toFixed(1)}M
                              </td>
                              <td className="py-1.5 font-mono font-bold text-right text-black">
                                {p.operating_profit < 0 ? '−' : ''}
                                {formatMillionWon(Math.abs(p.operating_profit))}
                              </td>
                              <td className="py-1.5 font-mono text-slate-600 text-right">
                                {margin.toFixed(1)}%
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="mt-auto text-[0.5625rem] text-slate-500 leading-relaxed border-t border-slate-200 pt-2">
                  <span className="font-bold">리스크 요인:</span> 임대료 상승 (변동 ±15%) · 원재료
                  공급가 (±10%) · 인건비 상승 (±5%) — 비관 시나리오에 반영. 실제 운영 시 월 단위 KPI
                  모니터링 권장.
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {/* Page 6: SHAP Top 5 — 화면 ShapInsightCard 와 동일하게 abs_shap 합 대비 상대 비율 % 표시.
          backend shap_value 의 절대 단위 (정규화/원 등) 모호 → 화면이 % 로 통일했고 PDF 도 동일.
          (2026-05-10) 사용자 보고: PDF SHAP 값 "이상함" → 원 단위 표시 + winner 동 미적용 회귀 수정. */}
      {showShap &&
        (() => {
          const n = ++pageNum;
          // 화면 동일 패턴 — Top 5 의 abs_shap 합 대비 % 비율 (절대 단위 무관).
          const shapTotalAbs = data.shap_top.reduce(
            (acc, s) => acc + Math.abs(s.abs_shap ?? s.shap_value),
            0,
          );
          const pctOf = (s: ShapFeatureItem) =>
            shapTotalAbs > 0 ? (Math.abs(s.abs_shap ?? s.shap_value) / shapTotalAbs) * 100 : 0;
          return (
            <div key={`shap-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    05. SHAP 기여도 분석
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    SHAP Feature Importance · 매출 예측 Top 5 기여 요인 + 영향 금액 + actionable
                    insight
                  </p>
                </div>

                {/* Top 5 막대 차트 — 화면 동일 % 비율 표시 */}
                <div>
                  <SectionHeader
                    title="Top 5 기여 요인"
                    subtitle="↑ = 매출 상승 기여 / ↓ = 매출 하락 기여 · 비율은 Top 5 합 대비 상대 영향도"
                  />
                  <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                    {data.shap_top.slice(0, 5).map((s, i) => {
                      const positive = s.shap_value >= 0;
                      const pct = pctOf(s);
                      return (
                        <SignedBarRow
                          key={i}
                          label={`${i + 1}. ${s.feature_ko ?? featureKo(s.feature)}`}
                          signedText={`${positive ? '↑' : '↓'} ${pct.toFixed(0)}%`}
                          ratio={pct / 100}
                          positive={positive}
                        />
                      );
                    })}
                  </div>
                </div>

                {/* 6~10 순위 요약 + 자연어 summary */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <SectionHeader title="6~10 순위 요약" subtitle="보조 영향 요인" />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      {data.shap_secondary.length === 0 ? (
                        <p className="text-[0.625rem] text-slate-500">데이터 없음</p>
                      ) : (
                        <div className="space-y-1">
                          {data.shap_secondary.map((s, i) => (
                            <div
                              key={i}
                              className="flex items-center justify-between text-[0.625rem]"
                            >
                              <span className="text-slate-700">
                                {i + 6}. {s.feature_ko ?? featureKo(s.feature)}
                              </span>
                              <span className="font-mono font-bold text-black">
                                {s.shap_value >= 0 ? '↑' : '↓'}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div>
                    <SectionHeader title="자연어 요약" subtitle="ML 모델 해석" />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3 h-full">
                      {data.shap_summary && data.shap_summary.length > 0 ? (
                        <ul className="space-y-1 text-[0.625rem] text-slate-700 leading-relaxed">
                          {data.shap_summary.slice(0, 4).map((s, i) => (
                            <li key={i}>· {s}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-[0.625rem] text-slate-500">
                          ↑는 매출 상승, ↓는 하락 영향. 비율은 Top 5 요인의 상대적 영향도입니다.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}
    </>
  );
}

/* ═══════════════════════════════════════════════════════
   AI PDF — 7 페이지
   ═══════════════════════════════════════════════════════ */
function AiPages({
  data,
  districtFull,
  reportDate,
  docId,
}: {
  data: AiPdfData;
  districtFull: string;
  reportDate: string;
  docId: string;
}) {
  const showVerdict = !!data.ai_verdict_summary || !!data.market_entry_signal;
  const showRanking = data.district_rankings.length > 0;
  const showLegal = data.legal_risks.length > 0;
  const showTrend = !!data.trend_forecast || !!data.competitor_intel;
  const showDemo = !!data.demographic_report;
  const showAttr = data.agent_attributions.length > 0;
  const totalPages =
    1 + // cover
    1 + // exec summary
    (showVerdict ? 1 : 0) +
    (showRanking ? 1 : 0) +
    (showLegal ? 1 : 0) +
    (showTrend ? 1 : 0) +
    (showDemo ? 1 : 0) +
    (showAttr ? 1 : 0);

  let pageNum = 1;
  const headerProps = (n: number) => ({
    pageNumber: n,
    totalPages,
    districtFull,
    modeLabel: 'AI 분석 리포트',
  });

  // Executive Summary 콘텐츠 — AI 핵심 KPI 6 + verdict + bullets.
  const signalKo: Record<string, string> = { green: '진입 양호', yellow: '주의', red: '포화' };
  const legalKo: Record<string, string> = { safe: '안전', caution: '주의', danger: '위험' };
  const top3Names = data.top_3_candidates
    .slice(0, 3)
    .map((c) => c.district)
    .filter(Boolean);
  const trendScore = data.trend_forecast?.score;
  const cannPct = data.competitor_intel?.cannibalization_pct;
  const aiExecKpis = [
    {
      label: '1등 추천 동',
      value: data.winner_district || '—',
      sub: top3Names.length > 1 ? `Top3 · ${top3Names.slice(1).join(' / ')}` : '단일 후보',
    },
    {
      label: '진입 신호',
      value: data.market_entry_signal ? signalKo[data.market_entry_signal] || '—' : '—',
      sub: '경쟁/포화 종합',
    },
    {
      label: '법률 리스크',
      value: data.overall_legal_risk ? legalKo[data.overall_legal_risk] || '—' : '—',
      sub: `상세 ${data.legal_risks.length}건`,
    },
    {
      label: '트렌드 점수',
      value: trendScore != null ? trendScore.toFixed(1) : '—',
      sub: data.trend_forecast?.direction ?? '—',
    },
    {
      label: '경쟁 점포 수',
      value:
        data.competitor_intel?.competition_count != null
          ? `${data.competitor_intel.competition_count}개`
          : '—',
      sub: data.competitor_intel?.saturation_level ?? '—',
    },
    {
      label: '카니발리제이션',
      value: cannPct != null ? `${cannPct.toFixed(1)}%` : '—',
      sub: '자기잠식 추정',
    },
  ];
  const aiVerdict = data.ai_verdict_summary
    ? data.ai_verdict_summary.length > 110
      ? data.ai_verdict_summary.slice(0, 110) + '…'
      : data.ai_verdict_summary
    : `${data.winner_district || districtFull} 진입 신호 ${data.market_entry_signal ? signalKo[data.market_entry_signal] : '미평가'} · 법률 리스크 ${data.overall_legal_risk ? legalKo[data.overall_legal_risk] : '—'}.`;
  const aiBullets: { title: string; body: string }[] = [];
  if (data.top_3_candidates.length > 0) {
    const c = data.top_3_candidates[0];
    aiBullets.push({
      title: `Top1 · ${c.district}`,
      body: c.summary || '핵심 차별 요인 분석 진행',
    });
  }
  if (data.legal_risks.length > 0) {
    const r = data.legal_risks[0];
    aiBullets.push({
      title: `법률 1순위 · ${r.type}`,
      body: r.detail || r.recommendation || '상세 검토 필요',
    });
  }
  if (
    data.competitor_intel?.recommended_actions &&
    data.competitor_intel.recommended_actions.length > 0
  ) {
    aiBullets.push({
      title: '권장 액션',
      body: data.competitor_intel.recommended_actions.slice(0, 2).join(' / '),
    });
  }
  if (data.demographic_report?.narrative) {
    aiBullets.push({
      title: '인구 특성',
      body: data.demographic_report.narrative.slice(0, 90),
    });
  }
  if (aiBullets.length === 0) {
    aiBullets.push({
      title: 'LangGraph 에이전트 분석 진행',
      body: '상세 페이지에서 동별 랭킹/법률/트렌드/인구/근거 확인.',
    });
  }

  // 신호/위험 등급 — 검정 톤 무채색. 강조는 보더 굵기와 배경 명도 차로.
  const signalColor = (s: string | null | undefined) =>
    s === 'green'
      ? { color: '#000000', bg: 'bg-white border-slate-300', text: '진입 양호' }
      : s === 'yellow'
        ? { color: '#1f2937', bg: 'bg-slate-50 border-slate-500', text: '주의' }
        : s === 'red'
          ? { color: '#000000', bg: 'bg-slate-100 border-black', text: '경쟁 포화' }
          : { color: '#6b7280', bg: 'bg-slate-50 border-slate-200', text: '데이터 없음' };

  return (
    <>
      <CoverPage
        districtFull={districtFull}
        reportDate={reportDate}
        docId={docId}
        subtitle="AI 분석 결과"
        badge="SPOTTER ANALYZE · LANGGRAPH AGENT REPORT"
      />

      {(() => {
        const n = ++pageNum;
        return (
          <ExecutiveSummaryPage
            key={`exec-ai-${n}`}
            pageNumber={n}
            totalPages={totalPages}
            districtFull={districtFull}
            reportDate={reportDate}
            modeLabel="AI 분석 리포트"
            kpis={aiExecKpis}
            verdict={aiVerdict}
            bullets={aiBullets.slice(0, 4)}
          />
        );
      })()}

      {showVerdict &&
        (() => {
          const n = ++pageNum;
          return (
            <div key={`v-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    01. AI 종합 판단
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    AI Verdict · {data.analysis_meta.agent_count}개 에이전트 합의 ·{' '}
                    {data.analysis_meta.generated_at}
                  </p>
                </div>

                {/* Winner + verdict 큰 박스 */}
                <div className="rounded-md border-2 border-black bg-slate-100 p-3">
                  <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                    WINNER DISTRICT
                  </div>
                  <div className="text-[1.5rem] font-black text-black leading-none mb-1.5">
                    {data.winner_district ?? '—'}
                  </div>
                  {data.ai_verdict_summary && (
                    <p className="text-[0.6875rem] text-slate-800 leading-relaxed">
                      {data.ai_verdict_summary}
                    </p>
                  )}
                </div>

                {/* 3대 신호 박스 (시장진입/법률/차별화) — 사용자 요청으로 제거 (2026-05-10) */}

                {/* TOP 3 후보 동 카드 */}
                {data.top_3_candidates.length > 0 && (
                  <div>
                    <SectionHeader title="TOP 3 후보 동" subtitle="winner + top 후보 score 요약" />
                    <div className="grid grid-cols-3 gap-2">
                      {data.top_3_candidates.map((c, i) => {
                        // 보더 굵기로 메달 차등 — 1위 가장 두껍게, 색은 검정 톤 통일
                        const borderClass =
                          i === 0
                            ? 'border-2 border-black'
                            : i === 1
                              ? 'border-2 border-slate-700'
                              : 'border border-slate-400';
                        return (
                          <div key={i} className={`rounded-md ${borderClass} bg-white p-3`}>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[0.5625rem] font-bold uppercase tracking-wider text-black">
                                #{i + 1}
                              </span>
                              <span className="text-[0.625rem] font-mono font-bold text-black">
                                {c.score}
                              </span>
                            </div>
                            <div className="text-[0.875rem] font-black text-slate-900 mb-1">
                              {c.district}
                            </div>
                            <p className="text-[0.5625rem] text-slate-600 leading-relaxed">
                              {c.summary}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 분석 메타 데이터 */}
                <div className="mt-auto rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                    분석 메타데이터
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[0.5625rem] text-slate-700">
                    <div>
                      <span className="font-bold">분석 일시:</span>{' '}
                      {data.analysis_meta.generated_at}
                    </div>
                    <div>
                      <span className="font-bold">에이전트 수:</span>{' '}
                      {data.analysis_meta.agent_count}개 (LangGraph)
                    </div>
                    <div>
                      <span className="font-bold">데이터 출처:</span>{' '}
                      {data.analysis_meta.data_sources.length}개
                    </div>
                  </div>
                  <div className="mt-1.5 text-[0.5625rem] text-slate-500 leading-relaxed">
                    {data.analysis_meta.data_sources.join(' / ')}
                  </div>
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {showRanking &&
        (() => {
          const n = ++pageNum;
          // Score 분포 (numeric parse)
          const scores = data.district_rankings
            .map((r) => parseFloat(r.score))
            .filter((s) => Number.isFinite(s));
          const maxScore = Math.max(0.01, ...scores);
          return (
            <div key={`r-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    02. Top 4 동 랭킹
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    District Ranking · 후보 Top 4 동 점수 / 폐업률 / BEP / 차별화 / 코멘트
                  </p>
                </div>

                {/* Score 분포 막대 — 막대는 데이터 시각으로 색상 유지 (Top 3 강조) */}
                <div>
                  <SectionHeader title="Score 분포" subtitle="동별 종합 점수 (Top 1~3 강조)" />
                  <div className="border border-slate-200 bg-slate-50 rounded-md p-3 space-y-1">
                    {data.district_rankings.slice(0, 4).map((r, i) => {
                      const v = parseFloat(r.score);
                      const ratio = Number.isFinite(v) ? v / maxScore : 0;
                      const color = i < 3 ? ['#d4af37', '#9ca3af', '#cd7f32'][i] : '#cbd5e1';
                      return (
                        <HorizontalBarRow
                          key={i}
                          label={`${r.rank}. ${r.district}`}
                          valueText={r.score}
                          ratio={ratio}
                          color={color}
                          labelWidth="w-28"
                        />
                      );
                    })}
                  </div>
                </div>

                {/* 표 — 화면 DistrictRankings 동일 5 컬럼 (순위/행정동/점수/매출성장/용도지역).
                    backend 미제공 BEP/차별화/코멘트 컬럼 제거 (2026-05-10 빈셀 회귀 차단). */}
                <div>
                  <SectionHeader title="상세 표" />
                  <table className="w-full text-[0.6rem] table-fixed">
                    <colgroup>
                      <col className="w-[40px]" />
                      <col className="w-[120px]" />
                      <col className="w-[80px]" />
                      <col className="w-[100px]" />
                      <col />
                    </colgroup>
                    <thead>
                      <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                        <th className="py-1.5 font-medium">순위</th>
                        <th className="py-1.5 font-medium">행정동</th>
                        <th className="py-1.5 font-medium text-right">점수</th>
                        <th className="py-1.5 font-medium text-right">매출성장</th>
                        <th className="py-1.5 font-medium text-center">용도지역</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.district_rankings.slice(0, 4).map((r, i) => {
                        const rowBg = i === 0 ? 'bg-slate-100' : i === 1 ? 'bg-slate-50' : '';
                        const zoningKo =
                          r.zoning_risk === 'safe'
                            ? '안전'
                            : r.zoning_risk === 'caution'
                              ? '주의'
                              : r.zoning_risk === 'danger'
                                ? '위험'
                                : '—';
                        return (
                          <tr key={i} className={`border-b border-slate-200 ${rowBg}`}>
                            <td className="py-1.5 font-mono font-bold text-black">{r.rank}</td>
                            <td
                              className="py-1.5 font-medium text-slate-900 truncate"
                              title={r.district}
                            >
                              {r.district}
                            </td>
                            <td className="py-1.5 font-mono text-slate-900 text-right">
                              {r.score}
                            </td>
                            <td className="py-1.5 font-mono text-slate-700 text-right">
                              {r.sales_growth}
                            </td>
                            <td className="py-1.5 text-center font-bold text-slate-900">
                              ● {zoningKo}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="mt-auto text-[0.5625rem] text-slate-500 leading-relaxed border-t border-slate-200 pt-2">
                  <span className="font-bold">랭킹 산출:</span> ML 매출 예측 (50%) + 폐업률 (20%) +
                  법률 위험도 (15%) + 경쟁/공실 (15%) 가중 평균. 후보 Top 4 동을 표시합니다.
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {showLegal &&
        (() => {
          const n = ++pageNum;
          // 위험도/조항 컬럼 + HIGH 박스 + 영업구역 카드 제거 (사용자 요청 2026-05-10).
          // 분야/상세/권고만 남김.
          return (
            <div key={`l-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-2.5">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    03. 법률 14 specialist
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Legal Risk · 가맹사업법 / 식품위생법 / 임대차보호법 외 14개 영역
                  </p>
                </div>

                {/* 14 specialist 표 — 분야/상세/권고만 (3 columns) */}
                <div>
                  <SectionHeader title="14 specialist 카테고리별 분석" />
                  <table className="w-full text-[0.5625rem] table-fixed">
                    <colgroup>
                      <col className="w-[110px]" />
                      <col />
                      <col className="w-[260px]" />
                    </colgroup>
                    <thead>
                      <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                        <th className="py-1 font-medium">분야</th>
                        <th className="py-1 font-medium">상세</th>
                        <th className="py-1 font-medium">권고</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.legal_risks.slice(0, 14).map((risk, i) => (
                        <tr key={i} className="border-b border-slate-200 align-top">
                          <td
                            className="py-1.5 font-medium text-slate-900 leading-tight pr-1 break-words"
                            title={risk.type}
                          >
                            {risk.type}
                          </td>
                          <td
                            className="py-1.5 text-slate-700 leading-tight pr-1 break-words"
                            title={risk.detail}
                          >
                            {risk.detail}
                          </td>
                          <td
                            className="py-1.5 text-slate-600 leading-tight pr-1 break-words"
                            title={risk.recommendation ?? ''}
                          >
                            {risk.recommendation ?? '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-auto text-[0.5625rem] text-slate-500 leading-relaxed border-t border-slate-200 pt-2">
                  <span className="font-bold">법률 자문 footnote:</span> 본 분석은 LLM 기반 자동
                  생성으로 법률 자문을 대체하지 않습니다. 변호사·전문가 검토를 권장합니다.
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {showTrend &&
        (() => {
          const n = ++pageNum;
          const ci = data.competitor_intel;
          const sig = signalColor(ci?.market_entry_signal ?? null);
          const tf = data.trend_forecast;
          return (
            <div key={`t-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    04. 트렌드 + 경쟁
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Trend Forecast & Competitor Intel · 산업 방향성 + 500m 반경 경쟁
                  </p>
                </div>

                {/* trend_forecast 핵심 지표 4 카드 */}
                <div className="grid grid-cols-4 gap-2">
                  <MiniInfoCard
                    label="트렌드 점수"
                    value={tf?.score != null ? `${Math.round(tf.score)}` : '—'}
                    hint={tf?.direction ? `방향: ${tf.direction}` : undefined}
                    accent="#000000"
                  />
                  <MiniInfoCard
                    label="YoY 변화율"
                    value={
                      tf?.yoy_change_pct != null
                        ? `${tf.yoy_change_pct >= 0 ? '+' : ''}${tf.yoy_change_pct.toFixed(1)}%`
                        : '—'
                    }
                    accent="#000000"
                  />
                  <MiniInfoCard
                    label="산업"
                    value={tf?.industry ?? '—'}
                    hint={tf?.horizon_months ? `예측 ${tf.horizon_months}개월` : undefined}
                  />
                  <MiniInfoCard
                    label="진입 신호"
                    value={(ci?.market_entry_signal ?? '—').toString().toUpperCase()}
                    hint={sig.text}
                    accent={sig.color}
                  />
                </div>

                {/* 트렌드 narrative + 12개월 라인 */}
                {(tf?.narrative || (tf?.samples ?? []).length > 0) && (
                  <div>
                    <SectionHeader title="트렌드 전망" subtitle="산업 12개월 추이" />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      {tf?.samples && tf.samples.length > 0 && (
                        <LineChart
                          values={tf.samples}
                          width={620}
                          height={70}
                          color="#002cd1"
                          fill="rgba(0,44,209,0.10)"
                        />
                      )}
                      {tf?.narrative && (
                        <p className="text-[0.625rem] text-slate-700 leading-relaxed mt-2">
                          {tf.narrative}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* 경쟁 KPI 3개 */}
                {ci && (
                  <div className="grid grid-cols-3 gap-2">
                    <KpiCard
                      title="500m 경쟁업체"
                      value={ci.competition_count != null ? `${ci.competition_count}곳` : '—'}
                    />
                    <KpiCard title="포화도" value={ci.saturation_level ?? '—'} />
                    <KpiCard
                      title="자기잠식"
                      value={
                        ci.cannibalization_pct != null
                          ? `${ci.cannibalization_pct.toFixed(1)}%`
                          : '—'
                      }
                      accent="#000000"
                    />
                  </div>
                )}

                {/* 경쟁업체 Top 5 표 */}
                {ci && ci.top_competitors.length > 0 && (
                  <div>
                    <SectionHeader title="반경 500m 경쟁업체 Top 5" />
                    <table className="w-full text-[0.625rem]">
                      <thead>
                        <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                          <th className="py-1.5 font-medium">상호</th>
                          <th className="py-1.5 font-medium">브랜드</th>
                          <th className="py-1.5 font-medium">카테고리</th>
                          <th className="py-1.5 font-medium text-right">거리</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ci.top_competitors.slice(0, 5).map((c, i) => (
                          <tr key={i} className="border-b border-slate-200">
                            <td className="py-1.5 text-slate-900">{c.place_name}</td>
                            <td className="py-1.5 text-slate-600">{c.brand_name ?? '—'}</td>
                            <td className="py-1.5 text-slate-500">{c.category ?? '—'}</td>
                            <td className="py-1.5 font-mono text-slate-700 text-right">
                              {c.distance_text}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* cannibalization + 차별화 + 추천 액션 */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-md border border-slate-500 bg-slate-50 p-3">
                    <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                      자기잠식 (Cannibalization)
                    </div>
                    <p className="text-[0.625rem] text-slate-700 leading-relaxed">
                      {ci?.cannibalization_pct != null
                        ? `예상 매출 영향: ${ci.cannibalization_pct.toFixed(2)}%. 동일 브랜드 인근 매장이 신규 매장 진입으로 인해 받을 영향.`
                        : '데이터 없음 — 동일 브랜드 매장 거리/밀도 정보 부족.'}
                    </p>
                    {ci?.differentiation_position && (
                      <div className="text-[0.5625rem] text-black mt-1.5 font-bold">
                        차별화 포지션: {ci.differentiation_position}
                      </div>
                    )}
                  </div>
                  <div className="rounded-md border-2 border-black bg-white p-3">
                    <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                      시장 진입 추천
                    </div>
                    {ci && ci.recommended_actions.length > 0 ? (
                      <ul className="space-y-0.5 text-[0.5625rem] text-slate-700 leading-relaxed">
                        {ci.recommended_actions.slice(0, 3).map((a, i) => (
                          <li key={i}>· {a}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-[0.5625rem] text-slate-700 leading-relaxed">
                        · 차별화 콘셉트 정립
                        <br />· 핵심 시간대 광고 집중
                        <br />· 경쟁 매장 모니터링 정기화
                      </p>
                    )}
                  </div>
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {showDemo &&
        (() => {
          const n = ++pageNum;
          const d = data.demographic_report!;
          // 성별 도넛 — core_gender 기반 추정 (60/40 또는 데이터 있으면 그 값)
          const isFemaleCore = d.core_gender?.includes('여');
          const femaleShare = isFemaleCore ? 0.62 : 0.38;
          const maleShare = 1 - femaleShare;
          const incomeLabel =
            d.area_income_level === 'high'
              ? '상위'
              : d.area_income_level === 'mid'
                ? '중위'
                : d.area_income_level === 'low'
                  ? '하위'
                  : '—';
          const popTrendLabel =
            d.population_trend === 'growing'
              ? '증가'
              : d.population_trend === 'declining'
                ? '감소'
                : d.population_trend === 'stable'
                  ? '안정'
                  : '—';
          return (
            <div key={`d-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">05. 인구 심화</h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Demographic Depth · 핵심 인구층 + 연령/성별 + 거주/방문 + 소득 + 매칭
                  </p>
                </div>

                {/* KPI 4종 */}
                <div className="grid grid-cols-4 gap-2">
                  <MiniInfoCard
                    label="핵심 고객층"
                    value={d.core_age && d.core_gender ? `${d.core_age} ${d.core_gender}` : '—'}
                    accent="#000000"
                  />
                  <MiniInfoCard
                    label="브랜드 매칭"
                    value={d.brand_match_score != null ? `${d.brand_match_score}/100` : '—'}
                    accent="#000000"
                  />
                  <MiniInfoCard label="소득 수준" value={incomeLabel} />
                  <MiniInfoCard label="인구 트렌드" value={popTrendLabel} accent="#000000" />
                </div>

                {/* 연령대 분포 막대 + 성별 도넛 */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <SectionHeader title="연령대 분포 Top 3" />
                    <div className="border border-slate-200 bg-white rounded-md p-3 space-y-1">
                      {d.top_age_groups.length > 0 ? (
                        d.top_age_groups.map((a, i) => (
                          <HorizontalBarRow
                            key={i}
                            label={a.age_group}
                            valueText={`${(a.share * 100).toFixed(1)}%`}
                            ratio={a.share}
                          />
                        ))
                      ) : (
                        <p className="text-[0.625rem] text-slate-500">데이터 없음</p>
                      )}
                    </div>
                  </div>
                  <div>
                    <SectionHeader title="성별 분포" subtitle="추정 비율" />
                    <div className="border border-slate-200 bg-white rounded-md p-3 flex items-center gap-3">
                      <DonutChart
                        size={80}
                        thickness={14}
                        segments={[
                          { label: '여성', value: femaleShare, color: '#e11d48' },
                          { label: '남성', value: maleShare, color: '#002cd1' },
                        ]}
                      />
                      <div className="text-[0.625rem] text-slate-700 space-y-1">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-sm bg-rose-600 inline-block" />
                          여성 {(femaleShare * 100).toFixed(0)}%
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-sm bg-[#002cd1] inline-block" />
                          남성 {(maleShare * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 주거/유동/평일/주말/고령자 표 */}
                <div>
                  <SectionHeader title="인구 구조 지표" />
                  <table className="w-full text-[0.625rem]">
                    <tbody>
                      <tr className="border-b border-slate-200">
                        <td className="py-1.5 font-medium text-slate-700 w-1/3">거주/방문 비율</td>
                        <td className="py-1.5 font-mono text-slate-900">
                          {d.resident_visitor_ratio != null
                            ? `${(d.resident_visitor_ratio * 100).toFixed(1)}% 거주`
                            : '—'}
                        </td>
                      </tr>
                      <tr className="border-b border-slate-200">
                        <td className="py-1.5 font-medium text-slate-700">평일/주말 비율</td>
                        <td className="py-1.5 font-mono text-slate-900">
                          {d.weekday_weekend_ratio != null
                            ? `${d.weekday_weekend_ratio.toFixed(2)}x`
                            : '—'}
                        </td>
                      </tr>
                      <tr className="border-b border-slate-200">
                        <td className="py-1.5 font-medium text-slate-700">고령자 비율</td>
                        <td className="py-1.5 font-mono text-slate-900">
                          {d.elderly_ratio != null ? `${(d.elderly_ratio * 100).toFixed(1)}%` : '—'}
                        </td>
                      </tr>
                      <tr className="border-b border-slate-200">
                        <td className="py-1.5 font-medium text-slate-700">피크 소비 시간</td>
                        <td className="py-1.5 font-mono text-slate-900">
                          {d.peak_consumption_hours.length > 0
                            ? d.peak_consumption_hours.join(' · ')
                            : '—'}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* narrative + 매칭 점수 카드 */}
                <div className="grid grid-cols-3 gap-2 mt-auto">
                  <div className="col-span-2 rounded-md border border-slate-200 bg-slate-50 p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      인구 분석 코멘트
                    </div>
                    <p className="text-[0.625rem] text-slate-700 leading-relaxed">
                      {d.narrative ?? '데이터 없음'}
                    </p>
                  </div>
                  <div className="rounded-md border-2 border-black bg-white p-3 flex flex-col justify-center items-center">
                    <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                      타겟 매칭
                    </div>
                    <div className="text-[1.5rem] font-black text-black leading-none">
                      {d.brand_match_score != null ? d.brand_match_score : '—'}
                    </div>
                    <div className="text-[0.5625rem] text-slate-700 mt-1">/ 100</div>
                  </div>
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {showAttr &&
        (() => {
          const n = ++pageNum;
          // agent 일치/불일치 분석 — verdict 키워드로 simple grouping
          const verdicts = data.agent_attributions.map((a) => a.verdict.toLowerCase());
          const positiveCount = verdicts.filter(
            (v) => v.includes('양호') || v.includes('green') || v.includes('진입'),
          ).length;
          const cautionCount = verdicts.filter(
            (v) => v.includes('주의') || v.includes('caution') || v.includes('경계'),
          ).length;
          const negativeCount = verdicts.filter(
            (v) => v.includes('위험') || v.includes('red') || v.includes('보류'),
          ).length;
          const consensus =
            positiveCount > cautionCount + negativeCount
              ? {
                  text: '에이전트 합의: 진입 양호',
                  color: '#000000',
                  bg: 'bg-white border-slate-300',
                }
              : negativeCount > positiveCount + cautionCount
                ? {
                    text: '에이전트 합의: 진입 위험',
                    color: '#000000',
                    bg: 'bg-slate-100 border-black',
                  }
                : {
                    text: '에이전트 의견 분산: 검토 필요',
                    color: '#1f2937',
                    bg: 'bg-slate-50 border-slate-500',
                  };
          return (
            <div key={`a-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-2.5">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    06. 에이전트 판단 근거
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Agent Attributions · {data.agent_attributions.length}개 LangGraph 노드 · 판단 +
                    근거 + 핵심 발견
                  </p>
                </div>

                {/* 합의/불일치 분석 */}
                <div className={`rounded-md border-2 ${consensus.bg} p-3`}>
                  <div className="flex items-center justify-between">
                    <div className="text-[0.75rem] font-black" style={{ color: consensus.color }}>
                      {consensus.text}
                    </div>
                    <div className="flex items-center gap-2 text-[0.5625rem] font-mono text-slate-700">
                      <span>긍정 {positiveCount}</span>
                      <span className="text-slate-500">·</span>
                      <span>주의 {cautionCount}</span>
                      <span className="text-slate-500">·</span>
                      <span>위험 {negativeCount}</span>
                    </div>
                  </div>
                </div>

                {/* agent 7개 카드 표 */}
                <div>
                  <SectionHeader
                    title="에이전트별 판단"
                    subtitle="이름 / 종류 / 판단 / 핵심 발견 / 근거"
                  />
                  <div className="space-y-1.5">
                    {data.agent_attributions.slice(0, 7).map((a, i) => {
                      const v = a.verdict.toLowerCase();
                      // 검정 톤 — verdict 강조는 굵기/배지 배경 명도차로
                      const tone =
                        v.includes('양호') || v.includes('진입')
                          ? { color: '#000000', dot: '#000000' }
                          : v.includes('위험') || v.includes('보류')
                            ? { color: '#000000', dot: '#000000' }
                            : v.includes('주의')
                              ? { color: '#1f2937', dot: '#1f2937' }
                              : { color: '#6b7280', dot: '#6b7280' };
                      return (
                        <div
                          key={i}
                          className="rounded-md border border-slate-200 bg-slate-50 p-2.5"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <span
                                className="w-2 h-2 rounded-full inline-block"
                                style={{ background: tone.dot }}
                              />
                              <h3 className="text-[0.6875rem] font-bold text-slate-900">
                                {a.display_name}
                              </h3>
                              <span className="text-[0.5rem] font-mono uppercase tracking-wider text-slate-500 px-1.5 py-0.5 border border-slate-300 rounded">
                                {a.kind}
                              </span>
                              {a.confidence && (
                                <span
                                  className="text-[0.5rem] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded text-white"
                                  style={{ background: tone.color }}
                                >
                                  {a.confidence}
                                </span>
                              )}
                            </div>
                            <span
                              className="text-[0.625rem] font-bold"
                              style={{ color: tone.color }}
                            >
                              {a.verdict}
                            </span>
                          </div>
                          {a.key_finding && (
                            <p className="text-[0.5625rem] text-slate-800 mb-0.5 font-medium leading-snug">
                              <span className="font-bold text-slate-500">핵심:</span>{' '}
                              {a.key_finding}
                            </p>
                          )}
                          <p className="text-[0.5625rem] text-slate-600 leading-snug">
                            {a.reasoning}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* synthesis 종합 박스 */}
                <div className="rounded-md border-2 border-black bg-white p-3 mt-auto">
                  <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                    Synthesis 종합
                  </div>
                  <p className="text-[0.625rem] text-slate-700 leading-relaxed">
                    {data.ai_verdict_summary ??
                      `${data.agent_attributions.length}개 에이전트가 각자 판단을 도출하고, synthesis 노드가 종합하여 winner_district 와 시장 진입 신호를 결정합니다. 본 페이지의 에이전트 별 판단을 종합한 최종 verdict 는 Page 1 에서 확인하세요.`}
                  </p>
                </div>

                <div className="text-[0.5rem] text-slate-500 leading-relaxed border-t border-slate-200 pt-1.5">
                  <span className="font-bold">신뢰도 footnote:</span> 에이전트 판단은 LLM 추론
                  결과로 100% 정확성을 보장하지 않습니다. 중요한 출점 결정 시 본 리포트를 참고
                  자료로 활용하고 추가 현장 실사를 병행하세요.
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}
    </>
  );
}

/* ═══════════════════════════════════════════════════════
   ABM PDF — 5 페이지
   ═══════════════════════════════════════════════════════ */
function AbmPages({
  data,
  districtFull,
  reportDate,
  docId,
}: {
  data: AbmPdfData;
  districtFull: string;
  reportDate: string;
  docId: string;
}) {
  const showKpi = data.kpis.length > 0;
  const showCann = !!data.cannibalization;
  const showDong = data.dong_totals.length > 0;
  const showScenario = !!data.scenario;
  const totalPages =
    1 + // cover
    1 + // exec summary
    (showKpi ? 1 : 0) +
    (showCann ? 1 : 0) +
    (showDong ? 1 : 0) +
    (showScenario ? 1 : 0);

  let pageNum = 1;
  const headerProps = (n: number) => ({
    pageNumber: n,
    totalPages,
    districtFull,
    modeLabel: 'ABM 시뮬 결과',
  });

  // Executive Summary 콘텐츠 — ABM 핵심 KPI 6 + verdict + bullets.
  const meta = data.sim_meta;
  const peakHourTop =
    data.peak_hours && data.peak_hours.length > 0
      ? `${data.peak_hours
          .slice(0, 3)
          .map((h) => `${h}시`)
          .join(', ')}`
      : data.hourly_visits && data.hourly_visits.length === 24
        ? (() => {
            const idx = data.hourly_visits.indexOf(Math.max(...data.hourly_visits));
            return `${idx}시`;
          })()
        : '—';
  const topDong =
    data.dong_winner || (data.dong_totals.length > 0 ? data.dong_totals[0].dong : '—');
  const cannPct = data.cannibalization?.estimated_impact_pct;
  const abmExecKpis = [
    {
      label: '총 에이전트',
      value: meta.n_agents != null ? `${meta.n_agents.toLocaleString('ko-KR')}명` : '—',
      sub: meta.days != null ? `${meta.days}일 시뮬` : '—',
    },
    {
      label: '일평균 방문',
      value:
        meta.daily_visits != null
          ? `${Math.round(meta.daily_visits).toLocaleString('ko-KR')}명`
          : '—',
      sub: meta.daily_visits_std != null ? `±${Math.round(meta.daily_visits_std)}` : '—',
    },
    {
      label: '월매출 추정',
      value: formatCompactWon(meta.monthly_revenue_estimate),
      sub: 'ABM 기반',
    },
    {
      label: '피크 시간대',
      value: peakHourTop,
      sub: 'Top 시간 분포',
    },
    {
      label: 'Top 동',
      value: topDong,
      sub: data.dong_totals.length > 0 ? `${data.dong_totals.length}개 비교` : '—',
    },
    {
      label: '자기잠식 영향',
      value: cannPct != null ? `${cannPct.toFixed(1)}%` : '—',
      sub: data.cannibalization
        ? `1차 ${data.cannibalization.primary_zone_count} · 2차 ${data.cannibalization.secondary_zone_count}`
        : '—',
    },
  ];
  const abmVerdict = (() => {
    if (cannPct != null && cannPct >= 15) {
      return `${districtFull} 자기잠식 ${cannPct.toFixed(1)}% — 신규 출점 시 기존 매장 매출 잠식 우려.`;
    }
    if (data.scenario?.revenue_delta_pct != null && data.scenario.revenue_delta_pct < -10) {
      return `시나리오 매출 ${formatSignedPercent(data.scenario.revenue_delta_pct)} 변화 — 가정 재검토 필요.`;
    }
    return `${districtFull} ${meta.n_agents ?? '—'} 에이전트 시뮬 · 일평균 ${meta.daily_visits != null ? Math.round(meta.daily_visits).toLocaleString('ko-KR') : '—'}명 · Top 동 ${topDong}.`;
  })();
  const abmBullets: { title: string; body: string }[] = [];
  if (data.cannibalization && data.cannibalization.affected_stores.length > 0) {
    const top = data.cannibalization.affected_stores[0];
    abmBullets.push({
      title: '자기잠식 1순위',
      body: `${top.name} (${top.dong}, ${top.distance_text}) · ${top.impact_pct.toFixed(1)}% 영향`,
    });
  }
  if (data.dong_commentary.length > 0) {
    const c = data.dong_commentary[0];
    abmBullets.push({
      title: `${c.dong} 코멘트`,
      body: c.comment.slice(0, 90),
    });
  }
  if (data.scenario?.narrator_summary) {
    abmBullets.push({
      title: '시나리오 요약',
      body: data.scenario.narrator_summary.slice(0, 90),
    });
  }
  const tierTotal = (meta.tier_s ?? 0) + (meta.tier_a ?? 0) + (meta.tier_b ?? 0);
  if (tierTotal > 0) {
    abmBullets.push({
      title: 'Tier 분포',
      body: `S ${meta.tier_s ?? 0} · A ${meta.tier_a ?? 0} · B ${meta.tier_b ?? 0} (총 ${tierTotal})`,
    });
  }
  if (abmBullets.length === 0) {
    abmBullets.push({
      title: 'ABM 시뮬 완료',
      body: '상세 페이지에서 KPI/자기잠식/동별/시나리오 확인.',
    });
  }

  return (
    <>
      <CoverPage
        districtFull={districtFull}
        reportDate={reportDate}
        docId={docId}
        subtitle="ABM 시뮬 결과"
        badge="SPOTTER ABM · AGENT-BASED MODEL"
      />

      {(() => {
        const n = ++pageNum;
        return (
          <ExecutiveSummaryPage
            key={`exec-abm-${n}`}
            pageNumber={n}
            totalPages={totalPages}
            districtFull={districtFull}
            reportDate={reportDate}
            modeLabel="ABM 시뮬 결과"
            kpis={abmExecKpis}
            verdict={abmVerdict}
            bullets={abmBullets.slice(0, 4)}
          />
        );
      })()}

      {showKpi &&
        (() => {
          const n = ++pageNum;
          const meta = data.sim_meta;
          const tierTotal = (meta.tier_s ?? 0) + (meta.tier_a ?? 0) + (meta.tier_b ?? 0) || 1;
          return (
            <div key={`k-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">01. 시뮬 KPI</h2>
                  <p className="text-[0.625rem] text-slate-500">
                    ABM Simulation KPIs · 에이전트 Tier S/A/B + 시간대별 visits + role 분포
                  </p>
                </div>

                {/* KPI 6개 grid */}
                <div className="grid grid-cols-3 gap-2">
                  {data.kpis.map((k, i) => (
                    <KpiCard key={i} title={k.title} value={k.value} accent={k.accent} />
                  ))}
                </div>

                {/* 시뮬 메타 표 — Tier 분포 / std / 월매출 */}
                <div>
                  <SectionHeader
                    title="시뮬 상세 메타"
                    subtitle="Tier 분포 + 일평균 변동 + 월매출 추정"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <table className="w-full text-[0.625rem]">
                      <tbody>
                        <tr className="border-b border-slate-200">
                          <td className="py-1 font-medium text-slate-700">총 에이전트</td>
                          <td className="py-1 font-mono text-slate-900 text-right">
                            {meta.n_agents ?? '—'}
                          </td>
                        </tr>
                        <tr className="border-b border-slate-200">
                          <td className="py-1 font-medium text-slate-700">시뮬 일수</td>
                          <td className="py-1 font-mono text-slate-900 text-right">
                            {meta.days ?? '—'}일
                          </td>
                        </tr>
                        <tr className="border-b border-slate-200">
                          <td className="py-1 font-medium text-slate-700">일평균 방문 (std)</td>
                          <td className="py-1 font-mono text-slate-900 text-right">
                            {meta.daily_visits ?? '—'} (±{meta.daily_visits_std ?? '—'})
                          </td>
                        </tr>
                        <tr className="border-b border-slate-200">
                          <td className="py-1 font-medium text-slate-700">월매출 추정</td>
                          <td className="py-1 font-mono text-slate-900 text-right">
                            {meta.monthly_revenue_estimate != null
                              ? `₩${(meta.monthly_revenue_estimate / 1_000_000).toFixed(1)}M`
                              : '—'}
                          </td>
                        </tr>
                        <tr className="border-b border-slate-200">
                          <td className="py-1 font-medium text-slate-700">예상 비용</td>
                          <td className="py-1 font-mono text-slate-900 text-right">
                            {meta.estimated_cost_usd != null
                              ? `$${meta.estimated_cost_usd.toFixed(2)} / 시뮬`
                              : '—'}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    <div className="border border-slate-200 bg-white rounded-md p-2.5">
                      <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                        Tier 분포 (LLM Brain 비용 계층화)
                      </div>
                      <div className="space-y-1">
                        <HorizontalBarRow
                          label="Tier S (Opus)"
                          valueText={
                            meta.tier_s != null
                              ? `${meta.tier_s}명 (${((meta.tier_s / tierTotal) * 100).toFixed(0)}%)`
                              : '—'
                          }
                          ratio={(meta.tier_s ?? 0) / tierTotal}
                          color="#e11d48"
                          labelWidth="w-16"
                        />
                        <HorizontalBarRow
                          label="Tier A (Haiku)"
                          valueText={
                            meta.tier_a != null
                              ? `${meta.tier_a}명 (${((meta.tier_a / tierTotal) * 100).toFixed(0)}%)`
                              : '—'
                          }
                          ratio={(meta.tier_a ?? 0) / tierTotal}
                          color="#d97706"
                          labelWidth="w-16"
                        />
                        <HorizontalBarRow
                          label="Tier B (Flash)"
                          valueText={
                            meta.tier_b != null
                              ? `${meta.tier_b}명 (${((meta.tier_b / tierTotal) * 100).toFixed(0)}%)`
                              : '—'
                          }
                          ratio={(meta.tier_b ?? 0) / tierTotal}
                          color="#059669"
                          labelWidth="w-16"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* 24시간 visits 막대 */}
                {data.hourly_visits && data.hourly_visits.length > 0 && (
                  <div>
                    <SectionHeader
                      title="시간대별 방문 분포"
                      subtitle={
                        data.peak_hours && data.peak_hours.length > 0
                          ? `피크 ${data.peak_hours.map((h) => `${String(h).padStart(2, '0')}:00`).join(' / ')}`
                          : undefined
                      }
                    />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      <VerticalBarChart
                        bars={data.hourly_visits.map((v, i) => ({
                          label: String(i).padStart(2, '0'),
                          value: v,
                          valueText: '',
                          color: data.peak_hours?.includes(i) ? '#002cd1' : '#cbd5e1',
                        }))}
                        height={80}
                      />
                    </div>
                  </div>
                )}

                {/* role 분포 */}
                {meta.role_distribution.length > 0 && (
                  <div>
                    <SectionHeader
                      title="Role 분포"
                      subtitle="resident / commuter / visitor / owner / ext_*"
                    />
                    <div className="border border-slate-200 bg-white rounded-md p-3 space-y-1">
                      {meta.role_distribution.map((r, i) => {
                        const pct = (r.count / (meta.n_agents ?? 1)) * 100;
                        return (
                          <HorizontalBarRow
                            key={i}
                            label={r.role}
                            valueText={`${r.count}명 (${pct.toFixed(0)}%)`}
                            ratio={r.count / (meta.n_agents ?? 1)}
                            labelWidth="w-24"
                            color="#0891b2"
                          />
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="mt-auto text-[0.5625rem] text-slate-500 leading-relaxed border-t border-slate-200 pt-2">
                  <span className="font-bold">방법론:</span> Mapo 1000 ABM 에이전트 — Tier S/A/B
                  계층화로 LLM 비용 ~$0.7/일. 11회 base 생성 + time_block×5 하드코딩 확장 (55) +
                  Brain Tier별 LLM 호출.
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {showCann &&
        (() => {
          const n = ++pageNum;
          const c = data.cannibalization!;
          // Huff β=2 거리감쇠 데모 — 0~1500m 11 points
          const huffDecay: number[] = [];
          for (let d = 0; d <= 1500; d += 150) {
            const safeDist = Math.max(50, d);
            huffDecay.push(1 / Math.pow(safeDist / 100, 2));
          }
          const huffMax = Math.max(...huffDecay);
          return (
            <div key={`c-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    02. 시장 자기잠식
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Cannibalization · Huff Model β=2 거리감쇠 + 1차/2차 영향권 + 학술 근거
                  </p>
                </div>

                {/* 영향률 큰 카드 — backend ABM estimated_impact_pct 가 percent value (19.0). × 100 제거. */}
                <div className="rounded-md border-2 border-black bg-slate-100 p-3">
                  <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1">
                    예상 영향률
                  </div>
                  <div className="flex items-baseline gap-3">
                    <div className="text-[1.875rem] font-black leading-none text-black">
                      {c.estimated_impact_pct.toFixed(2)}%
                    </div>
                    <div className="text-[0.625rem] text-slate-600 leading-relaxed">
                      Huff Probability Model (β=2 거리감쇠) — 신규 매장 진입으로 동일 브랜드 인근
                      매장 매출 감소 추정.
                    </div>
                  </div>
                </div>

                {/* 1차/2차 영향권 비교 + 거리감쇠 그래프 */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-md border border-slate-200 bg-white p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-2">
                      영향권 매장 수
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded border border-black bg-slate-100 p-2 text-center">
                        <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-0.5">
                          1차 (≤500m)
                        </div>
                        <div className="text-[1.25rem] font-black text-black">
                          {c.primary_zone_count}
                        </div>
                      </div>
                      <div className="rounded border border-slate-500 bg-slate-50 p-2 text-center">
                        <div className="text-[0.5rem] font-bold text-slate-800 uppercase tracking-wider mb-0.5">
                          2차 (500~1km)
                        </div>
                        <div className="text-[1.25rem] font-black text-slate-800">
                          {c.secondary_zone_count}
                        </div>
                      </div>
                    </div>
                    <div className="text-[0.5625rem] text-slate-500 mt-1.5 leading-relaxed">
                      총 {c.affected_stores.length}개 매장 영향. 1차 영향권 매장이 매출 감소 대부분
                      흡수.
                    </div>
                  </div>
                  <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                      Huff β=2 거리감쇠
                    </div>
                    <svg width={300} height={70} viewBox="0 0 300 70">
                      <line x1="10" y1="60" x2="290" y2="60" stroke="#cbd5e1" strokeWidth={1} />
                      <polyline
                        points={huffDecay
                          .map((v, i) => {
                            const x = 10 + (i * 280) / (huffDecay.length - 1);
                            const y = 60 - (v / huffMax) * 50;
                            return `${x},${y}`;
                          })
                          .join(' ')}
                        fill="none"
                        stroke="#002cd1"
                        strokeWidth={2}
                      />
                      <text x="10" y="68" fontSize="7" fill="#64748b">
                        0m
                      </text>
                      <text x="280" y="68" fontSize="7" fill="#64748b">
                        1.5km
                      </text>
                    </svg>
                    <div className="text-[0.5625rem] text-slate-500 mt-1 leading-relaxed">
                      거리 ↑ → 영향도 1/d² 비율로 급감. 500m 이내 매장이 영향의 80%+ 차지.
                    </div>
                  </div>
                </div>

                {/* 영향 매장 표 (Top 10) */}
                {c.affected_stores.length > 0 && (
                  <div>
                    <SectionHeader title="영향 매장 Top 10" />
                    <table className="w-full text-[0.625rem] table-fixed">
                      <colgroup>
                        <col />
                        <col className="w-[72px]" />
                        <col className="w-[58px]" />
                        <col className="w-[64px]" />
                        <col className="w-[40px]" />
                      </colgroup>
                      <thead>
                        <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                          <th className="py-1.5 font-medium">매장</th>
                          <th className="py-1.5 font-medium">동</th>
                          <th className="py-1.5 font-medium text-right">거리</th>
                          <th className="py-1.5 font-medium text-right">영향도</th>
                          <th className="py-1.5 font-medium">권역</th>
                        </tr>
                      </thead>
                      <tbody>
                        {c.affected_stores.slice(0, 10).map((s, i) => {
                          const zone =
                            s.distance_m == null
                              ? '—'
                              : s.distance_m < 500
                                ? '1차'
                                : s.distance_m < 1000
                                  ? '2차'
                                  : '3차';
                          // 권역 - 검정 톤 명도차
                          const zoneColor =
                            zone === '1차' ? '#000000' : zone === '2차' ? '#374151' : '#94a3b8';
                          return (
                            <tr key={i} className="border-b border-slate-200 align-top">
                              <td
                                className="py-1.5 text-slate-900 pr-1 leading-tight"
                                title={s.name}
                                style={{
                                  display: '-webkit-box',
                                  WebkitLineClamp: 2,
                                  WebkitBoxOrient: 'vertical',
                                  overflow: 'hidden',
                                  wordBreak: 'keep-all',
                                }}
                              >
                                {s.name}
                              </td>
                              <td
                                className="py-1.5 text-slate-600 leading-tight"
                                title={s.dong}
                                style={{
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                }}
                              >
                                {s.dong}
                              </td>
                              <td className="py-1.5 font-mono text-slate-700 text-right">
                                {s.distance_text}
                              </td>
                              <td className="py-1.5 font-mono font-bold text-black text-right">
                                {(s.impact_pct * 100).toFixed(2)}%
                              </td>
                              <td
                                className="py-1.5 font-mono font-bold text-[0.5rem]"
                                style={{ color: zoneColor }}
                              >
                                {zone}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="mt-auto text-[0.5625rem] text-slate-500 leading-relaxed border-t border-slate-200 pt-2">
                  <span className="font-bold">학술 근거:</span> 서경원·고사랑 (2023) 동일 브랜드
                  카니발리제이션 평균 19% / Pancras (2012) Huff Probability Model 표준 β=2 적용.
                  500m 이내 매장 영향이 전체의 80%+ 차지.
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {showDong &&
        (() => {
          const n = ++pageNum;
          // 시간대 매트릭스 — backend 가 미제공이면 dong_totals 의 daily_visits 를 24시간 균등 분배 (placeholder)
          const heatMatrix =
            data.dong_hour_matrix ??
            data.dong_totals.slice(0, 4).map((d) => ({
              dong: d.dong,
              hours: Array.from({ length: 24 }, (_, h) =>
                Math.round((d.daily_visits / 24) * (1 + Math.cos(((h - 12) * Math.PI) / 12))),
              ),
            }));
          const heatMax = Math.max(1, ...heatMatrix.flatMap((row) => row.hours));
          return (
            <div key={`d-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">03. 동별 비교</h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Dong Comparison · 4개 후보 동 visits/revenue + 시간대 매트릭스 + 코멘트
                  </p>
                </div>

                {/* 4동 visits/revenue 비교 (grouped) */}
                <div>
                  <SectionHeader title="visits / revenue 비교" />
                  <div className="grid grid-cols-2 gap-2">
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1">
                        일평균 방문 (명)
                      </div>
                      <VerticalBarChart
                        bars={data.dong_totals.slice(0, 4).map((d) => ({
                          label: d.dong,
                          value: d.daily_visits,
                          valueText: d.daily_visits.toLocaleString('ko-KR'),
                          color: d.dong === data.dong_winner ? '#002cd1' : '#cbd5e1',
                        }))}
                        height={90}
                      />
                    </div>
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3">
                      <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1">
                        일평균 매출 (원)
                      </div>
                      <VerticalBarChart
                        bars={data.dong_totals.slice(0, 4).map((d) => ({
                          label: d.dong,
                          value: d.daily_revenue,
                          valueText: `₩${(d.daily_revenue / 1_000_000).toFixed(1)}M`,
                          color: d.dong === data.dong_winner ? '#059669' : '#cbd5e1',
                        }))}
                        height={90}
                      />
                    </div>
                  </div>
                </div>

                {/* 표 — 매장 수 / 평균 매출 / winner 메달 */}
                <div>
                  <SectionHeader title="동별 상세" />
                  <table className="w-full text-[0.625rem]">
                    <thead>
                      <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                        <th className="py-1.5 font-medium">동</th>
                        <th className="py-1.5 font-medium text-right">일방문</th>
                        <th className="py-1.5 font-medium text-right">일매출</th>
                        <th className="py-1.5 font-medium text-right">매장수</th>
                        <th className="py-1.5 font-medium text-right">평균/매장</th>
                        <th className="py-1.5 font-medium">랭크</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.dong_totals.slice(0, 4).map((d, i) => (
                        <tr
                          key={i}
                          className={`border-b border-slate-200 ${d.dong === data.dong_winner ? 'bg-slate-100' : ''}`}
                        >
                          <td className="py-1.5 font-bold text-slate-900">
                            {d.dong}
                            {d.dong === data.dong_winner && (
                              <span className="ml-1 text-[0.5rem] text-black font-black">
                                ★ 1위
                              </span>
                            )}
                          </td>
                          <td className="py-1.5 font-mono text-slate-900 text-right">
                            {d.daily_visits.toLocaleString('ko-KR')}
                          </td>
                          <td className="py-1.5 font-mono text-slate-900 text-right">
                            ₩{(d.daily_revenue / 1_000_000).toFixed(2)}M
                          </td>
                          <td className="py-1.5 font-mono text-slate-700 text-right">
                            {d.store_count ?? '—'}
                          </td>
                          <td className="py-1.5 font-mono text-slate-700 text-right">
                            {d.avg_revenue != null ? `₩${formatCompactWon(d.avg_revenue)}` : '—'}
                          </td>
                          <td className="py-1.5 font-mono text-black font-bold">#{i + 1}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 시간대 × 동 매트릭스 (heatmap-like grid) */}
                {heatMatrix.length > 0 && (
                  <div>
                    <SectionHeader
                      title="시간대 × 동 방문 매트릭스"
                      subtitle={
                        data.dong_hour_matrix == null
                          ? '24시간 분배 추정 (실제 데이터 없음)'
                          : '실측'
                      }
                    />
                    <div className="border border-slate-200 bg-white rounded-md p-3 overflow-hidden">
                      <div
                        className="grid gap-0.5"
                        style={{ gridTemplateColumns: `60px repeat(24, 1fr)` }}
                      >
                        <div className="text-[0.5rem] text-slate-400 text-center" />
                        {Array.from({ length: 24 }, (_, h) => (
                          <div key={h} className="text-[0.4375rem] text-slate-400 text-center">
                            {String(h).padStart(2, '0')}
                          </div>
                        ))}
                        {heatMatrix.slice(0, 4).map((row) => (
                          <>
                            <div
                              key={`label-${row.dong}`}
                              className="text-[0.5rem] font-bold text-slate-700 self-center"
                            >
                              {row.dong}
                            </div>
                            {row.hours.slice(0, 24).map((v, h) => (
                              <HeatCell key={`${row.dong}-${h}`} value={v} max={heatMax} />
                            ))}
                          </>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* 동별 코멘트 */}
                {data.dong_commentary.length > 0 && (
                  <div>
                    <SectionHeader title="Narrator 코멘트" />
                    <div className="space-y-1">
                      {data.dong_commentary.slice(0, 4).map((c, i) => (
                        <div
                          key={i}
                          className="rounded-md border border-slate-200 bg-slate-50 p-2.5"
                        >
                          <div className="text-[0.5625rem] font-bold text-slate-900 mb-0.5">
                            {c.dong}
                          </div>
                          <p className="text-[0.5625rem] text-slate-700 leading-relaxed">
                            {c.comment}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}

      {showScenario &&
        (() => {
          const n = ++pageNum;
          const s = data.scenario!;
          return (
            <div key={`s-${n}`} className={PAGE_CLASS}>
              <PDFPageHeader {...headerProps(n)} />
              <div className="flex-1 pt-6 flex flex-col gap-3">
                <div>
                  <h2 className="text-[1.25rem] font-black text-slate-900 mb-0.5">
                    04. 시나리오 충격
                  </h2>
                  <p className="text-[0.625rem] text-slate-500">
                    Scenario Shock · 적용 변수 + baseline 대비 변화율 + 민감도 분석
                  </p>
                </div>

                {/* 적용 시나리오 표 */}
                <div>
                  <SectionHeader title="시나리오 적용 변수" />
                  <table className="w-full text-[0.625rem]">
                    <tbody>
                      <tr className="border-b border-slate-200">
                        <td className="py-1.5 font-medium text-slate-700 w-1/3">날씨 오버라이드</td>
                        <td className="py-1.5 font-mono text-slate-900">
                          {s.weather_override ?? '—'}
                        </td>
                      </tr>
                      <tr className="border-b border-slate-200">
                        <td className="py-1.5 font-medium text-slate-700">주말 강제</td>
                        <td className="py-1.5 font-mono text-slate-900">
                          {s.weekend_force == null ? '—' : s.weekend_force ? 'ON' : 'OFF'}
                        </td>
                      </tr>
                      <tr className="border-b border-slate-200">
                        <td className="py-1.5 font-medium text-slate-700">임대료 충격</td>
                        <td className="py-1.5 font-mono text-black font-bold">
                          {s.rent_shock_pct != null
                            ? `${s.rent_shock_pct >= 0 ? '+' : ''}${(s.rent_shock_pct * 100).toFixed(0)}%`
                            : '—'}
                        </td>
                      </tr>
                      <tr className="border-b border-slate-200">
                        <td className="py-1.5 font-medium text-slate-700">매장 면적</td>
                        <td className="py-1.5 font-mono text-slate-900">
                          {s.store_area_m2 != null ? `${s.store_area_m2}m²` : '—'}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* baseline 대비 변화율 카드 3개 */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-md border border-slate-300 bg-white p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      Baseline visits
                    </div>
                    <div className="text-[0.875rem] font-bold text-black font-mono">
                      {s.baseline_visits != null ? s.baseline_visits.toLocaleString('ko-KR') : '—'}
                    </div>
                    <div className="text-[0.625rem] font-mono mt-1 font-bold text-black">
                      {s.visits_delta_pct != null
                        ? `Δ ${formatSignedPercent(s.visits_delta_pct)}`
                        : '데이터 없음'}
                    </div>
                  </div>
                  <div className="rounded-md border border-slate-300 bg-white p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      Baseline revenue
                    </div>
                    <div className="text-[0.875rem] font-bold text-black font-mono">
                      {formatMillionWon(s.baseline_revenue)}
                    </div>
                    <div className="text-[0.625rem] font-mono mt-1 font-bold text-black">
                      {s.revenue_delta_pct != null
                        ? `Δ ${formatSignedPercent(s.revenue_delta_pct)}`
                        : '데이터 없음'}
                    </div>
                  </div>
                  <div className="rounded-md border-2 border-black bg-white p-3">
                    <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                      종합 영향
                    </div>
                    <div className="text-[0.625rem] text-slate-700 leading-relaxed">
                      적용 시나리오로 매출{' '}
                      {s.revenue_delta_pct != null
                        ? `${s.revenue_delta_pct >= 0 ? '증가' : '감소'} ${Math.abs(s.revenue_delta_pct * 100).toFixed(1)}%`
                        : '변화 미측정'}
                      , 방문 수{' '}
                      {s.visits_delta_pct != null
                        ? `${s.visits_delta_pct >= 0 ? '증가' : '감소'} ${Math.abs(s.visits_delta_pct * 100).toFixed(1)}%`
                        : '변화 미측정'}
                      .
                    </div>
                  </div>
                </div>

                {/* 민감도 분석 */}
                {s.sensitivity.length > 0 && (
                  <div>
                    <SectionHeader title="민감도 분석" subtitle="변수별 매출 영향" />
                    <div className="border border-slate-200 bg-slate-50 rounded-md p-3 space-y-1">
                      {s.sensitivity.slice(0, 6).map((sens, i) => {
                        const positive = sens.impact_pct >= 0;
                        const maxAbs = Math.max(
                          0.001,
                          ...s.sensitivity.map((x) => Math.abs(x.impact_pct)),
                        );
                        return (
                          <SignedBarRow
                            key={i}
                            label={sens.variable}
                            signedText={`${positive ? '+' : ''}${(sens.impact_pct * 100).toFixed(1)}%`}
                            ratio={Math.abs(sens.impact_pct) / maxAbs}
                            positive={positive}
                          />
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* narrator_summary 풀 박스 */}
                {s.narrator_summary && (
                  <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                    <div className="text-[0.5rem] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      Narrator Summary
                    </div>
                    <p className="text-[0.625rem] text-slate-800 leading-relaxed whitespace-pre-line">
                      {s.narrator_summary}
                    </p>
                  </div>
                )}

                {/* 추가 시나리오 권고 */}
                <div className="mt-auto rounded-md border border-slate-500 bg-slate-50 p-3">
                  <div className="text-[0.5rem] font-bold text-black uppercase tracking-wider mb-1">
                    추가 시나리오 권고
                  </div>
                  <ul className="space-y-0.5 text-[0.5625rem] text-slate-700 leading-relaxed">
                    <li>· 임대료 +20% / -10% 양 극단 추가 실험</li>
                    <li>· 주말 강제 ON + 날씨 비 시나리오 결합</li>
                    <li>· 매장 면적 30/50/80m² 비교</li>
                    <li>· 경쟁 매장 신규 출점 시뮬과 결합 분석</li>
                  </ul>
                </div>
              </div>
              <PDFPageFooter reportDate={reportDate} />
            </div>
          );
        })()}
    </>
  );
}

/* ═══════════════════════════════════════════════════════
   공용 KPI / 시나리오 카드
   ═══════════════════════════════════════════════════════ */
function KpiCard({
  title,
  value,
  accent = '#0f172a',
}: {
  title: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="border border-slate-200 bg-slate-50 p-4 rounded-lg">
      <div className="text-[0.5625rem] text-slate-500 mb-2 uppercase tracking-wider">{title}</div>
      <div
        className="text-[0.9375rem] font-black leading-tight font-mono"
        style={{ color: accent }}
      >
        {value}
      </div>
    </div>
  );
}

function ScenarioCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number | null;
  color: string;
}) {
  return (
    <div className="border border-slate-200 bg-white p-4 rounded-lg">
      <div className="text-[0.625rem] font-bold uppercase tracking-wider mb-2" style={{ color }}>
        {label}
      </div>
      <div className="text-[0.875rem] font-bold font-mono text-slate-900">
        {value != null ? `₩${(value / 1_000_000).toFixed(1)}M` : '—'}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   LEGACY PDF — 기존 4~5 페이지 (호환 유지)
   ═══════════════════════════════════════════════════════ */
function LegacyPages({
  districtFull,
  reportDate,
  docId,
  stats,
  cannibalizationRows,
  neighborhoodRows,
  insights,
  customerSegment,
}: {
  districtFull: string;
  reportDate: string;
  docId: string;
  stats: { title: string; value: string; trend: string }[];
  cannibalizationRows: CannRow[];
  neighborhoodRows: NeighborhoodRow[];
  insights: { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[];
  customerSegment?: CustomerSegment | null;
}) {
  const TOTAL_PAGES = customerSegment ? 5 : 4;
  // 인사이트 심각도 — 검정 톤 명도차 (critical=가장 진함, opportunity=가장 옅음)
  const severityStyle = {
    critical: { dot: 'bg-black', bg: 'bg-slate-100 border-black' },
    advisory: { dot: 'bg-slate-700', bg: 'bg-slate-50 border-slate-500' },
    opportunity: { dot: 'bg-slate-400', bg: 'bg-white border-slate-300' },
  };

  return (
    <>
      {/* Page 1: Cover */}
      <div className={PAGE_CLASS}>
        <div className="flex-1 flex flex-col items-center justify-center">
          <svg width="200" height="78" viewBox="0 0 78 30" fill="none" className="mb-10">
            {SPOTTER_LOGO_PATHS}
          </svg>
          <p className="text-black font-mono text-[0.6875rem] tracking-[0.3em] border border-black px-5 py-1.5 rounded-full bg-white mb-16">
            AI FRANCHISE INTELLIGENCE REPORT
          </p>
          <h1 className="text-[2.75rem] font-black text-slate-900 text-center leading-[1.2] tracking-tight">
            {districtFull}
            <br />
            상권 분석 결과
          </h1>
          <p className="text-sm text-slate-500 mt-6 tracking-wide">
            SPOTTER AI Multi-Agent Analysis · LangGraph
          </p>
        </div>
        <div className="flex justify-between items-end font-mono text-[0.625rem] text-slate-500 pt-6 border-t border-slate-200">
          <div className="space-y-1.5">
            <p className="tracking-wider">GENERATED · {reportDate}</p>
            <p className="tracking-wider">REQUESTED BY · SPOTTER-HQ</p>
            <p className="tracking-wider">DOCUMENT ID · {docId}</p>
          </div>
          <div className="font-bold text-black text-sm tracking-[0.25em]">CONFIDENTIAL</div>
        </div>
      </div>

      {/* Page 2: 종합 요약 */}
      <div className={PAGE_CLASS}>
        <PDFPageHeader pageNumber={2} totalPages={TOTAL_PAGES} districtFull={districtFull} />
        <div className="flex-1 pt-8">
          <h2 className="text-[1.375rem] font-black text-slate-900 mb-1">01. 상권 종합 요약</h2>
          <p className="text-xs text-slate-500 mb-6">Executive Summary · 핵심 KPI</p>
          <div className="grid grid-cols-3 gap-3 mb-8">
            {stats.map((s, i) => (
              <div key={i} className="border border-slate-200 bg-slate-50 p-4 rounded-lg">
                <div className="text-[0.5625rem] text-slate-500 mb-2 uppercase tracking-wider">
                  {s.title}
                </div>
                <div className="text-[0.9375rem] font-black text-slate-900 leading-tight">
                  {s.value}
                </div>
                <div className="text-[0.5625rem] text-slate-700 mt-1.5 font-mono">{s.trend}</div>
              </div>
            ))}
          </div>
        </div>
        <PDFPageFooter reportDate={reportDate} />
      </div>

      {/* Page 3: 데이터 테이블 */}
      <div className={PAGE_CLASS}>
        <PDFPageHeader pageNumber={3} totalPages={TOTAL_PAGES} districtFull={districtFull} />
        <div className="flex-1 pt-8 space-y-10">
          <div>
            <h2 className="text-[1.375rem] font-black text-slate-900 mb-1">
              02. 가맹점 간섭도 분석
            </h2>
            <p className="text-xs text-slate-500 mb-4">Cannibalization Analysis</p>
            <table className="w-full text-[0.6875rem]">
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
                        className={`px-2 py-0.5 text-[0.5625rem] rounded-full border font-bold ${
                          r.status === 'Safe'
                            ? 'bg-white text-black border-black'
                            : 'bg-slate-100 text-slate-700 border-slate-300'
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
            <h2 className="text-[1.375rem] font-black text-slate-900 mb-1">03. 행정동 비교 분석</h2>
            <p className="text-xs text-slate-500 mb-4">Neighborhood Comparison</p>
            <table className="w-full text-[0.6875rem]">
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
                    <td className="py-3 font-mono text-black font-bold">{r.bep}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <PDFPageFooter reportDate={reportDate} />
      </div>

      {/* Page 4: 인사이트 */}
      <div className={PAGE_CLASS}>
        <PDFPageHeader pageNumber={4} totalPages={TOTAL_PAGES} districtFull={districtFull} />
        <div className="flex-1 pt-8">
          <h2 className="text-[1.375rem] font-black text-slate-900 mb-1">
            04. SPOTTER AI 인사이트
          </h2>
          <p className="text-xs text-slate-500 mb-6">LangGraph Multi-Agent Analysis</p>
          {insights.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-10 text-center">
              <p className="text-[0.75rem] font-semibold text-slate-600">인사이트 데이터 없음</p>
            </div>
          ) : (
            <div className="space-y-4">
              {insights.map((insight, i) => {
                const style = severityStyle[insight.severity];
                return (
                  <div key={i} className={`border rounded-lg p-5 ${style.bg}`}>
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="text-[0.875rem] font-bold text-slate-900 flex-1">
                        {insight.title}
                      </h3>
                      <span className="inline-flex items-center gap-1.5 shrink-0 ml-3">
                        <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                        <span className="text-[0.5625rem] font-mono uppercase tracking-[0.15em] text-slate-500">
                          {insight.severity.toUpperCase()}
                        </span>
                      </span>
                    </div>
                    <p className="text-[0.6875rem] text-slate-700 leading-relaxed">
                      {insight.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
          <div className="mt-10 pt-6 border-t border-slate-200">
            <p className="text-[0.5625rem] text-slate-400 mt-3 font-mono">
              DOC ID · {docId} · SPOTTER v3.9
            </p>
          </div>
        </div>
        <PDFPageFooter reportDate={reportDate} />
      </div>

      {/* Page 5: customer_segment (있을 때만) */}
      {customerSegment && (
        <div className={PAGE_CLASS}>
          <PDFPageHeader pageNumber={5} totalPages={TOTAL_PAGES} districtFull={districtFull} />
          <div className="flex-1 pt-8">
            <h2 className="text-[1.375rem] font-black text-slate-900 mb-1">
              05. 타겟 고객 매출 분석
            </h2>
            <p className="text-xs text-slate-500 mb-6">Target Customer Segmentation</p>
            {customerSegment.profile_summary && (
              <div className="mb-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-[0.75rem] text-slate-800 leading-relaxed">
                  {customerSegment.profile_summary}
                </p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3 mb-6">
              <KpiCard
                title="세그먼트 비율"
                value={
                  typeof customerSegment.segment_ratio === 'number'
                    ? `${(customerSegment.segment_ratio * 100).toFixed(2)}%`
                    : '—'
                }
                accent="#000000"
              />
              <KpiCard
                title="타겟 매출"
                value={
                  customerSegment.segment_sales != null
                    ? `₩${formatCompactWon(customerSegment.segment_sales)}`
                    : '—'
                }
                accent="#000000"
              />
            </div>
          </div>
          <PDFPageFooter reportDate={reportDate} />
        </div>
      )}
    </>
  );
}

/* ═══════════════════════════════════════════════════════
   메인 컴포넌트
   ═══════════════════════════════════════════════════════ */
export const HiddenPDFTemplate = forwardRef<HTMLDivElement, HiddenPDFTemplateProps>(
  (
    {
      mode = 'legacy',
      districtFull,
      reportDate,
      savedHistoryId = null,
      stats = [],
      cannibalizationRows = [],
      neighborhoodRows = [],
      insights = [],
      customerSegment = null,
      foresee,
      ai,
      abm,
    },
    ref,
  ) => {
    const docId = formatDocumentId(savedHistoryId);

    return (
      <div
        ref={ref}
        className="absolute top-[-9999px] left-[-9999px] w-[794px] bg-white font-sans"
        style={{ fontFamily: 'Pretendard, sans-serif' }}
      >
        {mode === 'foresee' && foresee && (
          <ForeseePages
            data={foresee}
            districtFull={districtFull}
            reportDate={reportDate}
            docId={docId}
          />
        )}
        {mode === 'ai' && ai && (
          <AiPages data={ai} districtFull={districtFull} reportDate={reportDate} docId={docId} />
        )}
        {mode === 'abm' && abm && (
          <AbmPages data={abm} districtFull={districtFull} reportDate={reportDate} docId={docId} />
        )}
        {mode === 'legacy' && (
          <LegacyPages
            districtFull={districtFull}
            reportDate={reportDate}
            docId={docId}
            stats={stats}
            cannibalizationRows={cannibalizationRows}
            neighborhoodRows={neighborhoodRows}
            insights={insights}
            customerSegment={customerSegment}
          />
        )}
      </div>
    );
  },
);
HiddenPDFTemplate.displayName = 'HiddenPDFTemplate';
