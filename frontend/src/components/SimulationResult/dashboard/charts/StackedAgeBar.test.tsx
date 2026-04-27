import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StackedAgeBar, normalizeAgeGroups } from './StackedAgeBar';

describe('normalizeAgeGroups', () => {
  it('빈 배열 → []', () => {
    expect(normalizeAgeGroups([])).toEqual([]);
  });
  it('정상 배열 share 합이 1.0 초과 시 정규화', () => {
    const result = normalizeAgeGroups([
      { age_group: '30대', share: 0.6 },
      { age_group: '20대', share: 0.5 },
      { age_group: '40대', share: 0.3 },
    ]);
    const sum = result.reduce((s, r) => s + r.share, 0);
    expect(sum).toBeCloseTo(1.0, 5);
  });
  it('share 합이 1 미만이면 "기타" 자동 추가', () => {
    const result = normalizeAgeGroups([
      { age_group: '30대', share: 0.4 },
      { age_group: '20대', share: 0.3 },
    ]);
    expect(result).toHaveLength(3);
    expect(result[2].age_group).toBe('기타');
    expect(result[2].share).toBeCloseTo(0.3, 5);
  });
});

describe('StackedAgeBar', () => {
  it('데이터 있으면 연령대 라벨 렌더', () => {
    render(
      <StackedAgeBar
        groups={[
          { age_group: '30대', share: 0.4 },
          { age_group: '20대', share: 0.3 },
        ]}
      />,
    );
    expect(screen.getByText('30대')).toBeInTheDocument();
  });
  it('빈 배열이면 placeholder', () => {
    render(<StackedAgeBar groups={[]} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
