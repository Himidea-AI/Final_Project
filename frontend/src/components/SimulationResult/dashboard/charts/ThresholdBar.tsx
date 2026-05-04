/**
 * ThresholdBar — 임계값 구간이 있는 지표를 가로 척도 + 현재 위치 마커로 시각화.
 *
 * 사용 예 (HHI):
 *   <ThresholdBar
 *     value={9050}
 *     min={0}
 *     max={10000}
 *     segments={HHI_SEGMENTS}
 *     valueFormat={(v) => v.toLocaleString('ko-KR')}
 *     sourceText="DOJ/FTC Horizontal Merger Guidelines (2010)"
 *   />
 *
 * 디자인 원칙 (셀 변경안 PDF + 사용자 피드백):
 *   - 색상은 위험 구간만 강조 (빨/주황), 안전 구간은 채도 낮게.
 *   - 마커 위치 = 현재 값의 백분위 (min/max 비례).
 *   - 출처(sourceText)는 임계값 신뢰도를 위해 작게 노출.
 *
 * Tailwind purge 호환: 색은 동적 concat 금지 → 명시적 클래스 매핑 사용.
 */

interface Segment {
  label: string;
  /** 이 구간의 상한값 (포함). 마지막 segment 의 max 는 전체 차트의 max 와 같아야 함. */
  max: number;
  /** Tailwind 색 토큰 키 (emerald / lime / amber / orange / rose) */
  color: 'emerald' | 'lime' | 'amber' | 'orange' | 'rose';
}

interface Props {
  value: number;
  min?: number;
  max: number;
  segments: ReadonlyArray<Segment>;
  /** 값 포맷터. 기본: toLocaleString. */
  valueFormat?: (v: number) => string;
  /** 임계값 출처 (작게 ⓘ 와 함께 노출). */
  sourceText?: string;
  /** 추가 한 줄 해석 — 마커 아래 노출. */
  caption?: string;
}

const FILL_BG: Record<Segment['color'], string> = {
  emerald: 'bg-emerald-500/30',
  lime: 'bg-lime-500/30',
  amber: 'bg-amber-500/35',
  orange: 'bg-orange-500/45',
  rose: 'bg-rose-500/55',
};

const TEXT_COLOR: Record<Segment['color'], string> = {
  emerald: 'text-emerald-500',
  lime: 'text-lime-500',
  amber: 'text-amber-500',
  orange: 'text-orange-500',
  rose: 'text-rose-500',
};

function findSegment(value: number, segments: ReadonlyArray<Segment>): Segment {
  for (const seg of segments) {
    if (value < seg.max) return seg;
  }
  return segments[segments.length - 1];
}

export function ThresholdBar({
  value,
  min = 0,
  max,
  segments,
  valueFormat = (v) => v.toLocaleString('ko-KR'),
  sourceText,
  caption,
}: Props) {
  const span = Math.max(1, max - min);
  // 마커 위치 = 현재 값의 백분위 (clamp [0, 100]).
  const markerPct = Math.min(100, Math.max(0, ((value - min) / span) * 100));
  const currentSeg = findSegment(value, segments);

  // 각 segment 의 너비 = (이 max - 직전 max) / 전체 span
  let prev = min;
  const widths = segments.map((seg) => {
    const w = ((seg.max - prev) / span) * 100;
    prev = seg.max;
    return w;
  });

  return (
    <div className="w-full">
      {/* 막대: 색 segment 들 + 위에 마커.
          마커가 끝(0%/100%) 가까이일 때 overflow-hidden 으로 잘리지 않게,
          색 막대만 overflow-hidden 으로 둥글게 자르고 마커는 별도 absolute 레이어. */}
      <div className="relative h-3.5 w-full">
        <div className="absolute left-0 right-0 top-1/2 flex h-2.5 -translate-y-1/2 overflow-hidden rounded-full bg-card">
          {segments.map((seg, i) => (
            <div
              key={`${seg.label}-${i}`}
              className={`h-full ${FILL_BG[seg.color]}`}
              style={{ width: `${widths[i]}%` }}
              aria-label={`${seg.label} 구간`}
            />
          ))}
        </div>
        {/* 현재 위치 마커 — 흰 점 + 색 테두리. 막대 위 별도 레이어라 끝에서도 안 잘림. */}
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-foreground bg-card shadow"
          style={{ left: `${markerPct}%` }}
          aria-label={`현재 값 ${valueFormat(value)}`}
        />
      </div>

      {/* 임계값 라벨 — segment 경계 텍스트 */}
      <div className="mt-1.5 flex justify-between text-[0.625rem] tabular-nums text-muted-foreground">
        <span>{valueFormat(min)}</span>
        {segments.slice(0, -1).map((seg, i) => (
          <span key={`th-${i}`}>{valueFormat(seg.max)}</span>
        ))}
        <span>{valueFormat(max)}</span>
      </div>

      {/* 라벨 줄 — 각 segment 명 */}
      <div className="mt-0.5 flex w-full text-[0.625rem] font-bold uppercase">
        {segments.map((seg, i) => (
          <span
            key={`lb-${seg.label}-${i}`}
            className={`text-center ${seg === currentSeg ? TEXT_COLOR[seg.color] : 'text-muted-foreground/60'}`}
            style={{ width: `${widths[i]}%` }}
          >
            {seg.label}
          </span>
        ))}
      </div>

      {caption && <div className="mt-2 text-xs text-muted-foreground">{caption}</div>}

      {sourceText && (
        <div className="mt-1 text-[0.625rem] text-muted-foreground/70">
          <span aria-hidden>ⓘ </span>
          {sourceText}
        </div>
      )}
    </div>
  );
}
