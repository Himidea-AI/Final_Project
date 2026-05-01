import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Sparkline, computeTrendDirection } from './Sparkline';

describe('computeTrendDirection', () => {
  it('마지막 > 첫 20% 초과면 up', () => {
    expect(computeTrendDirection([100, 110, 125])).toBe('up');
  });
  it('마지막 < 첫 20% 초과면 down', () => {
    expect(computeTrendDirection([100, 90, 70])).toBe('down');
  });
  it('20% 이내면 flat', () => {
    expect(computeTrendDirection([100, 105, 95])).toBe('flat');
  });
  it('데이터 2개 미만이면 flat', () => {
    expect(computeTrendDirection([100])).toBe('flat');
    expect(computeTrendDirection([])).toBe('flat');
  });
});

describe('Sparkline', () => {
  it('데이터 없으면 "—" 렌더', () => {
    const { container } = render(<Sparkline data={[]} />);
    expect(container.textContent).toContain('—');
  });
  it('데이터 있으면 SVG 렌더', () => {
    const { container } = render(<Sparkline data={[100, 110, 125, 120]} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
