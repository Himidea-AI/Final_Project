import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AgentConfidenceRadar, buildRadarData } from './AgentConfidenceRadar';
import type { AgentAttribution } from '../../../../types';

describe('buildRadarData', () => {
  it('8 에이전트 모두 0~100 점수로 변환', () => {
    const attrs: AgentAttribution[] = [
      {
        id: 'market_analyst',
        display_name: 'Market',
        kind: 'Python',
        sources: [],
        verdict: '',
        reasoning: '',
        confidence: 0.85,
      },
    ];
    const data = buildRadarData(attrs);
    expect(data).toHaveLength(8);
    const market = data.find((d) => d.id === 'market_analyst');
    expect(market?.score).toBe(85);
  });
  it('missing 에이전트는 score=null (0 폴백 금지 — 거짓 0% 신뢰도 방지)', () => {
    const data = buildRadarData([]);
    expect(data.every((d) => d.score === null)).toBe(true);
  });
  it('confidence null → score=null', () => {
    const attrs: AgentAttribution[] = [
      {
        id: 'legal',
        display_name: 'Legal',
        kind: 'RAG',
        sources: [],
        verdict: '',
        reasoning: '',
      },
    ];
    const legal = buildRadarData(attrs).find((d) => d.id === 'legal');
    expect(legal?.score).toBeNull();
  });
});

describe('AgentConfidenceRadar', () => {
  it('SVG 렌더', () => {
    const { container } = render(<AgentConfidenceRadar attributions={[]} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
