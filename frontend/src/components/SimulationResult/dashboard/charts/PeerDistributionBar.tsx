/**
 * PeerDistributionBar — 카드 안 mini bar.
 * 16 동 anomaly_score 분포에서 본 동의 위치를 horizontal bar + dot 으로 시각화.
 *
 * 입력: peer_distribution (사분위 + rank) + ownScore (본 동) + seriesColor.
 * 출력: 좌(min=0) ─ 우(max=1) horizontal track + p25/p50/p75 사분위 tick +
 *       p90 강조 + 본 동 dot (seriesColor) + "N위 (상위 X%)" 라벨.
 */

import type { EmergingSignal } from '../../../../types';

interface Props {
  peerDistribution: NonNullable<EmergingSignal['peer_distribution']>;
  ownScore: number;
  seriesColor: string;
}

export function PeerDistributionBar({ peerDistribution, ownScore, seriesColor }: Props) {
  // anomaly_score 0~1 → 0~100 % left 좌표
  const pct = (v: number) => Math.min(100, Math.max(0, v * 100));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
        <span>16동 분포</span>
        <span>
          변화 {peerDistribution.rank_in_total}위 / {peerDistribution.total}동
        </span>
      </div>
      <div className="relative h-2 w-full rounded-full bg-secondary overflow-visible">
        {/* 사분위 tick (p25 / p50 / p75) — 얇은 vertical 라인 */}
        {[peerDistribution.p25, peerDistribution.p50, peerDistribution.p75].map((q, i) => (
          <span
            key={i}
            aria-hidden
            className="absolute top-0 h-2 w-px bg-border"
            style={{ left: `${pct(q)}%` }}
          />
        ))}
        {/* p90 강조 tick — 굵고 길게 */}
        <span
          aria-hidden
          className="absolute -top-0.5 h-3 w-0.5 bg-muted-foreground/60"
          style={{ left: `${pct(peerDistribution.p90)}%` }}
        />
        {/* 본 동 dot (seriesColor) */}
        <span
          aria-hidden
          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 border-card"
          style={{
            left: `${pct(ownScore)}%`,
            backgroundColor: seriesColor,
          }}
        />
      </div>
      <div className="flex justify-between text-[0.5rem] tabular-nums text-muted-foreground/70">
        <span>0</span>
        <span>0.5</span>
        <span>1.0</span>
      </div>
    </div>
  );
}
