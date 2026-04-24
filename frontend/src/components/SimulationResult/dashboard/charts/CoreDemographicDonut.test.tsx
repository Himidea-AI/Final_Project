import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CoreDemographicDonut } from './CoreDemographicDonut';

describe('CoreDemographicDonut', () => {
  it('core 데이터 있으면 라벨 + share 렌더', () => {
    render(<CoreDemographicDonut core={{ age: '30대', gender: '여성', share: 0.42 }} />);
    expect(screen.getByText(/30대.*여성|30대 여성/)).toBeInTheDocument();
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });
  it('core null이면 placeholder 렌더', () => {
    render(<CoreDemographicDonut core={null} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
