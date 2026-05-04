/**
 * ClosureRiskHeatmap — 4동 폐업 위험도 SHAP 기여 피처 비교 (heatmap)
 *
 * 행 = 피처 (4동의 top SHAP signals 합집합), 열 = 동.
 * 셀 색 = contribution 부호와 강도 (양수: 빨강 위험↑, 음수: 초록 위험↓, alpha = |c| / max|c|)
 * 셀 텍스트 = `+0.045` 형식의 contribution 값. 데이터 없는 셀 = "—"
 *
 * LightGBM 과 TCN 두 모델은 별도 heatmap 으로 분리 표시 — 입력 공간이 다름 (15 vs 34 피처).
 */

import type { ClosureRisk, ClosureRiskSignal } from '../../../../types';
import { SERIES_COLORS } from '../../QuarterlyProjectionChart';
import { shapStrengthLabel } from '../utils/formatters';

interface DistrictRiskRow {
  district: string;
  closure: ClosureRisk | null | undefined;
}

interface Props {
  rows: DistrictRiskRow[];
}

type Source = 'lgbm' | 'tcn';

interface FeatureRow {
  feature_key: string;
  feature_label: string;
  /** district name → contribution (없으면 undefined) */
  byDistrict: Record<string, number>;
}

function collectFeatureRows(rows: DistrictRiskRow[], source: Source): FeatureRow[] {
  const map = new Map<string, FeatureRow>();
  for (const r of rows) {
    const signals: ClosureRiskSignal[] =
      (source === 'lgbm' ? r.closure?.top_signals_lgbm : r.closure?.top_signals_tcn) ?? [];
    for (const sig of signals) {
      const key = sig.feature_key ?? sig.feature;
      if (!key) continue;
      let row = map.get(key);
      if (!row) {
        row = {
          feature_key: key,
          feature_label: sig.feature ?? key,
          byDistrict: {},
        };
        map.set(key, row);
      }
      row.byDistrict[r.district] = sig.contribution;
    }
  }
  // 기여도 합 절댓값 큰 순 정렬 — 위험 결정력 큰 피처 위로
  return Array.from(map.values()).sort((a, b) => {
    const sumA = Object.values(a.byDistrict).reduce((s, v) => s + Math.abs(v), 0);
    const sumB = Object.values(b.byDistrict).reduce((s, v) => s + Math.abs(v), 0);
    return sumB - sumA;
  });
}

function HeatmapTable({
  title,
  features,
  rows,
}: {
  title: string;
  features: FeatureRow[];
  rows: DistrictRiskRow[];
}) {
  if (features.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-secondary p-6 text-center text-xs text-muted-foreground">
        {title} 데이터 없음
      </div>
    );
  }

  // 셀 색 강도 정규화 — 모든 셀 절댓값의 최대 기준
  const maxAbs = Math.max(
    ...features.flatMap((f) => Object.values(f.byDistrict).map((v) => Math.abs(v))),
    0.0001,
  );

  return (
    <div className="rounded-2xl border border-border bg-secondary p-6">
      <div className="mb-3 flex items-center justify-between">
        <h5 className="text-[0.6875rem] font-bold uppercase tracking-widest text-foreground">
          {title}
        </h5>
        <div className="flex items-center gap-3 text-[0.5625rem] font-bold uppercase tracking-widest text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-danger" />
            위험 ↑
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-success" />
            위험 ↓
          </span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[0.6875rem]">
          <thead>
            <tr>
              <th className="sticky left-0 bg-secondary px-3 py-2 text-left font-bold text-muted-foreground">
                피처
              </th>
              {rows.map((r, idx) => (
                <th
                  key={r.district}
                  className="min-w-[88px] px-2 py-2 text-center font-bold text-foreground"
                >
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: SERIES_COLORS[idx % SERIES_COLORS.length] }}
                    />
                    {r.district}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {features.map((f) => (
              <tr key={f.feature_key} className="border-t border-border/60">
                <td className="sticky left-0 bg-secondary px-3 py-2 text-left font-medium text-foreground">
                  {f.feature_label}
                </td>
                {rows.map((r) => {
                  const c = f.byDistrict[r.district];
                  if (c == null || c === 0) {
                    return (
                      <td
                        key={r.district}
                        className="px-2 py-2 text-center text-muted-foreground/60 tabular-nums"
                      >
                        —
                      </td>
                    );
                  }
                  const alpha = Math.min(1, Math.abs(c) / maxAbs);
                  const color = c > 0 ? 'var(--danger)' : 'var(--success)';
                  const sign = c > 0 ? '+' : '';
                  // 셀 텍스트는 "↑ 강 / ↑ 중 / ↑ 약" 등급 표기. 원시 SHAP 값은 hover tooltip 으로 보존.
                  // 임계값(0.02 / 0.05) 은 utils/formatters.ts shapStrength() 정의 단일소스.
                  return (
                    <td
                      key={r.district}
                      className="px-2 py-2 text-center font-bold text-foreground"
                      style={{
                        backgroundColor: `color-mix(in srgb, ${color} ${Math.round(alpha * 60)}%, transparent)`,
                      }}
                      title={`${f.feature_label}: ${sign}${c.toFixed(4)} (${c > 0 ? '위험 증가' : '위험 감소'} 방향, 원시 SHAP 값)`}
                    >
                      {shapStrengthLabel(c)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ClosureRiskHeatmap({ rows }: Props) {
  const lgbmFeatures = collectFeatureRows(rows, 'lgbm');
  const tcnFeatures = collectFeatureRows(rows, 'tcn');

  // 둘 다 빈 경우 — placeholder
  if (lgbmFeatures.length === 0 && tcnFeatures.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-secondary p-8 text-center text-xs text-muted-foreground">
        SHAP 기여 피처 데이터 없음 — LightGBM / TCN 모델 결과 대기
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <HeatmapTable
        title="LightGBM · 과거 패턴 기반 기여 피처"
        features={lgbmFeatures}
        rows={rows}
      />
      <HeatmapTable title="TCN · 시계열 흐름 기반 기여 피처" features={tcnFeatures} rows={rows} />
      <p className="text-[0.625rem] text-muted-foreground leading-relaxed mt-3">
        셀 색강도 = 해당 피처가 폐업 위험에 기여한 정도 (양수 빨강 = 위험↑, 음수 초록 = 위험↓).
        |값|/최대|값| × 60% 알파.
      </p>
    </div>
  );
}
