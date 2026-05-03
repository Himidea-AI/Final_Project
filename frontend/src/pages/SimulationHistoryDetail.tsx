import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, FileDown, Loader2, RotateCw } from 'lucide-react';
import { useSimulationDetail } from '../hooks/useSimulationDetail';
import { HistoryDashboardView } from './HistoryDashboardView';
import { formatDocumentId, type SimulationKind } from '../types/simulationHistory';
import { HiddenPDFTemplate } from '../components/PDF/HiddenPDFTemplate';
import { buildPdfPropsFromSimulation } from '../utils/pdfPropsBuilder';
import { useSimulationStore } from '../stores/simulationStore';
import type { SimulationInput } from '../types';

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ko-KR', { hour12: false });
  } catch {
    return iso;
  }
}

interface SimulationHistoryDetailProps {
  /**
   * 진입 라우트 별 kind 주입 — App.tsx 에서 wrapper element 로 prop 전달.
   * - 'foresee' : /dashboard/foresee/:id
   * - 'ai'      : /dashboard/ai/:id
   * - undefined : /dashboard/history/:id (legacy) — pathname 으로 자동 fallback
   */
  kind?: SimulationKind;
}

export default function SimulationHistoryDetail({
  kind: kindProp,
}: SimulationHistoryDetailProps = {}) {
  const { id: raw } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const id = raw ? Number(raw) : null;

  // kind: prop 우선 → 없으면 pathname 분기 → 그래도 없으면 null (legacy fallback)
  const kind: SimulationKind | null = useMemo(() => {
    if (kindProp) return kindProp;
    const p = location.pathname;
    if (p.startsWith('/dashboard/foresee/')) return 'foresee';
    if (p.startsWith('/dashboard/ai/')) return 'ai';
    return null;
  }, [kindProp, location.pathname]);

  const { data, isLoading, error, notFound } = useSimulationDetail(
    Number.isFinite(id) ? id : null,
    kind,
  );

  const pdfTemplateRef = useRef<HTMLDivElement>(null);
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);

  const pdfProps = data
    ? buildPdfPropsFromSimulation({
        simResult: data.simulation_result,
        businessType: data.business_type ?? null,
        savedHistoryId: data.id,
      })
    : null;

  const handleDownloadPDF = useCallback(async () => {
    if (!pdfTemplateRef.current || !data) return;
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
      const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      const districtName = data.district || '마포구';
      pdf.save(`SPOTTER_${districtName}_${formatDocumentId(data.id)}_${stamp}.pdf`);
    } catch (err) {
      console.error('[history detail] PDF export failed', err);
      window.alert('PDF 생성 중 오류가 발생했습니다. 콘솔을 확인해주세요.');
    } finally {
      setIsGeneratingPDF(false);
    }
  }, [data]);

  // HistoryCard에서 ?autopdf=1로 진입 시 자동 다운로드 (data 로드 후 1회)
  useEffect(() => {
    if (!data || isGeneratingPDF) return;
    if (searchParams.get('autopdf') !== '1') return;
    void handleDownloadPDF();
    // 1회 실행 후 파라미터 제거 (재실행 방지)
    const next = new URLSearchParams(searchParams);
    next.delete('autopdf');
    setSearchParams(next, { replace: true });
  }, [data, isGeneratingPDF, searchParams, setSearchParams, handleDownloadPDF]);

  if (!id || !Number.isFinite(id)) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-card text-sm text-danger">
        잘못된 경로입니다.
      </div>
    );
  }

  return (
    // relative z-10 — 글로벌 NetworkBackground (fixed inset-0 z-0 별자리 캔버스) 가
    // 페이지 위로 비치는 회귀 차단. dashboard outlet 과 동일 stacking 패턴.
    <div className="custom-scrollbar relative z-10 h-screen overflow-y-auto bg-background pb-16 text-foreground">
      <div className="mx-auto max-w-[1600px] px-6 pt-20">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-4 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          목록으로
        </button>

        {isLoading && (
          <div className="rounded-lg border border-dashed border-border bg-card/40 p-10 text-center text-sm text-muted-foreground">
            불러오는 중…
          </div>
        )}

        {error && !isLoading && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 p-6 text-center text-sm text-danger">
            {error}
            {notFound && (
              <div className="mt-2 text-xs text-muted-foreground">
                다른 매니저의 이력은 조회할 수 없습니다.
              </div>
            )}
          </div>
        )}

        {data && !isLoading && !error && (
          <>
            <DetailHeader
              id={data.id}
              clientName={data.client_name}
              brandName={data.brand_name}
              district={data.district}
              createdAt={data.created_at}
              kind={kind}
              onRerun={() => {
                // Phase 2 (2026-05-03) — saved 시뮬의 scenario(=원본 SimulationInput) 를
                // simulationStore.params 에 주입 후 /simulator 로 이동. SimulatorDashboard 의
                // initParams lazy useState 가 mount 시 store.params 에서 폼 자동 채움 (분석조건
                // drawer "조건 수정" 동선 동일 패턴).
                // intent='edit' state — App.tsx 의 auto-redirect (rawSimResult 있으면 dashboard
                // 로 다시 보내는 effect) skip. saved detail 본 후 새 시뮬 돌렸던 회귀 차단.
                // data.scenario 가 null (DB 컬럼 추가 전) 이면 빈 폼 fallback.
                const savedInput = (data.scenario as SimulationInput | null) ?? null;
                useSimulationStore.getState().dismissResult();
                if (savedInput) {
                  useSimulationStore.setState({ params: savedInput });
                }
                navigate('/simulator', { state: { intent: 'edit' } });
              }}
              onDownloadPDF={handleDownloadPDF}
              isGeneratingPDF={isGeneratingPDF}
            />
            <div className="mt-6">
              <HistoryDashboardView
                simResult={data.simulation_result}
                savedHistoryId={data.id}
                brandName={data.brand_name}
                businessType={data.business_type}
                kind={kind}
              />
            </div>
          </>
        )}

        {/* A4 PDF 템플릿 — 화면 밖 렌더, html2canvas 캡처용 */}
        {pdfProps && (
          <HiddenPDFTemplate
            ref={pdfTemplateRef}
            districtFull={pdfProps.districtFull}
            stats={pdfProps.stats}
            cannibalizationRows={pdfProps.cannibalizationRows}
            neighborhoodRows={pdfProps.neighborhoodRows}
            insights={pdfProps.insights}
            reportDate={pdfProps.reportDate}
            savedHistoryId={pdfProps.savedHistoryId}
            customerSegment={pdfProps.customerSegment}
          />
        )}
      </div>
    </div>
  );
}

