import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WeekdayWeekendBar, normalizeRatio } from './WeekdayWeekendBar';

describe('normalizeRatio', () => {
  it('ratio > 1이면 1로 clamp', () => {
    expect(normalizeRatio(1.5)).toBe(1);
  });
  it('ratio < 0이면 0으로 clamp', () => {
    expect(normalizeRatio(-0.3)).toBe(0);
  });
  it('정상 범위는 그대로', () => {
    expect(normalizeRatio(0.4)).toBe(0.4);
  });
  it('null/undefined → null', () => {
    expect(normalizeRatio(null)).toBe(null);
    expect(normalizeRatio(undefined)).toBe(null);
  });
});

describe('WeekdayWeekendBar', () => {
  it('ratio 있으면 라벨 렌더', () => {
    render(<WeekdayWeekendBar ratio={0.6} />);
    // Recharts renders axis labels in <tspan> + aria-hidden <span>; both match.
    expect(screen.getAllByText(/주중/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/주말/).length).toBeGreaterThan(0);
  });
  it('ratio null이면 placeholder', () => {
    render(<WeekdayWeekendBar ratio={null} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
