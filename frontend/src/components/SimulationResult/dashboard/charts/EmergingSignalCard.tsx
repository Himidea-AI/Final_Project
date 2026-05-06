/**
 * EmergingSignalCard — [E] emerging_district 시각화
 *
 * predict(dong_code, industry_code) → EmergingResult.
 * 4-tier fallback (change_ix → classifier → b1_trend → slope → none) 이 signal/summary/tier/raw 결정,
 * autoencoder 가 anomaly_score + consecutive_anomaly_quarters 보강.
 *
 * 카드 구성:
 *   - 헤더: 동 이름 + tier 배지 + (변화 1위 배지)
 *   - 신호등 + 변화도 점수 (grid-cols-2)
 *   - 8 분기 sparkline (quarter_history) + 트렌드 화살표 + Δ%
 *   - 16 동 분포 안 본 동 위치 (PeerDistributionBar — peer_distribution)
 *   - 자연어 summary 한 줄
 *
 * 2026-05-06: 평소와 다른 정도 게이지 + tier 별 RawChip 제거 — sparkline + peer bar + summary 로 정보 흡수.
 *
 * 렌더링 계약: 부모 (PredictEmergingDistrictTab 등) 가 항상 <div bg-card border rounded-3xl>
 * 로 감싸므로 자체 outer chrome 없이 bare 컨텐츠만 렌더 — 퐁당퐁당 (card→card 중첩 방지).
 */

import { Sparkles, TrendingDown, ShieldCheck, AlertCircle, Star } from 'lucide-react';
import type { EmergingSignal } from '../../../../types';
import { Sparkline } from './Sparkline';
import { PeerDistributionBar } from './PeerDistributionBar';

interface Props {
  signal: EmergingSignal | null | undefined;
  /** 헤더 우측에 표시할 동 라벨 (없으면 미표시). */
  district?: string;
  /** 현재 grid 4동 비교에서 anomaly_score 가 최댓값(=상대적으로 평소와 가장 다른 동)인지 여부. true 이면 헤더에 "변화 1위" 배지 노출. */
  isTopChange?: boolean;
  /** 4동 비교 grid 에서 동별 색 (SERIES_COLORS[idx]). sparkline / peer dot 색에 적용.
   *  미지정 시 SIGNAL_STYLES[signal.signal].bar 폴백. */
  seriesColor?: string;
}

interface SignalStyle {
  label: string;
  /** 아이콘 + 라벨 텍스트 색 — 박스 bg 는 다른 카드들과 통일된 쿨그레이(bg-secondary). */
  text: string;
  /** sparkline / peer dot fallback 색 — seriesColor 미지정 시 사용. */
  bar: string;
  Icon: typeof Sparkles;
}

const SIGNAL_STYLES: Record<EmergingSignal['signal'], SignalStyle> = {
  // 안정 상권 — success(Teal Green) + ShieldCheck.
  normal: {
    label: '안정 상권',
    text: 'text-success',
    bar: 'var(--success)',
    Icon: ShieldCheck,
  },
  // 신흥 상권 — primary(Deep Blue) + Sparkles.
  emerging: {
    label: '신흥 상권',
    text: 'text-primary',
    bar: 'var(--primary)',
    Icon: Sparkles,
  },
  // 쇠퇴 상권 — danger(Vivid Red) + TrendingDown.
  declining: {
    label: '쇠퇴 상권',
    text: 'text-danger',
    bar: 'var(--destructive)',
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

export function EmergingSignalCard({ signal, district, isTopChange = false, seriesColor }: Props) {
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
  const effectiveBarColor = seriesColor ?? style.bar;

  // sparkline 트렌드 화살표 + Δ% (8 분기 첫 ↔ 마지막)
  const history = signal.quarter_history;
  const sparkData = history?.map((q) => q.anomaly_score) ?? [];
  const sparkDelta = (() => {
    if (!history || history.length < 2) return null;
    const first = history[0]?.anomaly_score ?? 0;
    const last = history[history.length - 1]?.anomaly_score ?? 0;
    const delta = last - first;
    const arrow = delta > 0.05 ? '↗' : delta < -0.05 ? '↘' : '→';
    const sign = delta >= 0 ? '+' : '';
    return { arrow, label: `${sign}${(delta * 100).toFixed(0)}%` };
  })();

  return (
    <div className="space-y-5">
      {/* 헤더 — 동 이름이 카드 제목, 우측 tier 배지 (mock 배지 흡수). */}
      {/* isTopChange=true 시 동 이름 옆에 "변화 1위" 배지 — 4동 비교 grid 에서 anomaly_score 최댓값인 동 강조. */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <h3 className="text-xl font-black italic leading-none tracking-tight text-foreground">
            {district ?? '—'}
          </h3>
          {isTopChange && (
            <span className="px-2 py-0.5 rounded-full border border-primary/30 bg-primary/10 text-primary text-[0.5625rem] font-black flex items-center gap-1">
              <Star size={10} />
              변화 1위
            </span>
          )}
        </div>
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
          {/* per-quarter consecutive 메트릭 — 0 이면 의미 없으므로 숨김. */}
          {signal.consecutive_anomaly_quarters > 0 && (
            <div className="text-[0.5625rem] font-bold text-muted-foreground tabular-nums">
              최근 {signal.consecutive_anomaly_quarters}분기 연속
            </div>
          )}
        </div>
      </div>

      {/* 8 분기 sparkline — quarter_history 있을 때만. 트렌드 화살표 + Δ%. */}
      {sparkData.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
            <span>최근 8 분기 변화도</span>
            {sparkDelta && (
              <span className="tabular-nums" style={{ color: effectiveBarColor }}>
                {sparkDelta.arrow} {sparkDelta.label}
              </span>
            )}
          </div>
          <Sparkline data={sparkData} height={32} />
        </div>
      )}

      {/* 16 동 분포 안 본 동 위치 — peer_distribution 있을 때만. */}
      {signal.peer_distribution && (
        <PeerDistributionBar
          peerDistribution={signal.peer_distribution}
          ownScore={signal.anomaly_score}
          seriesColor={effectiveBarColor}
        />
      )}

      {/* summary 한 줄 — 4-tier fallback 이 만든 사용자 친화 한국어 메시지. 카드 하단. */}
      {signal.summary && (
        <p className="text-[0.6875rem] text-foreground leading-relaxed border-t border-border/50 pt-3">
          {signal.summary}
        </p>
      )}
    </div>
  );
}