interface DetailHeaderProps {
  id: number;
  clientName: string;
  brandName: string;
  district: string;
  createdAt: string;
  kind: SimulationKind | null;
  onRerun: () => void;
  onDownloadPDF: () => void;
  isGeneratingPDF: boolean;
}

function DetailHeader({
  id,
  clientName,
  brandName,
  district,
  createdAt,
  kind,
  onRerun,
  onDownloadPDF,
  isGeneratingPDF,
}: DetailHeaderProps) {
  const kindLabel = kind === 'foresee' ? 'ML 예측' : kind === 'ai' ? 'AI 분석' : null;
  const kindCls =
    kind === 'foresee'
      ? 'bg-primary/10 text-primary border-primary/40'
      : kind === 'ai'
        ? 'bg-chart-4/10 text-chart-4 border-chart-4/40'
        : '';
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-muted p-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-warning/15 px-2 py-0.5 text-xs font-mono font-bold text-warning">
            {formatDocumentId(id)}
          </span>
          {kindLabel && (
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[0.625rem] font-bold ${kindCls}`}
            >
              {kindLabel}
            </span>
          )}
          <span className="text-[0.625rem] uppercase tracking-widest text-muted-foreground">
            읽기 전용
          </span>
        </div>
        <h1 className="mt-2 text-xl font-semibold text-foreground">
          {clientName} 고객님 · {brandName} — {district}
        </h1>
        <div className="mt-1 font-mono text-xs text-muted-foreground">
          저장 {formatWhen(createdAt)}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onDownloadPDF}
          disabled={isGeneratingPDF}
          className="inline-flex items-center gap-2 rounded-md border border-primary/60 bg-primary/10 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isGeneratingPDF ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileDown className="h-4 w-4" />
          )}
          {isGeneratingPDF ? 'PDF 생성 중…' : 'PDF 다운로드'}
        </button>
        <button
          type="button"
          onClick={onRerun}
          className="inline-flex items-center gap-2 rounded-md bg-warning px-3 py-2 text-xs font-semibold text-warning-foreground hover:bg-warning"
        >
          <RotateCw className="h-4 w-4" />
          시뮬레이터로 이동
        </button>
      </div>
    </div>
  );
}
