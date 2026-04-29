/**
 * CompareHiddenTemplate — 저장된 시뮬 최대 4건 비교 리포트 (A4 landscape 1페이지).
 *
 * 설계 원칙: 기존 HiddenPDFTemplate과 동일한 light theme + 인쇄 품질.
 * 화면에 보이지 않도록 absolute top:-9999px, html2canvas가 캡처 → jsPDF가 A4 landscape로 변환.
 * 고정 크기: 1123 × 794 (A4 landscape @ 96dpi, scale=2로 캡처해 고해상도).
 */

import { forwardRef } from 'react';
import { formatDocumentId } from '../../types/simulationHistory';

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

export interface CompareShapItem {
  label: string;
  value: number;
}

export interface CompareItem {
  id: number;
  clientName: string;
  brandName: string;
  businessType: string | null;
  district: string;
  createdAt: string; // ISO
  signal: 'green' | 'yellow' | 'red' | null;
  monthlyRev: number | null;
  annualRev: number | null;
  netProfit: number | null;
  margin: number | null;
  bep: number | null;
  closure: number | null;
  closureLevel: 'safe' | 'caution' | 'danger' | null;
  legalHigh: number;
  legalTotal: number;
  confidencePct: number | null;
  winnerDistrict: string | null;
  shapTop: CompareShapItem[];
  recommendation: string | null;
}

interface Props {
  items: CompareItem[];
  reportDate: string;
}

