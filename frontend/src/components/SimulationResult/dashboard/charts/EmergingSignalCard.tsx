/**
 * EmergingSignalCard — [E] emerging_district 시각화
 *
 * predict(dong_code, industry_code) → EmergingResult.
 * 신호등 (emerging=green, declining=rose, normal=stone) + anomaly_score 게이지
 * + 연속 이상 분기 + 자연어 요약.
 *
 * 데이터 흐름:
 *   models/emerging_district/predict.predict
 *     → models/interface.py generate
 *     → backend/src/main.py response_data.emerging_signal
 *     → MarketTab → EmergingSignalCard
 */

import { Sparkles, TrendingDown, Minus, AlertCircle } from 'lucide-react';
import type { EmergingSignal } from '../../../../types';

interface Props {
  signal: EmergingSignal | null | undefined;
}

interface SignalStyle {
  label: string;
  ring: string;
  text: string;
  bg: string;
  border: string;
  bar: string;
  Icon: typeof Sparkles;
}

const SIGNAL_STYLES: Record<EmergingSignal['signal'], SignalStyle> = {
  emerging: {
    label: '신흥 상권',
    ring: 'ring-emerald-500/40',
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    bar: 'bg-emerald-500',
    Icon: Sparkles,
  },
  declining: {
    label: '쇠퇴 상권',
    ring: 'ring-rose-500/40',
    text: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    bar: 'bg-rose-500',
    Icon: TrendingDown,
  },
  normal: {
    label: '정상',
    ring: 'ring-stone-500/40',
    text: 'text-stone-300',
    bg: 'bg-stone-500/10',
    border: 'border-stone-500/30',
    bar: 'bg-stone-500',
    Icon: Minus,
  },
};

export function EmergingSignalCard({ signal }: Props) {
  if (!signal) {
    return (
      <div className="rounded-3xl border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center">
        <Sparkles className="mx-auto text-stone-600 mb-2" size={22} />
        <p className="text-xs text-stone-500">신흥 상권 조기 감지 데이터 없음</p>
        <p className="mt-1 text-[10px] text-stone-600">
          emerging_district (LSTM Autoencoder) 모델 호출 실패 시 표시됩니다
        </p>
      </div>
    );
  }

  const style = SIGNAL_STYLES[signal.signal] ?? SIGNAL_STYLES.normal;
  const { Icon } = style;
  const scorePct = Math.round(Math.min(1, Math.max(0, signal.anomaly_score)) * 100);
  const consecutive = signal.consecutive_anomaly_quarters;

  return (
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h4 className="text-sm font-black text-stone-100 flex items-center gap-2 uppercase tracking-tight">
          <Sparkles size={16} className="text-indigo-400" /> 신흥 상권 조기 감지
          <span className="text-[10px] font-black text-stone-500 normal-case tracking-normal">
            emerging_district · LSTM AE
          </span>
        </h4>
        {signal.is_mock && (
          <div className="px-3 py-1 bg-amber-500/10 border border-amber-500/20 rounded-full text-[10px] font-black text-amber-400 flex items-center gap-1.5 uppercase tracking-widest">
            <AlertCircle size={10} /> Mock
          </div>
        )}
      </div>

      {/* 신호등 + 연속 분기 */}
      <div className="grid grid-cols-3 gap-4">
        <div
          className={`col-span-1 rounded-2xl border ${style.border} ${style.bg} p-5 flex flex-col items-center justify-center gap-2 ring-1 ${style.ring}`}
        >
          <Icon className={style.text} size={28} />
          <div className={`text-base font-black ${style.text} tracking-tight`}>{style.label}</div>
          <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
            signal
          </div>
        </div>

        <div className="col-span-1 bg-stone-950/40 border border-stone-800 rounded-2xl p-5 flex flex-col items-center justify-center gap-1">
          <div className="text-3xl font-black text-stone-100 tabular-nums tracking-tighter">
            {scorePct}
          </div>
          <div className="text-[11px] font-bold text-stone-400 tracking-wide">/ 100</div>
          <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mt-1">
            이상도 점수
          </div>
        </div>

        <div className="col-span-1 bg-stone-950/40 border border-stone-800 rounded-2xl p-5 flex flex-col items-center justify-center gap-1">
          <div className="text-3xl font-black text-stone-100 tabular-nums tracking-tighter">
            {consecutive}
          </div>
          <div className="text-[11px] font-bold text-stone-400 tracking-wide">분기</div>
          <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mt-1">
            연속 이상 감지
          </div>
        </div>
      </div>

      {/* anomaly_score 게이지 */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
            Anomaly Score (threshold p95 = 0.0414 기준 정규화)
          </span>
          <span className="text-[11px] font-black text-stone-400 tabular-nums">
            {signal.anomaly_score.toFixed(4)}
          </span>
        </div>
        <div className="w-full bg-stone-800 h-2 rounded-full overflow-hidden">
          <div className={`h-full ${style.bar} transition-all`} style={{ width: `${scorePct}%` }} />
        </div>
        <div className="flex justify-between text-[9px] font-bold text-stone-600 tabular-nums mt-1">
          <span>0.00</span>
          <span>0.50</span>
          <span>1.00</span>
        </div>
      </div>

      {/* 자연어 요약 */}
      <div className="p-4 bg-stone-950/40 border border-stone-800 rounded-2xl">
        <p className="text-[13px] text-stone-300 leading-relaxed">{signal.summary}</p>
      </div>

      {/* Disclaimer */}
      <div className="pt-4 border-t border-stone-800/50 space-y-1">
        <p className="text-[10px] text-stone-600 leading-relaxed">
          ※ LSTM Autoencoder 비지도 학습 — threshold p95 = 0.041380 기준 anomaly_score 정규화 (1.0에
          클리핑).
        </p>
        <p className="text-[10px] text-stone-600 leading-relaxed">
          ※ 마포 157개 조합 중 7개 이상 감지(약 4.5%) — 코로나 영향으로 쇠퇴 감지가 다수, 신흥
          신호는 상대적으로 희소합니다.
        </p>
      </div>
    </div>
  );
}
