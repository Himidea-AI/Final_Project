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

import { Sparkles, TrendingDown, ShieldCheck, AlertCircle } from 'lucide-react';
import type { EmergingSignal } from '../../../../types';

interface Props {
  signal: EmergingSignal | null | undefined;
  /** 헤더 우측에 표시할 동 라벨 (없으면 미표시). */
  district?: string;
}

interface SignalStyle {
  label: string;
  /** 아이콘 + 라벨 텍스트 색 — 박스 bg 는 다른 카드들과 통일된 쿨그레이(bg-secondary). */
  text: string;
  /** 게이지 막대 색 — 박스 bg 와 별개로 막대만 신호색. */
  bar: string;
  Icon: typeof Sparkles;
}

const SIGNAL_STYLES: Record<EmergingSignal['signal'], SignalStyle> = {
  // 정상 상권 — 안정성 의미로 success(Teal Green) + ShieldCheck 아이콘.
  normal: {
    label: '정상 상권',
    text: 'text-success',
    bar: 'bg-success',
    Icon: ShieldCheck,
  },
  // 신흥 상권 — 브랜드 primary(Deep Blue) + Sparkles 아이콘 (반짝이는 신호 메타포).
  emerging: {
    label: '신흥 상권',
    text: 'text-primary',
    bar: 'bg-primary',
    Icon: Sparkles,
  },
  // 쇠퇴 상권 — danger(Vivid Red) + TrendingDown.
  declining: {
    label: '쇠퇴 상권',
    text: 'text-danger',
    bar: 'bg-danger',
    Icon: TrendingDown,
  },
};

export function EmergingSignalCard({ signal, district }: Props) {
  if (!signal) {
    return (
      <div className="text-center">
        <Sparkles className="mx-auto text-muted-foreground mb-2" size={22} />
        <p className="text-xs text-muted-foreground">상권 조기 감지 데이터 없음</p>
        <p className="mt-1 text-[0.625rem] text-muted-foreground">
          분석 데이터를 받지 못했습니다. 잠시 후 다시 시도해주세요
        </p>
      </div>
    );
  }

  const style = SIGNAL_STYLES[signal.signal] ?? SIGNAL_STYLES.normal;
  const { Icon } = style;
  const scorePct = Math.round(Math.min(1, Math.max(0, signal.anomaly_score)) * 100);

  return (
    <div className="space-y-6">
      {/* 헤더 — 동 이름이 카드 제목 역할 (큰 폰트). 우측엔 mock 배지만. */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-xl font-black italic leading-none tracking-tight text-foreground">
          {district ?? '—'}
        </h3>
        {signal.is_mock && (
          <div className="px-3 py-1 bg-warning/10 border border-warning/20 rounded-full text-[0.625rem] font-black text-warning flex items-center gap-1.5">
            <AlertCircle size={10} /> 데이터 신뢰도 검증 중
          </div>
        )}
      </div>

      {/* 신호등 + 이상도 점수 — 두 박스 동일 쿨그레이(bg-secondary border) 통일.
          아이콘/라벨 색만 신호별 차별화 (정상=Teal Green / 신흥=Deep Blue / 쇠퇴=Vivid Red). */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-secondary border border-border rounded-2xl p-5 flex flex-col items-center justify-center gap-2">
          <Icon className={style.text} size={28} />
          <div className={`text-base font-black ${style.text} tracking-tight`}>{style.label}</div>
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
            상권 신호
          </div>
        </div>

        <div className="bg-secondary border border-border rounded-2xl p-5 flex flex-col items-center justify-center gap-1">
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
      </div>

      {/* 이상도 게이지 — 0~1 정규화 막대. 0.5 이상은 통계적으로 유의미한 상권 변화 신호. */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
            이상도 (0~1 정규화)
          </span>
          <span className="text-[0.6875rem] font-black text-muted-foreground tabular-nums">
            {signal.anomaly_score.toFixed(2)}
          </span>
        </div>
        <div className="w-full bg-card h-2 rounded-full overflow-hidden">
          <div className={`h-full ${style.bar} transition-all`} style={{ width: `${scorePct}%` }} />
        </div>
        <div className="flex justify-between text-[0.5625rem] font-bold text-muted-foreground tabular-nums mt-1">
          <span>0</span>
          <span>0.5</span>
          <span>1</span>
        </div>
      </div>
    </div>
  );
}
