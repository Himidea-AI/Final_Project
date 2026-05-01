import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { mapGender } from '../utils/mappings';

interface CoreDemo {
  age: string;
  gender: string;
  share: number;
}

interface Props {
  core: CoreDemo | null | undefined;
}

export function CoreDemographicDonut({ core }: Props) {
  if (!core || typeof core.share !== 'number') {
    return (
      <div className="flex h-[140px] flex-col items-center justify-center rounded-2xl border border-dashed border-border text-muted-foreground text-xs">
        <span>demographic_depth 분석 대기</span>
      </div>
    );
  }
  const sharePct = Math.round(core.share * 100);
  const data = [
    { name: 'main', value: sharePct },
    { name: 'rest', value: 100 - sharePct },
  ];

  return (
    <div className="relative h-[140px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            innerRadius={40}
            outerRadius={60}
            startAngle={90}
            endAngle={-270}
            dataKey="value"
            stroke="none"
          >
            <Cell fill="var(--primary)" />
            <Cell fill="var(--border)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-[0.5625rem] font-black text-muted-foreground uppercase tracking-widest">
          Core
        </span>
        <span className="text-sm font-black text-foreground tabular-nums">
          {core.age} {mapGender(core.gender)}
        </span>
        <span className="text-[0.6875rem] font-black text-primary tabular-nums">{sharePct}%</span>
      </div>
    </div>
  );
}
