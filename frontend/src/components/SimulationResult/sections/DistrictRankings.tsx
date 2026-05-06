import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

const ZONING_CLS: Record<string, string> = {
  safe: 'text-success',
  caution: 'text-warning',
  danger: 'text-danger',
};
const ZONING_KO: Record<string, string> = {
  safe: '안전',
  caution: '주의',
  danger: '위험',
};

export function DistrictRankings({ simResult }: Props) {
  const allRankings = simResult.district_rankings ?? [];
  const winner = simResult.winner_district;
  const selectedDongs = simResult.target_districts ?? [];
  // [/predict 분리 호출] 동별 예측 결과 — is_excluded_combo:true 동은 ML 출력 없음 (회색 + "예측 불가" 배지)
  const districtPredictions = simResult.district_predictions ?? [];

  // 사용자가 선택한 동(최대 4개)만 필터 + score 내림차순 + 자체 1~N위 재매김.
  // target_districts 비면 전체 표시 (안전 폴백).
  const rankings =
    selectedDongs.length > 0
      ? allRankings
          .filter((r) => selectedDongs.includes(r.district))
          .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      : allRankings;

  if (rankings.length === 0) {
    return (
      <section>
        <SectionLabel label="DISTRICT RANKINGS" subtitle="선택 동 입지 순위" />
        <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          입지 랭킹 데이터가 없습니다
        </div>
      </section>
    );
  }

  const subtitle =
    selectedDongs.length > 0
      ? `선택한 ${rankings.length}개 동 자체 순위`
      : `마포 ${rankings.length}동 입지 순위`;

  return (
    <section>
      <SectionLabel label="DISTRICT RANKINGS" subtitle={subtitle} />
      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full min-w-[640px]">
          <thead className="border-b border-border bg-muted">
            <tr>
              <th className="p-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                순위
              </th>
              <th className="p-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                행정동
              </th>
              <th className="p-3 text-right text-xs font-semibold uppercase text-muted-foreground">
                점수
              </th>
              <th className="p-3 text-right text-xs font-semibold uppercase text-muted-foreground">
                매출성장
              </th>
              <th className="p-3 text-center text-xs font-semibold uppercase text-muted-foreground">
                용도지역
              </th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((r, i) => {
              const isWinner = r.district === winner;
              // /predict 응답에서 동 매칭 — is_excluded_combo:true 면 ML 출력 없음
              const pred = districtPredictions.find((p) => p.district === r.district);
              const isExcluded = pred?.is_excluded_combo === true;
              const rowCls = isExcluded
                ? 'opacity-50 bg-muted'
                : isWinner
                  ? 'bg-primary/10'
                  : i < 3
                    ? 'bg-primary/5'
                    : '';
              return (
                <tr key={r.district} className={`border-b border-border last:border-b-0 ${rowCls}`}>
                  <td className="p-3 font-mono text-sm text-foreground">
                    {/* 자체 1~N위 (정렬 후 인덱스). */}
                    {i + 1}
                  </td>
                  <td className="p-3 text-sm font-semibold text-foreground">
                    {r.district}
                    {isExcluded && (
                      <span className="ml-2 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                        예측 불가
                      </span>
                    )}
                    {isWinner && !isExcluded && (
                      <span className="ml-2 rounded bg-primary/20 px-1.5 py-0.5 text-[0.625rem] font-bold text-primary">
                        추천
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-foreground">
                    {isExcluded ? '—' : r.score.toFixed(1)}
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-foreground">
                    {/* backend qoq_growth는 이미 percent 단위 (tools.py:300 *100 적용). 추가 ×100 금지 */}
                    {isExcluded ? '—' : `${r.sales_growth.toFixed(1)}%`}
                  </td>
                  <td
                    className={`p-3 text-center text-xs font-semibold ${
                      ZONING_CLS[r.zoning_risk] ?? 'text-muted-foreground'
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
