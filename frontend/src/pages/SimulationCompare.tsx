/**
 * SimulationCompare — 저장된 시뮬 이력 최대 4건 side-by-side 비교 + PDF export
 *
 * 경로: /dashboard/compare?ids=1,2,3,4
 * 데이터 소스: simulation_history.simulation_result (JSONB) 전체 재활용.
 * B2B 영업팀이 가맹점주 설득 자료로 바로 인쇄할 수 있도록 PDF export 지원.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, FileDown, Loader2, AlertCircle } from 'lucide-react';
import { getSimulationHistoryDetail } from '../api/client';
import type { SimulationHistoryDetail } from '../types/simulationHistory';
import { formatDocumentId } from '../types/simulationHistory';
import CompareHiddenTemplate, { type CompareItem } from '../components/PDF/CompareHiddenTemplate';

const MAX_COMPARE = 4;

const SIGNAL_CLS: Record<string, string> = {
  green: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  yellow: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/40',
  red: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
};
const SIGNAL_LABEL: Record<string, string> = {
  green: '진입 권장',
  yellow: '조건부 진입',
  red: '진입 비권장',
};

function formatWon(v: number | null | undefined): string {
  if (v == null) return '—';
  const abs = Math.abs(v);
  if (abs >= 100_000_000) return `₩${(v / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `₩${Math.round(v / 10_000).toLocaleString()}만`;
  return `₩${v.toLocaleString()}`;
}

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

function parseIdsParam(raw: string | null): number[] {
  if (!raw) return [];
  return Array.from(
    new Set(
      raw
        .split(',')
        .map((s) => Number.parseInt(s.trim(), 10))
        .filter((n) => Number.isFinite(n) && n > 0),
    ),
  ).slice(0, MAX_COMPARE);
}

interface DetailState {
  id: number;
  loading: boolean;
  data: SimulationHistoryDetail | null;
  error: string | null;
}

/** simulation_result에서 비교 관점 핵심 필드 추출 (JSONB 구조 방어적) */
function extractMetrics(d: SimulationHistoryDetail | null) {
  if (!d) return null;
  const r = d.simulation_result as any;
  const qp = Array.isArray(r?.quarterly_projection) ? r.quarterly_projection : [];
  const firstQ = qp[0];
  const ps = r?.final_report?.profit_simulation ?? null;
  const monthlyRev =
    ps?.monthly_revenue ?? (firstQ?.revenue ? Math.round(firstQ.revenue / 3) : null);
  const annualRev = qp.reduce((sum: number, q: any) => sum + (q?.revenue ?? 0), 0) || null;
  const bep = ps?.bep_months ?? null;
  const netProfit = ps?.net_profit ?? null;
  const margin = ps?.margin_rate ?? null;
  // 백엔드 risk_score는 0~1 소수점 — 0~100 스케일로 정규화
  const closureRaw = r?.closure_risk?.risk_score ?? null;
  const closure =
    closureRaw == null
      ? null
      : closureRaw <= 1
        ? Math.round(closureRaw * 100)
        : Math.round(closureRaw);
  const closureLevel = r?.closure_risk?.risk_level ?? null;
  const legalRisks = Array.isArray(r?.legal_risks) ? r.legal_risks : [];
  const legalHigh = legalRisks.filter(
    (x: any) => String(x?.risk_level ?? '').toUpperCase() === 'HIGH' || x?.risk_level === 'danger',
  ).length;
  const shap = Array.isArray(r?.shap_result?.feature_importance)
    ? r.shap_result.feature_importance.slice(0, 3).map((f: any) => ({
        label: f?.feature_ko || f?.feature || '—',
        value: f?.shap_value ?? 0,
      }))
    : [];
  const synthAttr = Array.isArray(r?.agent_attributions)
    ? r.agent_attributions.find((a: any) => a?.id === 'synthesis')
    : null;
  const confidencePct =
    synthAttr?.confidence != null ? Math.round(synthAttr.confidence * 100) : null;
  const winnerDistrict = r?.winner_district ?? null;
  const recommendation = r?.final_report?.final_recommendation ?? r?.ai_recommendation ?? null;
  return {
    monthlyRev,
    annualRev,
    bep,
    netProfit,
    margin,
    closure,
    closureLevel,
    legalHigh,
    legalTotal: legalRisks.length,
    shap,
    confidencePct,
    winnerDistrict,
    recommendation,
  };
}

