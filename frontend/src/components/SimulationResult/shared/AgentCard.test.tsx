import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AgentCard } from './AgentCard';
import type { AgentAttribution } from '../../../types';

const mockAttr: AgentAttribution = {
  id: 'competitor_intel',
  display_name: '경쟁 인텔',
  kind: 'Hybrid',
  sources: ['kakao_store', 'ftc_brand_franchise'],
  verdict: '진입 신호 RED · 포화 saturated',
  reasoning: '500m 내 경쟁점 145개. Pancras 감쇠로 자사 잠식 12% 추정.',
  confidence: 0.85,
};

describe('AgentCard', () => {
  it('full variant renders verdict + reasoning + sources', () => {
    render(<AgentCard attribution={mockAttr} size="full" />);
    expect(screen.getByText('경쟁 인텔')).toBeInTheDocument();
    expect(screen.getByText(/진입 신호 RED/)).toBeInTheDocument();
    expect(screen.getByText(/500m 내 경쟁점 145/)).toBeInTheDocument();
    expect(screen.getByText('kakao_store')).toBeInTheDocument();
  });

  it('compact variant renders only verdict one-line', () => {
    render(<AgentCard attribution={mockAttr} size="compact" />);
    expect(screen.getByText('경쟁 인텔')).toBeInTheDocument();
    expect(screen.queryByText(/500m 내 경쟁점 145/)).not.toBeInTheDocument();
  });

  it('kind badge 색상 매핑', () => {
    const { rerender } = render(
      <AgentCard attribution={{ ...mockAttr, kind: 'LLM' }} size="full" />,
    );
    expect(screen.getByText('LLM')).toBeInTheDocument();

    rerender(<AgentCard attribution={{ ...mockAttr, kind: 'RAG' }} size="full" />);
    expect(screen.getByText('RAG')).toBeInTheDocument();
  });
});
