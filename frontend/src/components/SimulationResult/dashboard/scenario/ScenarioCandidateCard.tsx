/**
 * ScenarioCandidateCard — Master-Detail 좌측 후보 카드.
 *
 * 표시:
 *   - 동 dropdown (시뮬 입력 4동 한정) × 업종 텍스트
 *   - baseline 4분기 미니 sparkline (점포당 분기 매출)
 *   - 합계 = 점포당 연 매출
 *   - active ★
 *   - X 제거 버튼 (hover/focus 노출 / 후보 1개만 남으면 disabled)
 */

import { Star, X } from 'lucide-react';
import type { ScenarioCandidate } from '../../../../hooks/useScenarioCandidates';

interface Props {
  candidate: ScenarioCandidate;
  active: boolean;
  baseline: number[] | null; // length 4 — 점포당 분기 매출(원). null = 로딩/에러.
  /** 시뮬 입력 동 list (4동 한정). dropdown 옵션 source. */
  availableDongs: { name: string; code: string }[];
  /** 동 변경 콜백. dup 시 false 반환. */
  onChangeDong: (id: string, dong: string, dongCode: string) => boolean;
  /** 후보 1개만 남았을 때 삭제 버튼 disabled (UX 가드). */
  removeDisabled?: boolean;
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
  availableDongs,
  onChangeDong,
  removeDisabled = false,
  onClick,
  onRemove,
  loading = false,
  error = null,
}: Props) {
  const total = baseline ? baseline.reduce((sum, v) => sum + v, 0) : 0;
  const dongSelectDisabled = availableDongs.length === 0;
  // 후보의 현재 동이 availableDongs 안에 없으면 (sessionStorage 잔존 등) — 옵션에 강제 포함
  // 시켜 React controlled select 경고 방지. 사용자가 다른 동 선택 시 정상 변경.
  const dongInList = availableDongs.some((d) => d.name === candidate.dong);
  const renderedOptions: { name: string; code: string }[] = dongInList
    ? availableDongs
    : [{ name: candidate.dong, code: candidate.dongCode }, ...availableDongs];

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
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        aria-label={`${candidate.dong} ${candidate.industry} 후보 제거`}
        disabled={removeDisabled}
        className="absolute right-2 top-2 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-danger focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-danger group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-0 disabled:hover:text-muted-foreground"
      >
        <X size={12} />
      </button>

      <div className="flex items-center gap-2 pr-5">
        <select
          value={candidate.dong}
          onChange={(e) => {
            const next = availableDongs.find((d) => d.name === e.target.value);
            if (!next) return;
            onChangeDong(candidate.id, next.name, next.code);
          }}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          disabled={dongSelectDisabled}
          aria-label="동 선택"
          className="rounded-md border border-border bg-card px-2 py-1 text-xs font-bold text-foreground transition-colors hover:border-primary/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          {renderedOptions.map((d) => (
            <option key={d.code} value={d.name}>
              {d.name}
            </option>
          ))}
        </select>
        <span className="text-[0.625rem] text-muted-foreground">×</span>
        <span className="truncate text-[0.625rem] font-bold uppercase tracking-widest text-muted-foreground">
          {candidate.industry}
        </span>
        {active && (
          <Star size={12} className="ml-auto fill-primary text-primary" aria-hidden="true" />
        )}
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
