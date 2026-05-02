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
 *
 * 렌더링 계약: 부모 (PredictEmergingDistrictTab 등) 가 항상 <div bg-card border rounded-3xl>
 * 로 감싸므로 자체 outer chrome 없이 bare 컨텐츠만 렌더 — 퐁당퐁당 (card→card 중첩 방지).
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
    ring: 'ring-success/40',
    text: 'text-success',
    bg: 'bg-success/10',
    border: 'border-success/20',
    bar: 'bg-success',
    Icon: Sparkles,
  },
  declining: {
    label: '쇠퇴 상권',
    ring: 'ring-danger/40',
    text: 'text-danger',
    bg: 'bg-danger/10',
    border: 'border-danger/20',
    bar: 'bg-danger',
    Icon: TrendingDown,
  },
  normal: {
    label: '정상',
    ring: 'ring-border/40',
    text: 'text-foreground',
    bg: 'bg-muted/10',
    border: 'border-border/20',
    bar: 'bg-muted',
    Icon: Minus,
  },
};

export function EmergingSignalCard({ signal }: Props) {
  if (!signal) {
    return (
      <div className="text-center">
        <Sparkles className="mx-auto text-muted-foreground mb-2" size={22} />
        <p className="text-xs text-muted-foreground">신흥 상권 조기 감지 데이터 없음</p>
        <p className="mt-1 text-[0.625rem] text-muted-foreground">
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
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h4 className="text-sm font-black text-foreground flex items-center gap-2 uppercase tracking-tight">
          <Sparkles size={16} className="text-primary" /> 신흥 상권 조기 감지
          <span className="text-[0.625rem] font-black text-muted-foreground normal-case tracking-normal">
            emerging_district · LSTM AE
          </span>
        </h4>
        {signal.is_mock && (
          <div className="px-3 py-1 bg-warning/10 border border-warning/20 rounded-full text-[0.625rem] font-black text-warning flex items-center gap-1.5 uppercase tracking-widest">
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
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
            signal
          </div>
        </div>

        <div className="col-span-1 bg-secondary border border-border rounded-2xl p-5 flex flex-col items-center justify-center gap-1">
          <div className="text-3xl font-black text-foreground tabular-nums tracking-tighter">
            {scorePct}
          </div>
          <div className="text-[0.6875rem] font-bold text-muted-foreground tracking-wide">
            / 100
          </div>
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mt-1">
            이상도 점수
          </div>
        </div>

        <div className="col-span-1 bg-secondary border border-border rounded-2xl p-5 flex flex-col items-center justify-center gap-1">
          <div className="text-3xl font-black text-foreground tabular-nums tracking-tighter">
            {consecutive}
          </div>
          <div className="text-[0.6875rem] font-bold text-muted-foreground tracking-wide">분기</div>
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mt-1">
            연속 이상 감지
          </div>
        </div>
      </div>

      {/* anomaly_score 게이지 — 원본 score (≈0.04 범위, MSE-like) 는 3자리로 절단해 노이즈
          줄이고, 정규화 백분율은 좌측 신호등 아래 scorePct 카드에서 별도로 강조. */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
            Anomaly Score (threshold p95 = 0.041 기준 정규화)
          </span>
          <span className="text-[0.6875rem] font-black text-muted-foreground tabular-nums">
            {new Intl.NumberFormat('ko-KR', {
              minimumFractionDigits: 3,
              maximumFractionDigits: 3,
            }).format(signal.anomaly_score)}
          </span>
        </div>
        <div className="w-full bg-card h-2 rounded-full overflow-hidden">
          <div className={`h-full ${style.bar} transition-all`} style={{ width: `${scorePct}%` }} />
        </div>
        <div className="flex justify-between text-[0.5625rem] font-bold text-muted-foreground tabular-nums mt-1">
          <span>0.00</span>
          <span>0.50</span>
          <span>1.00</span>
        </div>
      </div>

      {/* 자연어 요약 */}
      <div className="p-4 bg-secondary border border-border rounded-2xl">
        <p className="text-[0.8125rem] text-foreground leading-relaxed">{signal.summary}</p>
      </div>

      {/* Disclaimer */}
      <div className="pt-4 border-t border-border space-y-1">
        <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ LSTM Autoencoder 비지도 학습 — threshold p95 ≈ 0.041 기준 anomaly_score 정규화 (1.0에
          클리핑).
        </p>
        <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ 마포 157개 조합 중 7개 이상 감지(약 4.5%) — 코로나 영향으로 쇠퇴 감지가 다수, 신흥
          신호는 상대적으로 희소합니다.
        </p>
      </div>
    </div>
  );
}