const SIGNAL_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  green: { bg: 'bg-emerald-100 border-emerald-300', text: 'text-emerald-700', label: '진입 권장' },
  yellow: { bg: 'bg-amber-100 border-amber-300', text: 'text-amber-700', label: '조건부 진입' },
  red: { bg: 'bg-rose-100 border-rose-300', text: 'text-rose-700', label: '진입 비권장' },
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatWon(v: number | null | undefined): string {
  if (v == null) return '—';
  const abs = Math.abs(v);
  if (abs >= 100_000_000) return `₩${(v / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `₩${Math.round(v / 10_000).toLocaleString()}만`;
  return `₩${v.toLocaleString()}`;
}

const CompareHiddenTemplate = forwardRef<HTMLDivElement, Props>(({ items, reportDate }, ref) => {
  const n = items.length;
  const gridCols =
    n === 1 ? 'grid-cols-1' : n === 2 ? 'grid-cols-2' : n === 3 ? 'grid-cols-3' : 'grid-cols-4';
  // 1페이지: 1123 × 794 (A4 landscape)
  const pageClass = 'w-[1123px] h-[794px] p-10 bg-white text-slate-900 relative flex flex-col';

  return (
    <div
      ref={ref}
      className="absolute top-[-9999px] left-[-9999px] w-[1123px] bg-white font-sans"
      style={{ fontFamily: 'Pretendard, sans-serif' }}
    >
      <div className={pageClass}>
        {/* Header */}
        <div className="flex items-end justify-between border-b-2 border-slate-200 pb-4">
          <div className="flex items-center gap-3">
            <svg width="44" height="17" viewBox="0 0 78 30" fill="none">
              {SPOTTER_LOGO_PATHS}
            </svg>
            <div>
              <h1 className="text-[1.25rem] font-black text-slate-900 leading-none tracking-tight">
                SPOTTER 입지 비교 리포트
              </h1>
              <p className="text-[0.6875rem] text-slate-500 mt-1">
                Side-by-side Comparison · {n}건 · AI Multi-Agent Analysis
              </p>
            </div>
          </div>
          <div className="text-right font-mono text-[0.625rem] text-slate-500">
            <p>GENERATED · {reportDate}</p>
            <p>REQUESTED BY · SPOTTER-HQ</p>
            <p className="text-rose-500 font-bold tracking-[0.2em] mt-1">CONFIDENTIAL</p>
          </div>
        </div>

        {/* Comparison Grid */}
        <div className={`grid ${gridCols} gap-4 flex-1 pt-5`}>
          {items.map((it) => (
            <ComparisonColumn key={it.id} item={it} />
          ))}
        </div>

        {/* Footer */}
        <div className="mt-4 flex justify-between border-t border-slate-200 pt-3 font-mono text-[0.5625rem] text-slate-400 tracking-wider">
          <span>© PROJECT SPOTTER · CONFIDENTIAL · LangGraph Multi-Agent</span>
          <span>PAGE 1 / 1</span>
        </div>
      </div>
    </div>
  );
});
CompareHiddenTemplate.displayName = 'CompareHiddenTemplate';

function ComparisonColumn({ item }: { item: CompareItem }) {
  const sig = item.signal ? SIGNAL_BADGE[item.signal] : null;
  const docId = formatDocumentId(item.id);

  const rows: { label: string; value: string; tone?: 'good' | 'warn' | 'bad' }[] = [
    { label: '예상 월매출', value: formatWon(item.monthlyRev) },
    { label: '연 매출 (TCN 합산)', value: formatWon(item.annualRev) },
    {
      label: '월 영업이익',
      value: formatWon(item.netProfit),
      tone: (item.netProfit ?? 0) > 0 ? 'good' : undefined,
    },
    {
      label: '마진율',
      value: item.margin != null ? `${(item.margin * 100).toFixed(1)}%` : '—',
    },
    {
      label: 'BEP (개월)',
      value: item.bep != null ? `${item.bep.toFixed(1)}` : '—',
      tone:
        item.bep == null ? undefined : item.bep <= 12 ? 'good' : item.bep <= 18 ? 'warn' : 'bad',
    },
    {
      label: '폐업 위험도',
      value: item.closure != null ? `${Math.round(item.closure)}/100` : '—',
      tone:
        item.closureLevel === 'safe'
          ? 'good'
          : item.closureLevel === 'danger'
            ? 'bad'
            : item.closureLevel === 'caution'
              ? 'warn'
              : undefined,
    },
    {
      label: '법률 리스크 (HIGH)',
      value: item.legalTotal > 0 ? `${item.legalHigh}/${item.legalTotal}` : '—',
      tone: item.legalHigh > 0 ? 'bad' : 'good',
    },
    {
      label: 'AI 신뢰도',
      value: item.confidencePct != null ? `${item.confidencePct}%` : '—',
    },
  ];

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      {/* Column header */}
      <div className="border-b border-slate-200 pb-2">
        <div className="flex items-center gap-2 mb-1">
          <span className="rounded bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 text-[0.5625rem] font-mono font-bold text-indigo-700">
            {docId}
          </span>
          <span className="text-[0.5625rem] font-mono text-slate-400">{formatDate(item.createdAt)}</span>
        </div>
        <div className="text-[0.875rem] font-black text-slate-900 leading-tight truncate">
          {item.clientName}
        </div>
        <div className="text-[0.625rem] text-slate-600">
          {item.brandName}
          {item.businessType && <span className="text-slate-400"> · {item.businessType}</span>}
        </div>
        <div className="text-[0.625rem] text-indigo-600 font-bold mt-0.5">마포구 {item.district}</div>
      </div>

      {/* Entry signal */}
      {sig ? (
        <div className={`rounded border ${sig.bg} p-2 text-center`}>
          <div className={`text-[0.5rem] font-black uppercase tracking-widest ${sig.text}`}>
            Entry Signal
          </div>
          <div className={`text-[0.75rem] font-black ${sig.text} leading-tight`}>{sig.label}</div>
        </div>
      ) : (
        <div className="rounded border border-slate-200 bg-slate-50 p-2 text-center">
          <span className="text-[0.625rem] text-slate-500">신호 미판정</span>
        </div>
      )}

      {/* Metrics */}
      <div className="flex-1 flex flex-col gap-1">
        {rows.map((r) => (
          <ComparisonRow key={r.label} label={r.label} value={r.value} tone={r.tone} />
        ))}
      </div>

      {/* SHAP top 3 */}
      {item.shapTop.length > 0 && (
        <div className="border-t border-slate-200 pt-2">
          <div className="text-[0.5rem] font-black uppercase tracking-widest text-slate-500 mb-1">
            매출 기여 Top {item.shapTop.length}
          </div>
          <div className="flex flex-col gap-0.5">
            {item.shapTop.map((s, i) => {
              const pos = s.value >= 0;
              return (
                <div key={`${s.label}-${i}`} className="flex items-center justify-between">
                  <span className="text-[0.5625rem] text-slate-700 truncate mr-1">{s.label}</span>
                  <span
                    className={`font-mono font-bold text-[0.5625rem] tabular-nums ${
                      pos ? 'text-indigo-600' : 'text-rose-600'
                    }`}
                  >
                    {pos ? '+' : ''}
                    {formatWon(s.value)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Winner / Recommendation */}
      {item.winnerDistrict && (
        <div className="text-[0.5625rem] text-slate-600">
          <span className="text-slate-400">추천 동:</span>{' '}
          <span className="font-bold text-indigo-700">{item.winnerDistrict}</span>
        </div>
      )}
    </div>
  );
}

function ComparisonRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'good' | 'warn' | 'bad';
}) {
  const toneCls =
    tone === 'good'
      ? 'text-emerald-700'
      : tone === 'warn'
        ? 'text-amber-700'
        : tone === 'bad'
          ? 'text-rose-700'
          : 'text-slate-900';
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-0.5">
      <span className="text-[0.5625rem] text-slate-500">{label}</span>
      <span className={`text-[0.625rem] font-black tabular-nums ${toneCls}`}>{value}</span>
    </div>
  );
}

export default CompareHiddenTemplate;
