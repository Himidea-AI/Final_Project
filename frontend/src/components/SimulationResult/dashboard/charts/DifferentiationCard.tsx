/**
 * DifferentiationCard — competitor_intel 차별화 포지션 + 기회/리스크
 *
 * 데이터: competitor_intel.differentiation_position / key_opportunities / key_risks
 * 디자인: pull-quote 스타일 + 양분 칩 리스트
 *
 * 렌더링 계약: 부모(MarketTab 등)가 outer wrapper(bg-card rounded-[40px] p-6) + 헤더 제공.
 * 본 컴포넌트는 bare content (blockquote + 기회/리스크 grid) 만 렌더 — 퐁당퐁당 중첩 회피.
 */

import { Lightbulb, ShieldAlert } from 'lucide-react';

interface Props {
  differentiation?: string | null;
  opportunities?: string[];
  risks?: string[];
}

export function DifferentiationCard({ differentiation, opportunities, risks }: Props) {
  const hasDiff = differentiation && differentiation.trim().length > 0;
  const hasOpp = opportunities && opportunities.length > 0;
  const hasRisks = risks && risks.length > 0;

  if (!hasDiff && !hasOpp && !hasRisks) {
    return null;
  }

  return (
    <>
      {hasDiff && (
        <div className="relative pl-4 border-l-2 border-primary/40 mb-4">
          <p className="text-sm text-foreground leading-relaxed italic">{differentiation}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {/* 기회 — 퐁당퐁당 룰: outer card(white) ↔ inner secondary(cool gray).
            의미 색은 텍스트/아이콘에만 — bg/border tint 금지. */}
        <div className="rounded-2xl border border-border bg-secondary p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Lightbulb size={12} className="text-success" />
            <span className="text-[0.625rem] font-black uppercase tracking-widest text-success">
              핵심 기회
            </span>
          </div>
          {hasOpp ? (
            <ul className="space-y-1.5">
              {opportunities!.map((o, i) => (
                <li
                  key={i}
                  className="text-[0.6875rem] text-foreground leading-relaxed flex items-start gap-1.5"
                >
                  <span className="text-success mt-0.5">•</span>
                  <span>{o}</span>
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-[0.625rem] text-muted-foreground">식별된 기회 없음</span>
          )}
        </div>

        {/* 리스크 */}
        <div className="rounded-2xl border border-border bg-secondary p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <ShieldAlert size={12} className="text-danger" />
            <span className="text-[0.625rem] font-black uppercase tracking-widest text-danger">
              핵심 리스크
            </span>
          </div>
          {hasRisks ? (
            <ul className="space-y-1.5">
              {risks!.map((r, i) => (
                <li
                  key={i}
                  className="text-[0.6875rem] text-foreground leading-relaxed flex items-start gap-1.5"
                >
                  <span className="text-danger mt-0.5">•</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-[0.625rem] text-muted-foreground">식별된 리스크 없음</span>
          )}
        </div>
      </div>
    </>
  );
}
