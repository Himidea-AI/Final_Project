/**
 * PeakHourCard — [D] living_pop_forecast 시각화
 *
 * predict_peak(dong_name, n_quarters=4)의 첫 분기(q1) 24시간 예측을 막대로 표시.
 * 피크 시간대는 인디고 강조, 나머지는 stone.
 *
 * 데이터 흐름:
 *   models/living_pop_forecast/predict.predict_peak
 *     → models/interface.py generate (dict 래핑)
 *     → backend/src/main.py response_data.living_pop_forecast
 *     → PredictCustomerFlowTab → PeakHourCard
 */

import { Activity, Clock } from 'lucide-react';
import type { LivingPopForecast } from '../../../../types';

interface Props {
  data: LivingPopForecast | null | undefined;
}

function formatTimeZone(tz: number): string {
  const start = tz.toString().padStart(2, '0');
  const end = ((tz + 1) % 24).toString().padStart(2, '0');
  return `${start}–${end}시`;
}

function formatPop(pop: number): string {
  if (pop >= 10000) return `${(pop / 10000).toFixed(1)}만`;
  if (pop >= 1000) return `${(pop / 1000).toFixed(1)}천`;
  return Math.round(pop).toLocaleString('ko-KR');
}

export function PeakHourCard({ data }: Props) {
  if (!data || !Array.isArray(data.quarters) || data.quarters.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-border bg-card/40 p-6 text-center">
        <Activity className="mx-auto text-muted-foreground mb-2" size={22} />
        <p className="text-xs text-muted-foreground">유동인구 피크 시간 예측 데이터 없음</p>
        <p className="mt-1 text-[0.625rem] text-muted-foreground">
          living_pop_forecast (TCN) 모델 호출 실패 시 표시됩니다
        </p>
      </div>
    );
  }

  // 첫 분기(q1) 24시간 예측. all_hours 배열에서 일부 시간대가 빠질 수 있어 time_zone 키 기준 정렬.
  const q1 = data.quarters[0];
  const hourly = [...(q1.all_hours ?? [])].sort((a, b) => a.time_zone - b.time_zone);
  const maxPop = Math.max(1, ...hourly.map((h) => h.predicted_pop));
  const peakTz = q1.peak_time_zone;
  const peakPop = q1.peak_pop;

  return (
    <div className="bg-card/40 border border-border/60 rounded-3xl p-8 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h4 className="text-sm font-black text-foreground flex items-center gap-2 uppercase tracking-tight">
          <Activity size={16} className="text-primary" /> 유동인구 피크 시간 예측
          <span className="text-[0.625rem] font-black text-muted-foreground normal-case tracking-normal">
            living_pop_forecast · TCN
          </span>
        </h4>
        <div className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-[0.6875rem] font-black text-primary tabular-nums flex items-center gap-1.5">
          <Clock size={11} />
          피크 {formatTimeZone(peakTz)} · {formatPop(peakPop)}명
        </div>
      </div>

      {/* 자연어 요약 */}
      <p className="text-[0.8125rem] text-foreground leading-relaxed">
        {data.dong_name} 다음 분기 시간대별 유동인구 예측. 피크는 {formatTimeZone(peakTz)}에 약{' '}
        {formatPop(peakPop)}명으로 집중되며, 운영 인력·재고 배치의 기준 시간대로 활용 가능합니다.
      </p>

      {/* 24시간 막대 차트 */}
      <div>
        <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-3">
          24시간 예측 ({q1.quarter_offset}분기 후)
        </div>
        <div className="flex items-end gap-[2px] h-[140px]">
          {hourly.map((h) => {
            const height = Math.max(4, (h.predicted_pop / maxPop) * 100);
            const isPeak = h.time_zone === peakTz;
            return (
              <div
                key={h.time_zone}
                className="flex-1 flex flex-col items-center gap-1 group relative"
                title={`${formatTimeZone(h.time_zone)} · ${formatPop(h.predicted_pop)}명`}
              >
                <div
                  className={`w-full rounded-sm transition-all ${
                    isPeak
                      ? 'bg-primary shadow-[0_0_8px_rgba(0,44,209,0.4)]'
                      : 'bg-muted group-hover:bg-muted'
                  }`}
                  style={{ height: `${height}%` }}
                />
                {/* 시간대 라벨 — 3의 배수 시간만 표시 (가독성, 24개 라벨 다 노출하면 빽빽) */}
                <div
                  className={`text-[0.5rem] font-bold tabular-nums ${
                    isPeak ? 'text-primary' : 'text-muted-foreground'
                  }`}
                >
                  {h.time_zone % 3 === 0 ? h.time_zone : ''}
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex justify-between text-[0.5625rem] font-bold text-muted-foreground tabular-nums mt-1">
          <span>0시</span>
          <span>6시</span>
          <span>12시</span>
          <span>18시</span>
          <span>23시</span>
        </div>
      </div>

      {/* 분기별 피크 요약 (q1~qn) */}
      {data.quarters.length > 1 && (
        <div>
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-3">
            분기별 피크 시간 추이
          </div>
          <div className="grid grid-cols-4 gap-2">
            {data.quarters.map((q) => (
              <div
                key={q.quarter_offset}
                className="bg-card/40 border border-border rounded-xl p-3 text-left"
              >
                <div className="text-[0.5625rem] font-black text-muted-foreground uppercase tracking-widest">
                  +{q.quarter_offset}분기
                </div>
                <div className="text-base font-black text-foreground tabular-nums tracking-tighter mt-1">
                  {formatTimeZone(q.peak_time_zone)}
                </div>
                <div className="text-[0.625rem] font-bold text-primary tabular-nums mt-0.5">
                  {formatPop(q.peak_pop)}명
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      <div className="pt-4 border-t border-border/50 space-y-1">
        <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ TCN 모델 — 코로나 시기(2020~2021) 가중치 0.5 보정 적용.
        </p>
        <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ 마포구 16동 × 24시간대 단일 학습. 다른 조합/시간대는 외삽 결과로 신뢰도 하락 가능.
        </p>
      </div>
    </div>
  );
}
