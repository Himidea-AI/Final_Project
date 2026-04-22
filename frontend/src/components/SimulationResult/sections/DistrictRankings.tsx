import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

const ZONING_CLS: Record<string, string> = {
  safe: 'text-emerald-400',
  caution: 'text-yellow-400',
  danger: 'text-rose-400',
};
const ZONING_KO: Record<string, string> = {
  safe: '안전',
  caution: '주의',
  danger: '위험',
};

export function DistrictRankings({ simResult }: Props) {
  const rankings = simResult.district_rankings ?? [];
  const winner = simResult.winner_district;

  if (rankings.length === 0) {
    return (
      <section>
        <SectionLabel label="DISTRICT RANKINGS" subtitle="마포 16동 입지 순위" />
        <div className="rounded-lg border border-stone-700 bg-stone-800 p-6 text-center text-sm text-stone-400">
          입지 랭킹 데이터가 없습니다
        </div>
      </section>
    );
  }

  return (
    <section>
      <SectionLabel label="DISTRICT RANKINGS" subtitle={`마포 ${rankings.length}동 입지 순위`} />
      <div className="overflow-x-auto rounded-lg border border-stone-700 bg-stone-800">
        <table className="w-full min-w-[640px]">
          <thead className="border-b border-stone-700 bg-stone-900/60">
            <tr>
              <th className="p-3 text-left text-xs font-semibold uppercase text-stone-400">순위</th>
              <th className="p-3 text-left text-xs font-semibold uppercase text-stone-400">
                행정동
              </th>
              <th className="p-3 text-right text-xs font-semibold uppercase text-stone-400">
                점수
              </th>
              <th className="p-3 text-right text-xs font-semibold uppercase text-stone-400">
                매출성장
              </th>
              <th className="p-3 text-right text-xs font-semibold uppercase text-stone-400">
                폐업위험
                <span className="ml-1 text-[9px] font-normal text-stone-600">(ML예측)</span>
              </th>
              <th className="p-3 text-right text-xs font-semibold uppercase text-stone-400">BEP</th>
              <th className="p-3 text-center text-xs font-semibold uppercase text-stone-400">
                용도지역
              </th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((r, i) => {
              const isWinner = r.district === winner;
              const rowCls = isWinner ? 'bg-indigo-500/10' : i < 3 ? 'bg-indigo-500/5' : '';
              return (
                <tr
                  key={r.district}
                  className={`border-b border-stone-700/50 last:border-b-0 ${rowCls}`}
                >
                  <td className="p-3 font-mono text-sm text-stone-100">{r.rank ?? i + 1}</td>
                  <td className="p-3 text-sm font-semibold text-stone-100">
                    {r.district}
                    {isWinner && (
                      <span className="ml-2 rounded bg-indigo-500/20 px-1.5 py-0.5 text-[10px] font-bold text-indigo-400">
                        추천
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-stone-100">
                    {r.score.toFixed(1)}
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-stone-300">
                    {(r.sales_growth * 100).toFixed(1)}%
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-rose-400">
                    {r.closure_rate != null ? `${(r.closure_rate * 100).toFixed(1)}%` : '—'}
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-stone-300">
                    {r.bep_months != null ? `${r.bep_months}개월` : '—'}
                  </td>
                  <td
                    className={`p-3 text-center text-xs font-semibold ${
                      ZONING_CLS[r.zoning_risk] ?? 'text-stone-400'
                    }`}
                  >
                    ● {ZONING_KO[r.zoning_risk] ?? r.zoning_risk}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
