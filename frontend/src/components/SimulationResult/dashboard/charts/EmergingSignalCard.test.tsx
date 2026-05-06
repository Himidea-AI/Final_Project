import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmergingSignalCard } from './EmergingSignalCard';
import type { EmergingSignal } from '../../../../types';

const mkSignal = (overrides: Partial<EmergingSignal> = {}): EmergingSignal => ({
  dong_code: '11440680',
  industry_code: 'CS100002',
  anomaly_score: 0.5,
  signal: 'normal',
  consecutive_anomaly_quarters: 0,
  summary: '데이터 검증 중 — 안정 상권으로 가정',
  tier: 'none',
  raw: {},
  is_mock: true,
  ...overrides,
});

describe('EmergingSignalCard — 라벨 단어 사전', () => {
  it('"이상도" 표현 미노출', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" />);
    expect(screen.queryByText(/이상도/)).toBeNull();
  });

  it('KPI 라벨이 "평소 대비 변화"', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" />);
    expect(screen.getByText('평소 대비 변화')).toBeInTheDocument();
  });

  it('signal=normal 일 때 "안정 상권" 표시', () => {
    render(<EmergingSignalCard signal={mkSignal({ signal: 'normal' })} district="합정동" />);
    expect(screen.getByText('안정 상권')).toBeInTheDocument();
  });

  it('KPI 점수가 정수 0~100 스케일 (소수점 미노출)', () => {
    render(<EmergingSignalCard signal={mkSignal({ anomaly_score: 0.77 })} district="합정동" />);
    expect(screen.getByText('77')).toBeInTheDocument();
    expect(screen.queryByText('0.77')).toBeNull();
  });
});

describe('EmergingSignalCard — consecutive_anomaly_quarters chip', () => {
  it('consecutive=2 → "최근 2분기 연속" 노출', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ consecutive_anomaly_quarters: 2 })}
        district="합정동"
      />,
    );
    expect(screen.getByText(/최근 2분기 연속/)).toBeInTheDocument();
  });

  it('consecutive=0 → 분기 연속 라벨 미노출', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ consecutive_anomaly_quarters: 0 })}
        district="합정동"
      />,
    );
    expect(screen.queryByText(/분기 연속/)).toBeNull();
  });
});

describe('EmergingSignalCard — isTopChange 배지', () => {
  it('isTopChange=true → "변화 1위" 배지 노출', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" isTopChange />);
    expect(screen.getByText('변화 1위')).toBeInTheDocument();
  });

  it('isTopChange 미지정 → "변화 1위" 배지 미노출', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" />);
    expect(screen.queryByText('변화 1위')).toBeNull();
  });

  it('isTopChange=false → "변화 1위" 배지 미노출', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" isTopChange={false} />);
    expect(screen.queryByText('변화 1위')).toBeNull();
  });
});

describe('EmergingSignalCard — tier 헤더 배지', () => {
  it('change_ix → "공식 데이터" 배지', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'change_ix', is_mock: false })}
        district="합정동"
      />,
    );
    expect(screen.getByText('공식 데이터')).toBeInTheDocument();
  });

  it('classifier → "AI 판정" 배지', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'classifier', is_mock: false })}
        district="합정동"
      />,
    );
    expect(screen.getByText('AI 판정')).toBeInTheDocument();
  });

  it('b1_trend → "보조 신호" 배지', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'b1_trend', is_mock: false })}
        district="합정동"
      />,
    );
    expect(screen.getByText('보조 신호')).toBeInTheDocument();
  });

  it('slope → "보조 신호" 배지', () => {
    render(
      <EmergingSignalCard signal={mkSignal({ tier: 'slope', is_mock: false })} district="합정동" />,
    );
    expect(screen.getByText('보조 신호')).toBeInTheDocument();
  });

  it('none → "데이터 검증 중" 배지', () => {
    render(
      <EmergingSignalCard signal={mkSignal({ tier: 'none', is_mock: true })} district="합정동" />,
    );
    expect(screen.getByText('데이터 검증 중')).toBeInTheDocument();
    expect(screen.queryByText('데이터 신뢰도 검증 중')).toBeNull();
  });
});

describe('EmergingSignalCard — summary 한 줄', () => {
  it('signal.summary 문자열을 그대로 렌더', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'change_ix',
          is_mock: false,
          summary: '서울시 상권변화지표 기준 — 신흥 상권',
        })}
        district="합정동"
      />,
    );
    expect(screen.getByText('서울시 상권변화지표 기준 — 신흥 상권')).toBeInTheDocument();
  });
});

describe('EmergingSignalCard — quarter_history sparkline', () => {
  it('quarter_history 있을 때 "최근 8 분기 변화도" 라벨 노출', () => {
    const history = Array.from({ length: 8 }, (_, i) => ({
      quarter: i === 7 ? '현재' : `Q-${7 - i}`,
      anomaly_score: 0.3 + i * 0.05,
    }));
    render(
      <EmergingSignalCard signal={mkSignal({ quarter_history: history })} district="합정동" />,
    );
    expect(screen.getByText(/최근 8 분기 변화도/)).toBeInTheDocument();
  });

  it('quarter_history null → sparkline 라벨 미노출', () => {
    render(<EmergingSignalCard signal={mkSignal({ quarter_history: null })} district="합정동" />);
    expect(screen.queryByText(/최근 8 분기 변화도/)).toBeNull();
  });
});

describe('EmergingSignalCard — peer_distribution bar', () => {
  it('peer_distribution 있을 때 "16동 분포" 라벨 + 순위 노출', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          peer_distribution: {
            p25: 0.2,
            p50: 0.4,
            p75: 0.6,
            p90: 0.8,
            percentile_self: 25,
            rank_in_total: 4,
            total: 16,
          },
        })}
        district="합정동"
      />,
    );
    expect(screen.getByText(/16동 분포/)).toBeInTheDocument();
    expect(screen.getByText(/4 \/ 16위/)).toBeInTheDocument();
  });

  it('peer_distribution null → 16동 분포 라벨 미노출', () => {
    render(<EmergingSignalCard signal={mkSignal({ peer_distribution: null })} district="합정동" />);
    expect(screen.queryByText(/16동 분포/)).toBeNull();
  });
});
