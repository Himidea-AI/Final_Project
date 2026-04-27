import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { BulletChart, qualitativeBand } from './BulletChart';

describe('qualitativeBand', () => {
  it('70 이상 → good', () => {
    expect(qualitativeBand(80, [40, 70])).toBe('good');
  });
  it('40-70 → ok', () => {
    expect(qualitativeBand(55, [40, 70])).toBe('ok');
  });
  it('40 미만 → bad', () => {
    expect(qualitativeBand(20, [40, 70])).toBe('bad');
  });
});

describe('BulletChart', () => {
  it('actual 값 표시', () => {
    render(<BulletChart actual={72} target={70} max={100} label="유동인구" />);
    expect(screen.getByText('72')).toBeInTheDocument();
    expect(screen.getByText('유동인구')).toBeInTheDocument();
  });
  it('actual null이면 "—"', () => {
    render(<BulletChart actual={null} target={70} max={100} label="유동인구" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
