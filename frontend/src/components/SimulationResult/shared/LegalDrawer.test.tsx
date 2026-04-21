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
});
