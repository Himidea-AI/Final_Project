/**
 * CorrelationInsightCard — 슬라이더 페어 상관관계 정보 카드 (자동 연동 X).
 *
 * 명세서 §4.5:
 *   - 슬라이더 페어 상관관계 (Pearson r, -1~1)
 *   - |r| ≥ 0.5 강한 상관만 노출
 *   - parseCorrelationKey() — "vacancy_rate__cpi_index" / "vac↔cpi" / "vacancy_rate→cpi_index"
 *     세 패턴 모두 매칭 (백엔드 schema 변형 대응)
 *   - 정보 표시만, 슬라이더 자동 연동 안 함
 */

import { Info } from 'lucide-react';
import { SLIDER_LABELS, type PctSliderKey } from '../../../../types/elasticity';

interface Props {
  correlations: Record<string, number>;
}

const PCT_KEYS: ReadonlyArray<PctSliderKey> = [
  'vacancy_rate',
  'trend_score',
  'cpi_index',
  'opr_sale_mt_avg',
];

const SHORT_TO_FULL: Record<string, PctSliderKey> = {
  vac: 'vacancy_rate',
  vacancy: 'vacancy_rate',
  trend: 'trend_score',
  trd: 'trend_score',
  cpi: 'cpi_index',
  opr: 'opr_sale_mt_avg',
  sale: 'opr_sale_mt_avg',
};

function isPctKey(k: string): k is PctSliderKey {
  return (PCT_KEYS as readonly string[]).includes(k);
}

function normalizeToken(tok: string): PctSliderKey | null {
  const t = tok.trim().toLowerCase();
  if (isPctKey(t)) return t as PctSliderKey;
  if (SHORT_TO_FULL[t]) return SHORT_TO_FULL[t];
  return null;
}

/** 다양한 separator 패턴 분해 — "↔" / "__" / "→" 모두 처리. */
export function parseCorrelationKey(key: string): { a: PctSliderKey; b: PctSliderKey } | null {
  const seps = ['↔', '__', '→', '_↔_'];
  for (const sep of seps) {
    if (key.includes(sep)) {
      const [rawA, rawB] = key.split(sep);
      const a = rawA ? normalizeToken(rawA) : null;
      const b = rawB ? normalizeToken(rawB) : null;
      if (a && b && a !== b) return { a, b };
    }
  }
  return null;
}

interface DisplayPair {
  a: PctSliderKey;
  b: PctSliderKey;
  r: number;
}

export function CorrelationInsightCard({ correlations }: Props) {
  // dedupe by unordered pair set; pick max |r|
  const dedup = new Map<string, DisplayPair>();
  for (const [k, v] of Object.entries(correlations)) {
    if (typeof v !== 'number' || !Number.isFinite(v)) continue;
    const parsed = parseCorrelationKey(k);
    if (!parsed) continue;
    const ordered = [parsed.a, parsed.b].sort();
    const sigKey = `${ordered[0]}|${ordered[1]}`;
    const prev = dedup.get(sigKey);
    if (!prev || Math.abs(v) > Math.abs(prev.r)) {
      dedup.set(sigKey, { a: ordered[0] as PctSliderKey, b: ordered[1] as PctSliderKey, r: v });
    }
  }

  const strong = Array.from(dedup.values())
    .filter((p) => Math.abs(p.r) >= 0.5)
    .sort((x, y) => Math.abs(y.r) - Math.abs(x.r));

  if (strong.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-secondary/40 p-4">
        <div className="flex items-center gap-1.5 text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
          <Info size={12} aria-hidden="true" /> 변수 간 상관관계
        </div>
        <p className="mt-1.5 text-[0.6875rem] text-muted-foreground">
          강한 상관관계(|r| ≥ 0.5)가 발견되지 않았습니다.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-secondary/40 p-4">
      <div className="flex items-center gap-1.5">
        <Info size={12} className="text-muted-foreground" aria-hidden="true" />
        <span className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
          변수 간 상관관계 (참고용, 자동 연동 X)
        </span>
      </div>
      <ul className="mt-2 space-y-1">
        {strong.map(({ a, b, r }) => {
          const tone = r > 0 ? 'text-success' : r < 0 ? 'text-danger' : 'text-muted-foreground';
          return (
            <li
              key={`${a}-${b}`}
              className="flex items-center justify-between text-[0.6875rem] leading-relaxed"
            >
              <span className="text-foreground">
                {SLIDER_LABELS[a]} <span className="text-muted-foreground">↔</span>{' '}
                {SLIDER_LABELS[b]}
              </span>
              <span className={`font-black tabular-nums ${tone}`}>r = {r.toFixed(2)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
