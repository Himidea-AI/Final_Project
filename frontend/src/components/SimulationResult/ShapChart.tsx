/**
 * ShapChart — TCN 매출 예측 SHAP 피처 기여도 수평 바 차트
 *
 * explain_tcn_prediction() 결과를 시각화:
 * - 상위 10개 피처 (abs_shap 기준 내림차순)
 * - positive(파랑) / negative(빨강) / neutral(회색) 방향별 색상 구분
 * - is_mock이면 "참고용 데이터" 배지 표시
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import type { ShapResult } from '../../types';

interface Props {
  data: ShapResult;
}

/** 방향별 색상 매핑 */
const DIRECTION_COLOR: Record<string, string> = {
  positive: 'var(--success)', // 매출 증가 기여
  negative: 'var(--danger)', // 매출 감소 기여
  neutral: 'var(--muted-foreground)', // 중립
};

export function ShapChart({ data }: Props) {
  // data 없으면 안내 메시지 표시
  if (!data || !data.feature_importance || data.feature_importance.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        SHAP 분석 데이터 없음
      </div>
    );
  }

  // 상위 10개 피처만 표시 (abs_shap 기준 내림차순 — 백엔드에서 이미 정렬되어 있음)
  const top10 = data.feature_importance.slice(0, 10);

  // recharts 수평 바 차트용: YAxis가 feature_ko, XAxis가 shap_value
  const chartData = top10.map((item) => ({
    feature_ko: item.feature_ko,
    shap_value: item.shap_value,
    abs_shap: item.abs_shap,
    direction: item.direction,
  }));

  return (
    <div>
      {/* mock 데이터 안내 배지 */}
      {data.is_mock && (
        <div className="mb-2 inline-block px-2 py-0.5 bg-warning/20 text-warning text-xs rounded">
          참고용 데이터 (모델 가중치 미로드)
        </div>
      )}

      {/* 예측 매출액 요약 */}
      <p className="text-xs text-muted-foreground mb-3">
        예측 매출:{' '}
        <span className="text-foreground font-semibold">
          {(data.predicted_value / 100_000_000).toFixed(1)}억{data.predicted_value_unit}
        </span>
      </p>

      <ResponsiveContainer width="100%" height={320}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
        >
          {/* 격자선 */}
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />

          {/* X축 — SHAP 값 (소수점 4자리) */}
          <XAxis
            type="number"
            tickFormatter={(v: number) => v.toFixed(4)}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
          />

          {/* Y축 — 피처 한국어명 */}
          <YAxis
            type="category"
            dataKey="feature_ko"
            width={130}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
          />

          {/* Tooltip — SHAP 값 소수점 4자리 */}
          <Tooltip
            formatter={(value: number) => [value.toFixed(4), 'SHAP 기여도']}
            contentStyle={{
              backgroundColor: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
            }}
            labelStyle={{ color: 'var(--card-foreground)', fontSize: 12 }}
            itemStyle={{ color: 'var(--muted-foreground)' }}
          />

          {/* 범례 */}
          <Legend
            payload={[
              { value: '매출 증가 기여', type: 'square', color: 'var(--success)' },
              { value: '매출 감소 기여', type: 'square', color: 'var(--danger)' },
              { value: '중립', type: 'square', color: 'var(--muted-foreground)' },
            ]}
            wrapperStyle={{ fontSize: 12, color: 'var(--muted-foreground)' }}
          />

          {/* 수평 바 — 방향별 색상 적용 */}
          <Bar dataKey="shap_value" name="SHAP 기여도">
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={DIRECTION_COLOR[entry.direction] ?? 'var(--muted-foreground)'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* 자연어 요약 문장 */}
      {data.summary && data.summary.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-muted-foreground font-medium">AI 분석 요약</p>
          {data.summary.map((sentence, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2 px-3 py-2 bg-card rounded-lg border border-border"
            >
              <span className="mt-0.5 text-warning text-xs flex-shrink-0">•</span>
              <span className="text-xs text-muted-foreground leading-relaxed">{sentence}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
