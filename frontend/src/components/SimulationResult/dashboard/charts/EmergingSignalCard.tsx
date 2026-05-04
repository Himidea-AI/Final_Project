/**
 * EmergingSignalCard — [E] emerging_district 시각화
 *
 * predict(dong_code, industry_code) → EmergingResult.
 * 4-tier fallback (change_ix → classifier → b1_trend → slope → none) 이 signal/summary/tier/raw 결정,
 * autoencoder 가 anomaly_score + consecutive_anomaly_quarters 보강.
 *
 * 헤더 우측: tier 배지 (mock 배지 흡수). KPI 그리드: 신호등 + 변화도 점수.
 * 게이지: 평소와 다른 정도 (낮음 ↔ 높음). summary 한 줄. tier별 raw chip.
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
  // 안정 상권 — success(Teal Green) + ShieldCheck.
  normal: {
    label: '안정 상권',
    text: 'text-success',
    bar: 'bg-success',
    Icon: ShieldCheck,
  },
  // 신흥 상권 — primary(Deep Blue) + Sparkles.
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

/** tier 별 헤더 배지 라벨 + 색상. mock 배지를 tier 배지에 흡수 (none = 데이터 검증 중). */
const TIER_BADGE: Record<EmergingSignal['tier'], { label: string; cls: string }> = {
  change_ix: {
    label: '공식 데이터',
    cls: 'text-success bg-success/10 border-success/20',
  },
  classifier: {
    label: 'AI 판정',
    cls: 'text-primary bg-primary/10 border-primary/20',
  },
  b1_trend: {
    label: '보조 신호',
    cls: 'text-warning bg-warning/10 border-warning/20',
  },
  slope: {
    label: '보조 신호',
    cls: 'text-warning bg-warning/10 border-warning/20',
  },
  none: {
    label: '데이터 검증 중',
    cls: 'text-warning bg-warning/10 border-warning/20',
  },
};

/** slope 부호별 화살표 — 임계 0.5 (백엔드 _slope_verb 와 동일). */
function _slopeArrow(value: number): string {
  if (value > 0.5) return '↑';
  if (value < -0.5) return '↓';
  return '→';
}

/** 비율 부호 포함 한국어 포맷 — +5.0% / -3.2% / +0.0%. */
function _percentSigned(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
}

/** tier별 raw evidence chip — change_ix·none 은 chip 미렌더. */
function RawChip({ signal }: { signal: EmergingSignal }) {
  const { tier, raw } = signal;

  if (tier === 'classifier' && typeof raw.confidence === 'number') {
    const pct = Math.round(raw.confidence * 100);
    return (
      <div className="rounded-2xl border border-border bg-secondary px-3 py-2 text-[0.6875rem] text-foreground">
        <div className="flex items-center justify-between mb-1">
          <span className="font-black">신뢰도</span>
          <span className="font-bold tabular-nums">{pct}%</span>
        </div>
        <div className="w-full bg-card h-1.5 rounded-full overflow-hidden">
          <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }

  if (tier === 'b1_trend') {
    const sg = raw.subway_growth;
    const mr = raw.migration_2030_rate;
    return (
      <div className="flex flex-wrap gap-2">
        {typeof sg === 'number' && (
          <span className="rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-black text-foreground tabular-nums">
            지하철 {_percentSigned(sg)}
          </span>
        )}
        {typeof mr === 'number' && (
          <span className="rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-black text-foreground tabular-nums">
            청년 {_percentSigned(mr)}
          </span>
        )}
      </div>
    );
  }

  if (tier === 'slope') {
    const ss = raw.sales_slope;
    const sts = raw.store_slope;
    return (
      <div className="flex flex-wrap gap-2">
        {typeof ss === 'number' && (
          <span className="rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-black text-foreground">
            매출 {_slopeArrow(ss)}
          </span>
        )}
        {typeof sts === 'number' && (
          <span className="rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-black text-foreground">
            점포수 {_slopeArrow(sts)}
          </span>
        )}
      </div>
    );
  }

  // change_ix: summary 로 충분, chip 미렌더. none: 데이터 없음, chip 미렌더.
  return null;
}

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
  const tierBadge = TIER_BADGE[signal.tier] ?? TIER_BADGE.none;
  const showAlertIcon = signal.tier === 'none';

  return (
    <div className="space-y-6">
      {/* 헤더 — 동 이름이 카드 제목, 우측 tier 배지 (mock 배지 흡수). */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-xl font-black italic leading-none tracking-tight text-foreground">
          {district ?? '—'}
        </h3>
        <div
          className={`px-3 py-1 ${tierBadge.cls} border rounded-full text-[0.625rem] font-black flex items-center gap-1.5`}
        >
          {showAlertIcon && <AlertCircle size={10} />}
          {tierBadge.label}
        </div>
      </div>

      {/* 신호등 + 변화도 점수 — 두 박스 동일 쿨그레이(bg-secondary border) 통일.
          아이콘/라벨 색만 신호별 차별화 (안정=Teal Green / 신흥=Deep Blue / 쇠퇴=Vivid Red). */}
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
            평소 대비 변화
          </div>
        </div>
      </div>

      {/* 평소와 다른 정도 게이지 — 0~1 정규화 막대. 0.5 이상은 통계적으로 유의미한 패턴 변화. */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
            평소와 다른 정도
          </span>
          <span className="text-[0.6875rem] font-black text-muted-foreground tabular-nums">
            {signal.anomaly_score.toFixed(2)}
          </span>
        </div>
        <div className="w-full bg-card h-2 rounded-full overflow-hidden">
          <div className={`h-full ${style.bar} transition-all`} style={{ width: `${scorePct}%` }} />
        </div>
        <div className="flex justify-between text-[0.5625rem] font-bold text-muted-foreground tabular-nums mt-1">
          <span>낮음</span>
          <span>높음</span>
        </div>
      </div>

      {/* summary 한 줄 — 4-tier fallback 이 만든 사용자 친화 한국어 메시지. */}
      <p className="text-xs text-foreground tracking-tight leading-relaxed">{signal.summary}</p>

      {/* tier별 raw evidence chip — change_ix·none 은 미렌더. */}
      <RawChip signal={signal} />
    </div>
  );
}
