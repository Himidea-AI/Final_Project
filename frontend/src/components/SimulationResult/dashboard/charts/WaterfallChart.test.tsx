import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WaterfallChart, buildRows, type WaterfallStep } from './WaterfallChart';

describe('buildRows', () => {
  const steps: WaterfallStep[] = [
    { label: 'Base', value: 100, kind: 'base' },
    { label: 'A', value: 30, kind: 'contribution' },
    { label: 'B', value: -20, kind: 'contribution' },
    { label: 'Final', value: 110, kind: 'final' },
  ];
  it('base/final의 spacer는 0', () => {
    const { rows } = buildRows(steps);
    expect(rows[0].spacer).toBe(0);
    expect(rows[3].spacer).toBe(0);
  });
  it('양수 contribution: spacer = 이전 running total', () => {
    const { rows } = buildRows(steps);
    expect(rows[1].spacer).toBe(100);
    expect(rows[1].bar).toBe(30);
  });
  it('음수 contribution: spacer = running + value (더 낮은 위치)', () => {
    // A 후 running = 130. B = -20. spacer = 130 + -20 = 110. bar = |value| = 20.
    const { rows } = buildRows(steps);
    expect(rows[2].spacer).toBe(110);
    expect(rows[2].bar).toBe(20);
  });
});

describe('WaterfallChart', () => {
  it('빈 steps → placeholder', () => {
    const { container } = render(<WaterfallChart steps={[]} />);
    expect(container.textContent).toContain('Waterfall 데이터 없음');
  });
  it('steps 있으면 SVG 렌더', () => {
    const steps: WaterfallStep[] = [
      { label: 'Base', value: 100, kind: 'base' },
      { label: 'Final', value: 100, kind: 'final' },
    ];
    const { container } = render(<WaterfallChart steps={steps} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
