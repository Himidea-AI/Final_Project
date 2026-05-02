import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { LegalDrawer } from './LegalDrawer';

const mockRisk = {
  type: '가맹사업법',
  risk_level: 'HIGH' as const,
  articles: [
    { article_ref: '가맹사업법 제5조', content: '가맹본부의 의무...' },
    { article_ref: '가맹사업법 제9조', content: '정보공개서...' },
  ],
  checklist: [{ text: '정보공개서 수령', isRequired: true }],
  recommendation: '계약 전 14일 숙고기간 확보',
};

describe('LegalDrawer', () => {
  it('open 시 조항 본문·체크리스트·권고 모두 렌더', () => {
    render(<LegalDrawer risk={mockRisk} open={true} onClose={() => {}} />);
    expect(screen.getByText('가맹사업법')).toBeInTheDocument();
    expect(screen.getByText('가맹사업법 제5조')).toBeInTheDocument();
    expect(screen.getByText('정보공개서 수령')).toBeInTheDocument();
    expect(screen.getByText(/14일 숙고기간/)).toBeInTheDocument();
  });

  it('X 버튼 클릭 시 onClose 호출', () => {
    const onClose = vi.fn();
    render(<LegalDrawer risk={mockRisk} open={true} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText('닫기'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('open=false 시 렌더 안 함', () => {
    render(<LegalDrawer risk={mockRisk} open={false} onClose={() => {}} />);
    expect(screen.queryByText('가맹사업법')).not.toBeInTheDocument();
  });

  it('체크박스 토글 가능 + localStorage 영속화', () => {
    window.localStorage.clear();
    render(<LegalDrawer risk={mockRisk} open={true} onClose={() => {}} />);
    const cb = screen.getByLabelText('정보공개서 수령') as HTMLInputElement;
    expect(cb.disabled).toBe(false);
    expect(cb.checked).toBe(false);
    fireEvent.click(cb);
    expect(cb.checked).toBe(true);
    const stored = window.localStorage.getItem('legal-checklist-v1:가맹사업법');
    expect(stored).toBeTruthy();
    expect(stored).toContain('정보공개서 수령');
  });

  it('재오픈 시 저장된 체크 상태 복원', () => {
    window.localStorage.setItem(
      'legal-checklist-v1:가맹사업법',
      JSON.stringify({ '0:정보공개서 수령': true }),
    );
    render(<LegalDrawer risk={mockRisk} open={true} onClose={() => {}} />);
    const cb = screen.getByLabelText('정보공개서 수령') as HTMLInputElement;
    expect(cb.checked).toBe(true);
  });
});
