import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { FlowVsRevenueScatter, simpleLinearRegression } from './FlowVsRevenueScatter';
import type { DistrictRanking } from '../../../../types';

describe('simpleLinearRegression', () => {
  it('완벽 선형 데이터 → slope + intercept 복구', () => {
    const points = [
      { x: 0, y: 0 },
      { x: 1, y: 2 },
      { x: 2, y: 4 },
      { x: 3, y: 6 },
    ];
    const { slope, intercept } = simpleLinearRegression(points)!;
    expect(slope).toBeCloseTo(2, 5);
    expect(intercept).toBeCloseTo(0, 5);
  });
  it('데이터 2개 미만 → null', () => {
    expect(simpleLinearRegression([])).toBe(null);
    expect(simpleLinearRegression([{ x: 1, y: 1 }])).toBe(null);
  });
});

describe('FlowVsRevenueScatter', () => {
  it('SVG 렌더', () => {
    const rankings: DistrictRanking[] = [
      {
        rank: 1,
        district: '서교동',
        score: 85,
        sales_growth: 0.1,
        sales_score: 80,
        pop_growth: 0.05,
        pop_score: 75,
        avg_rent: 0,
        rent_score: 0,
        vacancy_rate: 0,
        zoning_risk: 'safe',
      },
    ];
    const { container } = render(
      <FlowVsRevenueScatter rankings={rankings} winnerDistrict="서교동" />,
    );
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
