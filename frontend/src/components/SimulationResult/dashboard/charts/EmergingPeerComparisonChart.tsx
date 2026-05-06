/**
 * EmergingPeerComparisonChart — 페이지 상단 16동 분포 안 4동 위치 비교 차트.
 *
 * 입력: 4동 dpredicts (sortByRanking 정렬됨) + 첫 동의 peer_distribution (모두 동일 분포 가정).
 * 시각화: 사분위 P25/P50/P75/P90 vertical reference line + 4동 dot (SERIES_COLORS).
 *
 * 4동 외 12 동 score 는 backend 가 별도로 보내지 않음 (peer_distribution 은 quantile 만).
 * 따라서 본 차트는 "4동 위치 + 사분위 가이드" 형태.
 *
 * peer_distribution null 시 placeholder.
 */

import type { DistrictPredictionResult } from '../../../../types';
import { SERIES_COLORS } from '../../QuarterlyProjectionChart';

interface Props {
  /** sortByRanking 으로 winner→4위 정렬된 4 동 */
  dpredicts: DistrictPredictionResult[];
}

export function EmergingPeerComparisonChart({ dpredicts }: Props) {
  // 첫 emerging_signal 의 peer_distribution 사용 (4동 모두 같은 분포)
  const first = dpredicts.find((p) => p.emerging_signal?.peer_distribution);
  const peer = first?.emerging_signal?.peer_distribution;

  if (!peer) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-secondary p-6 text-center text-xs text-muted-foreground">
        16동 분포 데이터 미수신
      </div>
    );
  }

  // anomaly_score (0~1) → 0~100 % left
  const pct = (v: number) => Math.min(100, Math.max(0, v * 100));

  // 4동 score + 색 매핑 (SERIES_COLORS — winner→4위 순서)
  // 차트에서는 가독성 위해 score 오름차순 재정렬 (안정 → 변화 큼)
  const fourDongs = dpredicts
    .map((p, idx) => ({
      district: p.district,
      score: p.emerging_signal?.anomaly_score ?? 0,
      color: SERIES_COLORS[idx % SERIES_COLORS.length]!,
    }))
    .sort((a, b) => a.score - b.score);

  const quartiles: { v: number; label: string }[] = [
    { v: peer.p25, label: 'P25' },
    { v: peer.p50, label: 'P50' },
    { v: peer.p75, label: 'P75' },
    { v: peer.p90, label: 'P90' },
  ];

  return (
    <div className="space-y-3">
      {/* 사분위 라벨 row — 차트 위쪽 */}
      <div className="relative h-4">
        {quartiles.map(({ v, label }) => (
          <span
            key={label}
            className="absolute -top-0.5 -translate-x-1/2 text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground"
            style={{ left: `${pct(v)}%` }}
          >
            {label}
          </span>
        ))}
      </div>

      {/* 본 차트 — track + 사분위 vertical line + 4동 dot (y 분산 — 겹침 방지) */}
      <div className="relative h-14 w-full rounded-2xl bg-secondary">
        {quartiles.map(({ v, label }) => (
          <span
            key={label}
            aria-hidden
            className="absolute top-0 h-14 w-px bg-border"
            style={{ left: `${pct(v)}%` }}
          />
        ))}
        {fourDongs.map((d, i) => (
          <div
            key={d.district}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{
              left: `${pct(d.score)}%`,
              top: `${20 + i * 18}%`,
            }}
            title={`${d.district} · ${(d.score * 100).toFixed(0)}점`}
          >
            <span
              className="block h-3.5 w-3.5 rounded-full border-2 border-card"
              style={{ backgroundColor: d.color }}
            />
            <span className="absolute left-1/2 top-full mt-0.5 -translate-x-1/2 whitespace-nowrap text-[0.5625rem] font-bold text-foreground">
              {d.district}
            </span>
          </div>
        ))}
      </div>

      <div className="flex justify-between text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
        <span>안정 ────────</span>
        <span>──────── 평소와 다름</span>
      </div>
    </div>
  );
}