function toCompareItem(d: SimulationHistoryDetail): CompareItem {
  const m = extractMetrics(d)!;
  return {
    id: d.id,
    clientName: d.client_name,
    brandName: d.brand_name,
    businessType: d.business_type,
    district: d.district,
    createdAt: d.created_at,
    signal: (d.market_entry_signal as CompareItem['signal']) ?? null,
    monthlyRev: m.monthlyRev,
    annualRev: m.annualRev,
    netProfit: m.netProfit,
    margin: m.margin,
    bep: m.bep,
    closure: m.closure,
    closureLevel: m.closureLevel as CompareItem['closureLevel'],
    legalHigh: m.legalHigh,
    legalTotal: m.legalTotal,
    confidencePct: m.confidencePct,
    winnerDistrict: m.winnerDistrict,
    shapTop: m.shap,
    recommendation: m.recommendation,
  };
}

export default function SimulationCompare() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const ids = useMemo(() => parseIdsParam(searchParams.get('ids')), [searchParams]);
  const [details, setDetails] = useState<DetailState[]>([]);
  const hiddenPdfRef = useRef<HTMLDivElement | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  // 각 id별 병렬 fetch
  useEffect(() => {
    if (ids.length === 0) return;
    let cancelled = false;
    setDetails(ids.map((id) => ({ id, loading: true, data: null, error: null })));
    ids.forEach((id) => {
      getSimulationHistoryDetail(id)
        .then((data) => {
          if (cancelled) return;
          setDetails((prev) => prev.map((d) => (d.id === id ? { ...d, loading: false, data } : d)));
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          const msg = err instanceof Error ? err.message : '조회 실패';
          setDetails((prev) =>
            prev.map((d) => (d.id === id ? { ...d, loading: false, error: msg } : d)),
          );
        });
    });
    return () => {
      cancelled = true;
    };
  }, [ids]);

  const handleExportPdf = async () => {
    if (!hiddenPdfRef.current || isExporting) return;
    setIsExporting(true);
    try {
      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
        import('html2canvas'),
        import('jspdf'),
      ]);
      const node = hiddenPdfRef.current;
      const pages = Array.from(node.children) as HTMLElement[];
      const pdf = new jsPDF('l', 'mm', 'a4');
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
      const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      pdf.save(`SPOTTER_compare_${ids.length}items_${stamp}.pdf`);
    } catch (err) {
      console.error('[compare] PDF export failed', err);
      window.alert('PDF 내보내기에 실패했습니다. 콘솔을 확인해주세요.');
    } finally {
      setIsExporting(false);
    }
  };

  if (ids.length === 0) {
    return (
      <div className="min-h-screen bg-[#1e1b18] p-10 text-stone-200">
        <div className="mx-auto max-w-2xl rounded-xl border border-amber-500/30 bg-amber-500/10 p-6">
          <div className="flex items-center gap-2 text-amber-400">
            <AlertCircle size={16} />
            <span className="font-bold">비교할 시뮬 이력이 선택되지 않았습니다.</span>
          </div>
          <p className="mt-2 text-sm text-amber-200/80">
            "내 시뮬 이력"에서 2건 이상을 체크한 뒤 비교하기를 눌러주세요.
          </p>
          <button
            onClick={() => navigate('/hq?tab=history')}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#818cf8] px-4 py-2 text-xs font-bold text-[#1e1b18] hover:bg-[#6366f1]"
          >
            <ArrowLeft size={14} />
            이력 목록으로
          </button>
        </div>
      </div>
    );
  }

  const cols = details.length || ids.length;
  const gridCols =
    cols === 1
      ? 'grid-cols-1'
      : cols === 2
        ? 'grid-cols-1 md:grid-cols-2'
        : cols === 3
          ? 'grid-cols-1 md:grid-cols-3'
          : 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4';

  const loadedItems = details.filter((d) => d.data !== null).map((d) => toCompareItem(d.data!));
  const pdfReportDate = `${new Date().getFullYear()}.${String(new Date().getMonth() + 1).padStart(2, '0')}.${String(new Date().getDate()).padStart(2, '0')}`;

  return (
    <div className="min-h-screen bg-[#1e1b18] p-8 text-stone-200">
      <div className="mx-auto max-w-[1600px]">
        {/* 툴바 */}
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-2 rounded-lg border border-stone-700 bg-[#2c2825] px-4 py-2 text-xs font-bold text-stone-300 hover:border-stone-600 hover:text-stone-100"
          >
            <ArrowLeft size={14} />
            이력으로 돌아가기
          </button>
          <div className="flex items-center gap-3">
            <span className="text-xs text-stone-500">
              <span className="font-mono text-stone-100">{ids.length}</span>건 비교
            </span>
            <button
              onClick={handleExportPdf}
              disabled={isExporting}
              className="inline-flex items-center gap-2 rounded-lg bg-[#818cf8] px-4 py-2 text-xs font-bold text-[#1e1b18] shadow-[0_0_20px_rgba(129,140,248,0.3)] hover:bg-[#6366f1] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isExporting ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <FileDown size={14} />
              )}
              {isExporting ? '생성 중…' : 'PDF 내보내기'}
            </button>
          </div>
        </div>

        {/* 화면 미리보기 영역 */}
        <div className="rounded-2xl border border-stone-800 bg-[#2c2825] p-6">
          <div className="mb-6 flex items-center justify-between border-b border-stone-800 pb-4">
            <div>
              <h1 className="text-lg font-black text-stone-100">시뮬레이션 비교 리포트</h1>
              <p className="mt-1 text-xs text-stone-500">
                SPOTTER · 생성일 {new Date().toLocaleString('ko-KR')}
              </p>
            </div>
          </div>

          <div className={`grid gap-4 ${gridCols}`}>
            {details.map((d) => (
              <CompareColumn key={d.id} state={d} />
            ))}
          </div>
        </div>

        {/* 화면 밖 A4 landscape 템플릿 — PDF 캡처 전용 */}
        {loadedItems.length > 0 && (
          <CompareHiddenTemplate
            ref={hiddenPdfRef}
            items={loadedItems}
            reportDate={pdfReportDate}
          />
        )}
      </div>
    </div>
  );
}

