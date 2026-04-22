import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, RotateCw } from 'lucide-react';
import { useSimulationDetail } from '../hooks/useSimulationDetail';
import { IntegratedReport } from '../components/SimulationResult/IntegratedReport';
import { formatDocumentId } from '../types/simulationHistory';

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
  const id = raw ? Number(raw) : null;
  const { data, isLoading, error, notFound } = useSimulationDetail(Number.isFinite(id) ? id : null);

  if (!id || !Number.isFinite(id)) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-[#1e1b18] text-sm text-rose-400">
        잘못된 경로입니다.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#1e1b18] pb-16 text-stone-100">
      <div className="mx-auto max-w-7xl px-6 pt-20">
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
            />
            <div className="mt-6">
              <IntegratedReport
                simResult={data.simulation_result}
                onExportPdf={() => {
                  // 상세 뷰는 읽기 전용 — PDF 내보내기는 원 화면에서 이미 가능하므로 안내.
                  window.alert(
                    '이 페이지는 읽기 전용입니다. PDF 다운로드는 시뮬레이터 화면에서 이용해주세요.',
                  );
                }}
                onExportXlsx={() => {
                  window.alert(
                    '이 페이지는 읽기 전용입니다. XLSX 다운로드는 시뮬레이터 화면에서 이용해주세요.',
                  );
                }}
                compareMode={false}
                onToggleCompare={() => {}}
              />
            </div>
          </>
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
}

function DetailHeader({
  id,
  clientName,
  brandName,
  district,
  createdAt,
  onRerun,
}: DetailHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-stone-700 bg-stone-800 p-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-indigo-500/15 px-2 py-0.5 text-xs font-mono font-bold text-indigo-400">
            {formatDocumentId(id)}
          </span>
          <span className="text-[10px] uppercase tracking-widest text-stone-500">읽기 전용</span>
        </div>
        <h1 className="mt-2 text-xl font-semibold text-stone-100">
          {clientName} 고객님 · {brandName} — {district}
        </h1>
        <div className="mt-1 font-mono text-xs text-stone-500">저장 {formatWhen(createdAt)}</div>
      </div>
      <button
        type="button"
        onClick={onRerun}
        className="inline-flex items-center gap-2 rounded-md bg-indigo-500 px-3 py-2 text-xs font-semibold text-stone-900 hover:bg-indigo-400"
      >
        <RotateCw className="h-4 w-4" />
        시뮬레이터로 이동
      </button>
    </div>
  );
}
