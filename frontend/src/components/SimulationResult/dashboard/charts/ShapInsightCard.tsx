/**
 * ShapInsightCard — SHAP 기여도를 텍스트 인사이트로 표시
 *
 * 2026-04-27 사용자 결정: WaterfallChart 제거 + 자연어 카드로 대체.
 * 본부 영업팀에 "어떤 요인이 매출에 ±얼마 기여" 직관 전달이 목적.
 */

import type { ShapResult } from '../../../../types';

interface Props {
  shap: ShapResult | null | undefined;
}

function formatKrw(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(abs / 100_000_000).toFixed(1)}억원`;
  if (abs >= 10_000) return `${(abs / 10_000).toFixed(0)}만원`;
  return `${Math.round(abs).toLocaleString('ko-KR')}원`;
}

export function ShapInsightCard({ shap }: Props) {
  if (!shap) {
    return (
      <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-8 text-center text-xs text-stone-500">
        SHAP 해석 데이터 없음 — 모델 예측 신뢰도가 확정되면 표시됩니다
      </div>
    );
  }

  const top = (shap.feature_importance ?? []).slice(0, 3);
  const isMock = shap.is_mock;

  if (top.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center text-xs text-stone-500">
        피처 기여도 산출 결과 없음
      </div>
    );
  }

  return (
    <div
      className={`rounded-2xl border p-5 ${
        isMock
          ? 'border-stone-800 bg-stone-950/30 opacity-60'
          : 'border-stone-800/60 bg-stone-950/50'
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
          기여도 상위 3개 피처
        </div>
        {isMock && (
          <span className="text-[9px] font-black text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full uppercase">
            데이터 신뢰도 검증 중
          </span>
        )}
      </div>
      <div className="space-y-3">
        {top.map((f) => {
          const positive = f.shap_value >= 0;
          const sign = positive ? '+' : '−';
          const colorClass = positive ? 'text-emerald-400' : 'text-rose-400';
          return (
            <div
              key={f.rank}
              className="flex items-baseline justify-between border-b border-stone-800/50 pb-2 last:border-b-0"
            >
              <span className="text-sm text-stone-300 font-bold">{f.feature_ko || f.feature}</span>
              <span className={`text-base font-black tabular-nums ${colorClass}`}>
                {sign}
                {formatKrw(f.shap_value)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-4 text-[10px] text-stone-500 leading-relaxed">
        모델이 매출을 예측할 때 각 요인이 기여한 영향. 양수는 매출 상승, 음수는 하락 요인.
      </p>
    </div>
  );
}
