import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EntrySignalLight } from './EntrySignalLight';

describe('EntrySignalLight', () => {
  it('green → "진입 권장" 라벨', () => {
    render(<EntrySignalLight signal="green" />);
    expect(screen.getByText('진입 권장')).toBeInTheDocument();
  });
  it('yellow → "조건부 진입"', () => {
    render(<EntrySignalLight signal="yellow" />);
    expect(screen.getByText('조건부 진입')).toBeInTheDocument();
  });
  it('red → "진입 비권장"', () => {
    render(<EntrySignalLight signal="red" />);
    expect(screen.getByText('진입 비권장')).toBeInTheDocument();
  });
  it('null → placeholder 렌더', () => {
    render(<EntrySignalLight signal={null} />);
    expect(screen.getByText(/데이터 부재|competitor_intel 대기|—/)).toBeTruthy();
  });
});
