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
  { id: 'synthesis', label: '종합' },
];

export interface RadarRow {
  id: AgentId;
  label: string;
  score: number;
}

export function buildRadarData(attributions: AgentAttribution[]): RadarRow[] {
  return AGENT_ORDER.map(({ id, label }) => {
    const attr = attributions.find((a) => a.id === id);
    const score = attr?.confidence != null ? Math.round(attr.confidence * 100) : 0;
    return { id, label, score };
  });
}

interface Props {
  attributions: AgentAttribution[];
}

export function AgentConfidenceRadar({ attributions }: Props) {
  const data = buildRadarData(attributions);
  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="70%">
          <PolarGrid stroke="#292524" />
          <PolarAngleAxis dataKey="label" tick={{ fontSize: 10, fill: '#a8a29e' }} />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 9, fill: '#57534e' }}
            axisLine={false}
          />
          <Radar
            dataKey="score"
            stroke="#818cf8"
            fill="#818cf8"
            fillOpacity={0.25}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
