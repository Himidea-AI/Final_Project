import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

function scoreColor(score: number): string {
  if (score >= 70) return 'text-emerald-400';
  if (score >= 40) return 'text-indigo-400';
  return 'text-rose-400';
}

// 백엔드가 동 코드 + 에러 메시지 ("11440545: 매출 데이터 부족...")를 narrative로 넘기는 경우 가림.
// 데이터 부족 안내는 UI 레벨 empty state로 처리.
function isRationaleUsable(text: string): boolean {
  if (!text) return false;
  if (/^\s*\d{8}\s*[:：]/.test(text)) return false; // 동 코드 + colon 시작
  if (/데이터\s*부족|분석\s*제한|수집\s*중/.test(text)) return false;
  return true;
}

export function Scorecard({ simResult }: Props) {
  const demo = simResult.demographic_report;
  const match = demo?.brand_target_match_score ?? null;
  const core = demo?.core_demographic;
  const rawRationale = demo?.match_rationale ?? demo?.narrative ?? '';
  const rationale = isRationaleUsable(rawRationale) ? rawRationale : '';
  const hasData = match != null || core != null || rationale.length > 0;

  const matchPct = match != null ? Math.round(match) : null;
  const matchColor = matchPct != null ? scoreColor(matchPct) : 'text-stone-400';

  if (!hasData) {
    return (
      <section>
        <SectionLabel label="SCORECARD" subtitle="브랜드 타겟 매칭 · 핵심 소비층" />
        <div className="rounded-lg border border-dashed border-stone-700 bg-stone-900/40 p-10 text-center">
          <div className="mx-auto mb-2 h-8 w-8 animate-pulse rounded-full bg-stone-700" />
          <div className="text-sm text-stone-400">데이터 수집 중</div>
          <div className="mt-1 text-xs text-stone-500">
            타겟 매칭 분석에 필요한 인구 샘플이 부족합니다
          </div>
        </div>
      </section>
    );
  }

  return (
    <section>
      <SectionLabel label="SCORECARD" subtitle="브랜드 타겟 매칭 · 핵심 소비층" />
      <div className="rounded-lg border border-stone-700 bg-stone-800 p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <div className="text-xs uppercase tracking-widest text-stone-400">브랜드 타겟 매칭</div>
            <div className={`mt-2 text-4xl font-bold ${matchColor}`}>
              {matchPct != null ? `${matchPct}` : '—'}
              <span className="ml-1 text-lg text-stone-500">/100</span>
            </div>
            {rationale && (
              <p className="mt-3 max-w-md text-sm leading-relaxed text-stone-300">
                {rationale.length > 200 ? `${rationale.slice(0, 200)}…` : rationale}
              </p>
            )}
          </div>

          {core && (
            <div className="min-w-[160px] rounded-md border border-stone-700 bg-stone-900/60 p-4">
              <div className="text-xs uppercase tracking-widest text-stone-400">핵심 소비층</div>
              <div className="mt-2 text-lg font-semibold text-stone-100">
                {core.age} · {core.gender}
              </div>
              {typeof core.share === 'number' && (
                <div className="mt-1 text-xs text-indigo-400">
                  점유 {(core.share * 100).toFixed(1)}%
                </div>
              )}
            </div>
          )}
        </div>

        {demo?.top_3_age_groups && demo.top_3_age_groups.length > 0 && (
          <div className="mt-6 border-t border-stone-700 pt-4">
            <div className="mb-2 text-xs uppercase tracking-widest text-stone-400">
              상위 3 연령대
            </div>
            <div className="flex flex-wrap gap-2">
              {demo.top_3_age_groups.map((g) => (
                <span
                  key={g.age_group}
                  className="rounded-md border border-stone-700 bg-stone-900/60 px-2.5 py-1 text-xs text-stone-300"
                >
                  {g.age_group}{' '}
                  <span className="text-stone-500">{(g.share * 100).toFixed(1)}%</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
