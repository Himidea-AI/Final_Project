import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { LegalDrawer } from './LegalDrawer';

const mockRisk = {
  type: '가맹사업법',
  risk_level: 'HIGH' as const,
  articles: [
    { article_ref: '가맹사업법 제5조', content: '가맹본부의 의무...', kind: 'article' as const },
    { article_ref: '가맹사업법 제9조', content: '정보공개서...' },
    {
      article_ref: '대법원 2019다12345',
      content: '정보공개서 미제공 시 계약 해지 인정...',
      kind: 'precedent' as const,
    },
  ],
  checklist: [{ text: '정보공개서 수령', isRequired: true }],
  recommendation: '계약 전 14일 숙고기간 확보',
};

const mockRiskNoPrecedent = {
  type: '식품위생법',
  risk_level: 'MEDIUM' as const,
  articles: [{ article_ref: '식품위생법 제37조', content: '영업허가...' }],
};

describe('LegalDrawer', () => {
  it('open 시 조항 본문·체크리스트·권고 모두 렌더', () => {
    render(<LegalDrawer risk={mockRisk} open={true} onClose={() => {}} />);
    expect(screen.getByText('가맹사업법')).toBeInTheDocument();
    expect(screen.getByText('조항 본문')).toBeInTheDocument();
    expect(screen.getByText('가맹사업법 제5조')).toBeInTheDocument();
    // kind 미설정 → default 'article' 처리 검증
    expect(screen.getByText('가맹사업법 제9조')).toBeInTheDocument();
    expect(screen.getByText('정보공개서 수령')).toBeInTheDocument();
    expect(screen.getByText(/14일 숙고기간/)).toBeInTheDocument();
  });

  it('precedent 항목은 "참고 판례" 섹션에 분리되어 렌더', () => {
    render(<LegalDrawer risk={mockRisk} open={true} onClose={() => {}} />);
    expect(screen.getByText('참고 판례')).toBeInTheDocument();
    expect(screen.getByText('대법원 2019다12345')).toBeInTheDocument();
    // 판례는 조항 섹션에 섞이지 않아야 함 (ref가 조항 본문 아래에 노출되더라도 헤더는 분리)
  });

  it('precedent 0건이면 "참고 판례" 섹션 미표시', () => {
    render(<LegalDrawer risk={mockRiskNoPrecedent} open={true} onClose={() => {}} />);
    expect(screen.getByText('조항 본문')).toBeInTheDocument();
    expect(screen.queryByText('참고 판례')).not.toBeInTheDocument();
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
