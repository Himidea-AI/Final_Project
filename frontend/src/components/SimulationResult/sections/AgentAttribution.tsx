import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';

interface Props {
  simResult: SimulationOutput;
}

export function AgentAttribution({ simResult }: Props) {
  const attrs = simResult.agent_attributions ?? [];

  if (attrs.length === 0) {
    return (
      <section>
        <SectionLabel label="AGENT ATTRIBUTION" subtitle="8 에이전트 판단 근거" />
        <div className="rounded-lg border border-stone-700 bg-stone-800 p-6 text-center text-sm text-stone-400">
          에이전트 판단 근거 데이터가 없습니다
        </div>
      </section>
    );
  }

  return (
    <section>
      <SectionLabel
        label="AGENT ATTRIBUTION"
        subtitle={`${attrs.length} 에이전트가 이 판단을 어떻게 만들었나`}
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {attrs.map((attr) => (
          <AgentCard key={attr.id} attribution={attr} size="full" />
        ))}
      </div>
    </section>
  );
}