function CompareColumn({ state }: { state: DetailState }) {
  const { id, loading, data, error } = state;

  if (loading) {
    return (
      <div className="rounded-xl border border-dashed border-stone-700 bg-[#1e1b18] p-6 text-center">
        <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-stone-500" />
        <span className="text-xs text-stone-500">불러오는 중…</span>
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-500/5 p-6">
        <div className="flex items-center gap-2 text-rose-400">
          <AlertCircle size={14} />
          <span className="text-xs font-bold">조회 실패</span>
        </div>
        <p className="mt-2 text-[0.6875rem] text-rose-300/80">
          ID {id} · {error ?? '데이터 없음'}
        </p>
      </div>
    );
  }

  const m = extractMetrics(data)!;
  const signalKey = data.market_entry_signal ?? '';
  const signalCls = SIGNAL_CLS[signalKey] ?? 'bg-stone-700/40 text-stone-300 border-stone-600';
  const signalLbl = SIGNAL_LABEL[signalKey] ?? '—';
  const docId = formatDocumentId(data.id);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-stone-700 bg-[#1e1b18] p-5">
      {/* Header */}
      <div className="border-b border-stone-800 pb-3">
        <span className="text-[0.5625rem] font-mono text-indigo-400">{docId}</span>
        <div className="mt-1 text-sm font-bold text-stone-100 truncate">{data.client_name}</div>
        <div className="text-[0.6875rem] text-stone-400">
          {data.brand_name}
          {data.business_type && <span className="text-stone-600"> · {data.business_type}</span>}
        </div>
        <div className="mt-1 text-[0.625rem] text-stone-500">
          {data.district} · {formatDate(data.created_at)}
        </div>
      </div>

      {/* Signal */}
      <div className={`rounded-lg border px-3 py-2 text-center ${signalCls}`}>
        <span className="text-[0.5625rem] font-black uppercase tracking-widest">Entry Signal</span>
        <div className="mt-0.5 text-sm font-black">{signalLbl}</div>
      </div>

      {/* Metrics table */}
      <div className="space-y-2">
        <MetricRow label="예상 월매출" value={formatWon(m.monthlyRev)} />
        <MetricRow label="연 매출 (TCN 합산)" value={formatWon(m.annualRev)} />
        <MetricRow
          label="월 영업이익"
          value={formatWon(m.netProfit)}
          tone={(m.netProfit ?? 0) > 0 ? 'good' : 'neutral'}
        />
        <MetricRow
          label="마진율"
          value={m.margin != null ? `${(m.margin * 100).toFixed(1)}%` : '—'}
        />
        <MetricRow
          label="BEP (개월)"
          value={m.bep != null ? `${m.bep.toFixed(1)}` : '—'}
          tone={m.bep == null ? 'neutral' : m.bep <= 12 ? 'good' : m.bep <= 18 ? 'warn' : 'bad'}
        />
        <MetricRow
          label="폐업 위험도"
          value={m.closure != null ? `${Math.round(m.closure)}/100` : '—'}
          tone={
            m.closureLevel === 'safe'
              ? 'good'
              : m.closureLevel === 'danger'
                ? 'bad'
                : m.closureLevel === 'caution'
                  ? 'warn'
                  : 'neutral'
          }
        />
        <MetricRow
          label="법률 리스크 (HIGH)"
          value={m.legalTotal > 0 ? `${m.legalHigh}/${m.legalTotal}` : '—'}
          tone={m.legalHigh > 0 ? 'bad' : 'good'}
        />
        <MetricRow
          label="AI 신뢰도"
          value={m.confidencePct != null ? `${m.confidencePct}%` : '—'}
        />
        {m.winnerDistrict && <MetricRow label="추천 동" value={m.winnerDistrict} />}
      </div>

      {/* SHAP top 3 */}
      {m.shap.length > 0 && (
        <div className="border-t border-stone-800 pt-3">
          <div className="mb-2 text-[0.5625rem] font-black uppercase tracking-widest text-stone-500">
            매출 기여 요인 Top {m.shap.length}
          </div>
          <div className="flex flex-col gap-1.5">
            {m.shap.map((s: { label: string; value: number }, i: number) => {
              const pos = s.value >= 0;
              return (
                <div
                  key={`${s.label}-${i}`}
                  className="flex items-center justify-between text-[0.625rem]"
                >
                  <span className="truncate text-stone-300">{s.label}</span>
                  <span
                    className={`font-mono font-bold tabular-nums ${pos ? 'text-indigo-400' : 'text-rose-400'}`}
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

      {/* Recommendation */}
      {m.recommendation && (
        <div className="border-t border-stone-800 pt-3">
          <div className="mb-1 text-[0.5625rem] font-black uppercase tracking-widest text-stone-500">
            AI 판정
          </div>
          <p className="text-[0.625rem] leading-relaxed text-stone-400 line-clamp-6">
            {m.recommendation}
          </p>
        </div>
      )}
    </div>
  );
}

function MetricRow({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: 'good' | 'warn' | 'bad' | 'neutral';
}) {
  const toneCls =
    tone === 'good'
      ? 'text-emerald-400'
      : tone === 'warn'
        ? 'text-amber-400'
        : tone === 'bad'
          ? 'text-rose-400'
          : 'text-stone-100';
  return (
    <div className="flex items-center justify-between border-b border-stone-800/60 pb-1.5">
      <span className="text-[0.625rem] text-stone-500">{label}</span>
      <span className={`text-xs font-black tabular-nums ${toneCls}`}>{value}</span>
    </div>
  );
}
