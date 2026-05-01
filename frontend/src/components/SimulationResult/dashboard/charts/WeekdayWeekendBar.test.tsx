import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WeekdayWeekendBar, normalizeRatio } from './WeekdayWeekendBar';

describe('normalizeRatio (배수 → 평일 점유율)', () => {
  it('배수=1 (평일=주말) → 0.5', () => {
    expect(normalizeRatio(1)).toBeCloseTo(0.5, 6);
  });
  it('배수=2 (평일이 주말의 2배) → 약 0.667', () => {
    expect(normalizeRatio(2)).toBeCloseTo(2 / 3, 6);
  });
  it('배수=0.5 (주말이 평일의 2배) → 약 0.333', () => {
    expect(normalizeRatio(0.5)).toBeCloseTo(1 / 3, 6);
  });
  it('배수=0 (평일 매출 0) → 0 (모두 주말)', () => {
    expect(normalizeRatio(0)).toBe(0);
  });
  it('음수는 invalid → null', () => {
    expect(normalizeRatio(-0.3)).toBe(null);
  });
  it('NaN/Infinity → null', () => {
    expect(normalizeRatio(NaN)).toBe(null);
    expect(normalizeRatio(Infinity)).toBe(null);
  });
  it('null/undefined → null', () => {
    expect(normalizeRatio(null)).toBe(null);
    expect(normalizeRatio(undefined)).toBe(null);
  });
});

describe('WeekdayWeekendBar', () => {
  it('ratio 있으면 라벨 렌더 (평일·주말 둘 다)', () => {
    render(<WeekdayWeekendBar ratio={1.5} />);
    // Recharts renders axis labels in <tspan> + aria-hidden <span>; both match.
    expect(screen.getAllByText(/주중/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/주말/).length).toBeGreaterThan(0);
  });
  it('ratio null이면 placeholder', () => {
    render(<WeekdayWeekendBar ratio={null} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
