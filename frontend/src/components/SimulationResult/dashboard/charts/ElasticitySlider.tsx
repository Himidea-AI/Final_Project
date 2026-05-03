/**
 * ElasticitySlider — TCN 시나리오 시뮬레이터 슬라이더 (단일 피처).
 *
 * - native <input type="range"> a11y 보장 (-30 ~ +30, step 10)
 * - Tailwind accent-primary 로 deep blue 토큰 적용
 * - 현재 elasticity 값 칩 (양수=success, 음수=danger)
 * - peer correlation 안내는 인라인 회색 텍스트 (|r|≥0.5 필터는 parent 책임)
 */

import type { ElasticityFeature } from '../../../../types/elasticity';
import { FEATURE_LABELS } from '../sub/predict/PredictScenarioSimTab';

interface PeerCorrelation {
  peer: ElasticityFeature;
  r: number;
}

interface Props {
  feature: ElasticityFeature;
  label: string;
  value: number; // -30 ~ +30 (step 10)
  onChange: (next: number) => void;
  elasticity: Record<string, number>;
  peerCorrelations: PeerCorrelation[];
}

const elasticityKey = (v: number): string => (v > 0 ? `+${v}` : String(v));

const formatPct = (v: number): string => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

export function ElasticitySlider({
  feature,
  label,
  value,
  onChange,
  elasticity,
  peerCorrelations,
}: Props) {
  const currentDelta = elasticity[elasticityKey(value)] ?? elasticity[String(value)] ?? 0;
  const deltaTone =
    currentDelta > 0
      ? 'border-success/30 bg-success/10 text-success'
      : currentDelta < 0
        ? 'border-danger/30 bg-danger/10 text-danger'
        : 'border-border bg-secondary text-muted-foreground';

  const valueLabel = `${value > 0 ? '+' : ''}${value}%`;
  const ariaLabel = `${label} 슬라이더, 현재 ${valueLabel} 변동, 매출 변화 ${formatPct(currentDelta)}`;

  return (
    <div className="space-y-2 rounded-2xl border border-border bg-secondary/40 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black text-foreground tracking-tight">{label}</span>
          <span
            className={`rounded-full border px-2 py-0.5 text-[0.625rem] font-black tabular-nums ${deltaTone}`}
            title="이 피처가 현재 슬라이더 위치에서 매출에 주는 영향"
          >
            {formatPct(currentDelta)}
          </span>
        </div>
        <span className="text-xs font-black text-primary tabular-nums">{valueLabel}</span>
      </div>

      <input
        type="range"
        min={-30}
        max={30}
        step={10}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={ariaLabel}
        aria-valuemin={-30}
        aria-valuemax={30}
        aria-valuenow={value}
        aria-valuetext={`${valueLabel}, 매출 변화 ${formatPct(currentDelta)}`}
        className="w-full accent-primary cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 rounded"
      />

      <div className="flex justify-between text-[0.5625rem] font-bold text-muted-foreground tabular-nums">
        <span>-30%</span>
        <span>-20</span>
        <span>-10</span>
        <span>0</span>
        <span>+10</span>
        <span>+20</span>
        <span>+30%</span>
      </div>

      {peerCorrelations.length > 0 && (
        <div className="mt-1.5 space-y-0.5">
          {peerCorrelations.map(({ peer, r }) => {
            const peerLabel = FEATURE_LABELS[peer];
            const sign = r > 0 ? '양' : '음';
            const action = r > 0 ? '함께 조정해보세요' : '반대로 조정해보세요';
            return (
              <p
                key={`${feature}-${peer}`}
                className="text-xs text-muted-foreground leading-relaxed"
              >
                💡 {peerLabel}와 {sign}의 상관 {r.toFixed(2)} — {action}
              </p>
            );
          })}
        </div>
      )}
    </div>
  );
}
