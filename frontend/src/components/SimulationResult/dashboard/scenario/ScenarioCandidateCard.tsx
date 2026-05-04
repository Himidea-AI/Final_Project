/**
 * ScenarioCandidateCard — Master-Detail 좌측 후보 카드.
 *
 * 표시:
 *   - 동 × 업종 라벨
 *   - baseline 4분기 미니 sparkline (점포당 분기 매출)
 *   - 합계 = 점포당 연 매출
 *   - active ★
 *   - X 제거 버튼 (hover/focus 노출)
 */

import { Star, X } from 'lucide-react';
import type { ScenarioCandidate } from '../../../../hooks/useScenarioCandidates';

interface Props {
  candidate: ScenarioCandidate;
  active: boolean;
  baseline: number[] | null; // length 4 — 점포당 분기 매출(원). null = 로딩/에러.
  onClick: () => void;
  onRemove: () => void;
  loading?: boolean;
  error?: Error | null;
}

const formatKrw = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString('ko-KR')}만`;
  return `${Math.round(value).toLocaleString('ko-KR')}`;
};

function MiniSparkline({ values }: { values: number[] }) {
  if (values.length === 0) {
    return <div className="h-6 w-full rounded bg-secondary" aria-hidden="true" />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 64;
  const height = 22;
  const stepX = values.length > 1 ? width / (values.length - 1) : 0;
  const points = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="text-primary"
      aria-hidden="true"
    >
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

export function ScenarioCandidateCard({
  candidate,
  active,
  baseline,
  onClick,
  onRemove,
  loading = false,
  error = null,
}: Props) {
  const total = baseline ? baseline.reduce((sum, v) => sum + v, 0) : 0;

  const statusText = error
    ? '데이터 없음'
    : loading
      ? '불러오는 중'
      : baseline
        ? `연 ₩${formatKrw(total)}`
        : '—';

  const ariaLabel = `${candidate.dong} ${candidate.industry} 후보${active ? ', 선택됨' : ''}`;

  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={active}
      aria-label={ariaLabel}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      className={`group relative cursor-pointer rounded-2xl border p-3 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 ${
        active
          ? 'border-primary bg-primary/5 shadow-sm'
          : 'border-border bg-card hover:border-primary/50'
      }`}
    >
      {active && (
        <Star
          size={12}
          className="absolute right-2 top-2 fill-primary text-primary"
          aria-hidden="true"
        />
      )}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        aria-label={`${candidate.dong} ${candidate.industry} 후보 제거`}
        className="absolute right-2 top-7 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-danger focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-danger group-hover:opacity-100"
      >
        <X size={12} />
      </button>

      <div className="space-y-1.5 pr-5">
        <div className="text-xs font-black tracking-tight text-foreground">{candidate.dong}</div>
        <div className="text-[0.625rem] font-bold uppercase tracking-widest text-muted-foreground">
          {candidate.industry}
        </div>
      </div>

      <div className="mt-2 flex items-end justify-between gap-2">
        <div className="text-[0.625rem] font-bold tabular-nums text-muted-foreground">
          {statusText}
        </div>
        {baseline && !loading && !error ? (
          <MiniSparkline values={baseline} />
        ) : (
          <div className="h-[22px] w-16 rounded bg-secondary" aria-hidden="true" />
        )}
      </div>
    </div>
  );
}
