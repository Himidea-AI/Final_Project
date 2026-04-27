import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { LegalDistributionBar, countByLevel } from './LegalDistributionBar';
import type { LegalRisk } from '../../../../types';

describe('countByLevel', () => {
  it('각 등급 건수 카운트 (대소문자 무시)', () => {
    const risks: LegalRisk[] = [
      { type: 't', risk_level: 'HIGH', detail: '' },
      { type: 't', risk_level: 'danger', detail: '' },
      { type: 't', risk_level: 'MEDIUM', detail: '' },
      { type: 't', risk_level: 'low', detail: '' },
    ];
    const counts = countByLevel(risks);
    expect(counts.high).toBe(2);
    expect(counts.medium).toBe(1);
    expect(counts.low).toBe(1);
  });
  it('빈 배열 → 모두 0', () => {
    const counts = countByLevel([]);
    expect(counts.high).toBe(0);
    expect(counts.medium).toBe(0);
    expect(counts.low).toBe(0);
  });
  it('is_fallback 카운트 분리', () => {
    const risks: LegalRisk[] = [
      { type: 't', risk_level: 'HIGH', detail: '' },
      { type: 't', risk_level: 'HIGH', detail: '', is_fallback: true },
    ];
    const counts = countByLevel(risks);
    expect(counts.high).toBe(2);
    expect(counts.fallback).toBe(1);
  });
});

describe('LegalDistributionBar', () => {
  it('건수 있으면 라벨 렌더', () => {
    const risks: LegalRisk[] = [
      { type: 't', risk_level: 'HIGH', detail: '' },
      { type: 't', risk_level: 'MEDIUM', detail: '' },
    ];
    render(<LegalDistributionBar risks={risks} />);
    expect(screen.getByText(/필수이행/)).toBeInTheDocument();
    expect(screen.getByText(/확인필요/)).toBeInTheDocument();
  });
  it('빈 배열 → placeholder', () => {
    render(<LegalDistributionBar risks={[]} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
