import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

type Verdict = 'GO' | 'HOLD' | 'NO';

// 다크 기본 톤 / 인쇄 시 화이트로 전환 (print:*) — Tailwind print variants
const VERDICT_DARK: Record<Verdict, string> = {
  GO: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  HOLD: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/40',
  NO: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
};

const VERDICT_PRINT: Record<Verdict, string> = {
  GO: 'print:bg-emerald-100 print:text-emerald-800 print:border-emerald-300',
  HOLD: 'print:bg-yellow-100 print:text-yellow-800 print:border-yellow-300',
  NO: 'print:bg-rose-100 print:text-rose-800 print:border-rose-300',
};

function deriveVerdict(simResult: SimulationOutput): Verdict {
  const legal = simResult.overall_legal_risk;
  if (legal === 'danger') return 'NO';
  if (legal === 'caution') return 'HOLD';

  const grade = simResult.analysis_metrics?.district_grade;
  if (grade === 'RISKY') return 'HOLD';

  return 'GO';
}

export function DecisionMemo({ simResult }: Props) {
  const verdict = deriveVerdict(simResult);
  const district = simResult.winner_district ?? simResult.target_district ?? '—';
  const rationale =
    (simResult.ai_recommendation ?? simResult.analysis_report ?? '').slice(0, 400) || '—';

  const compIntel = simResult.competitor_intel as Record<string, any> | null | undefined;
  const actions = (compIntel?.recommended_actions ?? []) as string[];

  return (
    <section>
      <SectionLabel label="DECISION MEMO" subtitle="본사 보고용 요약 (인쇄 가능)" />
      <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-8 text-zinc-100 print:border-zinc-300 print:bg-zinc-50 print:text-zinc-900 print:shadow-none">
        <div
          className={`mb-4 inline-flex items-center rounded-full border px-4 py-1 text-xl font-bold ${VERDICT_DARK[verdict]} ${VERDICT_PRINT[verdict]}`}
        >
          {verdict}
        </div>
        <h3 className="mb-6 text-2xl font-semibold">
          {district}{' '}
          <span className="text-base font-normal text-zinc-400 print:text-zinc-500">
            입지 의사결정
          </span>
        </h3>
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-widest text-zinc-400 print:text-zinc-600">
              근거
            </h4>
            <p className="whitespace-pre-line text-sm leading-relaxed text-zinc-300 print:text-zinc-700">
              {rationale}
            </p>
          </div>
          <div>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-widest text-zinc-400 print:text-zinc-600">
              다음 액션
            </h4>
            {actions.length > 0 ? (
              <ul className="space-y-1 text-sm text-zinc-300 print:text-zinc-700">
                {actions.slice(0, 5).map((a, i) => (
                  <li key={i}>• {a}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-zinc-500">추가 액션 데이터 없음 (본사 영업팀 후속 협의)</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
