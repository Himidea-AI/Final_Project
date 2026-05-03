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
import { MAPO_DONGS } from '../../../../constants/mapoDongs';
import { BIZ_TO_INDUSTRY_CODE } from '../../../../constants/bizToIndustry';

/** summary 텍스트 안 raw code(11440660 / CS100010) 를 한국어 동/업종 이름으로 치환. */
const INDUSTRY_TO_BIZ_KO: Record<string, string> = (() => {
  const map: Record<string, string> = {};
  for (const [koName, code] of Object.entries(BIZ_TO_INDUSTRY_CODE)) {
    if (!/[가-힣]/.test(koName)) continue;
    if (!map[code]) map[code] = koName;
  }
  return map;
})();

/** summary 텍스트 안 raw code/jargon 을 사용자 친화 한국어로 치환:
 *  - 동 code(11440660) → 동 이름(서교동)
 *  - 업종 code(CS100010) → 한국어(커피)
 *  - signal 영문(emerging/declining/normal) → 한국어(신흥/쇠퇴/정상)
 *  - stage=LL/LH/HL/HH (4-tier classifier 내부 등급) — 사용자에게 의미 없으니 제거
 *  - "ML classifier 예측", "(신뢰 N%, F1=0.87)" 같은 metric jargon 정리
 *  - 다중 공백 단일화 + trim
 *  Backend predict_fallback.py 가 raw 형식 그대로 출력하는 거 frontend 단에서 후처리. */
function humanizeSignalText(text: string): string {
  let out = text;
  // 1. raw code → 한국어
  for (const { name, code } of MAPO_DONGS) {
    out = out.replace(new RegExp(`\\b${code}\\b`, 'g'), name);
  }
  for (const [code, koName] of Object.entries(INDUSTRY_TO_BIZ_KO)) {
    out = out.replace(new RegExp(`\\b${code}\\b`, 'g'), koName);
  }
  // 2. signal 결과(emerging/declining/normal) 통째 제거 — 신호등 박스에 이미 큰 시각으로 표시 중. 중복 회피.
  out = out.replace(/\s*→\s*(emerging|declining|normal)\b/g, '');
  // 3. stage=LL/LH/HL/HH (4-tier 내부 분류, 사용자 의미 0) 제거
  out = out.replace(/\s*stage=[A-Z]{2}\s*/g, ' ');
  // 4. ML/F1 jargon 정리
  out = out.replace(/ML\s+classifier\s+예측\s*/g, '');
  out = out.replace(/\(\s*신뢰\s+\d+%[^)]*\)\s*/g, '');
  // 5. trailing 화살표/대시/콜론 + 다중 공백 정리
  out = out.replace(/[\s—:>→-]+$/g, '');
  out = out.replace(/\s+→\s+/g, ' — ');
  out = out.replace(/\s{2,}/g, ' ').trim();
  return out;
}

interface Props {
  signal: EmergingSignal | null | undefined;
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

export function EmergingSignalCard({ signal }: Props) {
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
  const consecutive = signal.consecutive_anomaly_quarters;

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h4 className="text-sm font-black text-foreground flex items-center gap-2 uppercase tracking-tight">
          <Sparkles size={16} className="text-primary" /> 상권 조기 감지
        </h4>
        {signal.is_mock && (
          <div className="px-3 py-1 bg-warning/10 border border-warning/20 rounded-full text-[0.625rem] font-black text-warning flex items-center gap-1.5">
            <AlertCircle size={10} /> 데이터 신뢰도 검증 중
          </div>
        )}
      </div>

      {/* 신호등 + 연속 분기 — 세 박스 모두 동일 쿨그레이(bg-secondary border) 통일.
          아이콘/라벨 색만 신호별 차별화 (정상=Teal Green / 신흥=Deep Blue / 쇠퇴=Vivid Red). */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-1 bg-secondary border border-border rounded-2xl p-5 flex flex-col items-center justify-center gap-2">
          <Icon className={style.text} size={28} />
          <div className={`text-base font-black ${style.text} tracking-tight`}>{style.label}</div>
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
            상권 신호
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

      {/* 자연어 요약 — backend raw code(11440660 / CS100010) 를 한국어 동/업종 이름으로 휴머나이즈. */}
      <div className="p-4 bg-secondary border border-border rounded-2xl">
        <p className="text-[0.8125rem] text-foreground leading-relaxed">
          {humanizeSignalText(signal.summary)}
        </p>
      </div>

      {/* Disclaimer — 사용자 친화 톤. 모델명/threshold 같은 jargon 제거. */}
      <div className="pt-4 border-t border-border space-y-1">
        <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ 분기별 상권 데이터 비교를 통한 상권 변화 조기 감지. 0.5 이상이면 평소와 다른 변화 신호.
        </p>
        <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ 마포구 16동 × 10업종 학습. 코로나 영향으로 쇠퇴 감지가 다수, 신흥 신호는 상대적으로
          희소합니다.
        </p>
      </div>
    </div>
  );
}
