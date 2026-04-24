import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, FileDown, Loader2, RotateCw } from 'lucide-react';
import { useSimulationDetail } from '../hooks/useSimulationDetail';
import { TabbedDashboard } from '../components/SimulationResult/dashboard/TabbedDashboard';
import { formatDocumentId } from '../types/simulationHistory';
import { HiddenPDFTemplate } from '../App';
import { buildPdfPropsFromSimulation } from '../utils/pdfPropsBuilder';

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ko-KR', { hour12: false });
  } catch {
    return iso;
  }
}

export default function SimulationHistoryDetail() {
  const { id: raw } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const id = raw ? Number(raw) : null;
  const { data, isLoading, error, notFound } = useSimulationDetail(Number.isFinite(id) ? id : null);

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
      <div className="flex min-h-[60vh] items-center justify-center bg-[#1e1b18] text-sm text-rose-400">
        잘못된 경로입니다.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0C0B0A] pb-16 text-stone-100">
      <div className="mx-auto max-w-[1600px] px-6 pt-20">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-4 inline-flex items-center gap-1 text-xs text-stone-400 hover:text-stone-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          목록으로
        </button>

        {isLoading && (
          <div className="rounded-lg border border-dashed border-stone-700 bg-stone-900/40 p-10 text-center text-sm text-stone-500">
            불러오는 중…
          </div>
        )}

        {error && !isLoading && (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-6 text-center text-sm text-rose-300">
            {error}
            {notFound && (
              <div className="mt-2 text-xs text-stone-500">
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
              onRerun={() => {
                // Phase 1: SimulatorDashboard가 별도 state로 payload 받는 경로가 없어
                // 우선 시뮬레이터로 이동. Phase 2에서 sessionStorage 경유 재실행 자동 주입.
                navigate('/simulator');
              }}
              onDownloadPDF={handleDownloadPDF}
              isGeneratingPDF={isGeneratingPDF}
            />
            <div className="mt-6">
              <TabbedDashboard
                simResult={data.simulation_result}
                savedHistoryId={data.id}
                brandName={data.brand_name}
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
  onRerun,
  onDownloadPDF,
  isGeneratingPDF,
}: DetailHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-stone-700 bg-stone-800 p-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs font-mono font-bold text-amber-400">
            {formatDocumentId(id)}
          </span>
          <span className="text-[10px] uppercase tracking-widest text-stone-500">읽기 전용</span>
        </div>
        <h1 className="mt-2 text-xl font-semibold text-stone-100">
          {clientName} 고객님 · {brandName} — {district}
        </h1>
        <div className="mt-1 font-mono text-xs text-stone-500">저장 {formatWhen(createdAt)}</div>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onDownloadPDF}
          disabled={isGeneratingPDF}
          className="inline-flex items-center gap-2 rounded-md border border-indigo-500/60 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/20 disabled:cursor-not-allowed disabled:opacity-60"
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
          className="inline-flex items-center gap-2 rounded-md bg-amber-500 px-3 py-2 text-xs font-semibold text-stone-900 hover:bg-amber-400"
        >
          <RotateCw className="h-4 w-4" />
          시뮬레이터로 이동
        </button>
      </div>
    </div>
  );
}
