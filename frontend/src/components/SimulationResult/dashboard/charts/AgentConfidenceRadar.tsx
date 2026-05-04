import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';
import type { AgentAttribution, AgentId } from '../../../../types';

const AGENT_ORDER: { id: AgentId; label: string }[] = [
  { id: 'market_analyst', label: '시장' },
  { id: 'population_analyst', label: '유동' },
  { id: 'demographic_depth', label: '인구' },
  { id: 'competitor_intel', label: '경쟁' },
  { id: 'legal', label: '법률' },
  { id: 'trend_forecaster', label: '트렌드' },
  { id: 'district_ranking', label: '랭킹' },
  { id: 'inflow', label: '접근성' },
  { id: 'synthesis', label: '종합' },
];

export interface RadarRow {
  id: AgentId;
  label: string;
  /** 실 confidence*100. 에이전트 미실행 or confidence null이면 null (이전엔 0으로 폴백해 "0% 신뢰도" 거짓 인상) */
  score: number | null;
}

export function buildRadarData(attributions: AgentAttribution[]): RadarRow[] {
  return AGENT_ORDER.map(({ id, label }) => {
    const attr = attributions.find((a) => a.id === id);
    const score = attr?.confidence != null ? Math.round(attr.confidence * 100) : null;
    return { id, label, score };
  });
}

interface Props {
  attributions: AgentAttribution[];
}

export function AgentConfidenceRadar({ attributions }: Props) {
  const data = buildRadarData(attributions);
  const missingAgents = data.filter((r) => r.score == null);
  const executedCount = data.length - missingAgents.length;

  return (
    <div className="flex flex-col gap-2">
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="70%">
            <PolarGrid stroke="var(--border)" />
            <PolarAngleAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fontSize: 9, fill: 'var(--muted-foreground)' }}
              axisLine={false}
            />
            {/* Recharts Radar는 null 값에서 vertex를 건너뜀 → 미실행 축은 그래프에서 자연스럽게 빠짐 */}
            <Radar
              dataKey="score"
              stroke="var(--primary)"
              fill="var(--primary)"
              fillOpacity={0.25}
              isAnimationActive={false}
              connectNulls={false}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center justify-center gap-2 text-[0.625rem] font-black uppercase tracking-widest">
        <span className="text-muted-foreground">
          실행 <span className="text-primary tabular-nums">{executedCount}</span>
          <span className="text-muted-foreground">/{data.length}</span>
        </span>
        {missingAgents.length > 0 && (
          <span className="text-muted-foreground">
            · 미실행:{' '}
            <span className="text-muted-foreground">
              {missingAgents.map((a) => a.label).join(', ')}
            </span>
          </span>
        )}
      </div>
    </div>
  );
}
