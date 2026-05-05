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

  it('게이지 좌우 라벨 "낮음" / "높음"', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" />);
    expect(screen.getByText('낮음')).toBeInTheDocument();
    expect(screen.getByText('높음')).toBeInTheDocument();
  });

  it('게이지 우측 값이 정수 0~100 스케일 (KPI와 동일)', () => {
    render(<EmergingSignalCard signal={mkSignal({ anomaly_score: 0.77 })} district="합정동" />);
    // KPI 박스의 "77" + 게이지 우측 라벨 "77" 두 위치 모두 정수 노출
    expect(screen.getAllByText('77').length).toBeGreaterThanOrEqual(2);
    // 소수점 표기 미노출
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

  it('none → "데이터 검증 중" 배지 (is_mock 별도 미렌더)', () => {
    render(
      <EmergingSignalCard signal={mkSignal({ tier: 'none', is_mock: true })} district="합정동" />,
    );
    expect(screen.getByText('데이터 검증 중')).toBeInTheDocument();
    // is_mock 별도 배지 흡수 — "데이터 신뢰도 검증 중" 미노출
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

describe('EmergingSignalCard — raw evidence chip', () => {
  it('classifier → "신뢰도 87%" chip', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'classifier',
          raw: { predicted_stage: 'LH', confidence: 0.87 },
          is_mock: false,
        })}
        district="합정동"
      />,
    );
    expect(screen.getByText(/신뢰도/)).toBeInTheDocument();
    expect(screen.getByText(/87%/)).toBeInTheDocument();
  });

  it('b1_trend → "지하철" + "청년" chip 2개', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'b1_trend',
          raw: { subway_growth: 0.05, migration_2030_rate: 0.02 },
          is_mock: false,
        })}
        district="합정동"
      />,
    );
    expect(screen.getByText(/지하철 \+5\.0%/)).toBeInTheDocument();
    expect(screen.getByText(/청년 \+2\.0%/)).toBeInTheDocument();
  });

  it('slope → "매출 ↑" + "점포수 →" 부호 chip', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'slope',
          raw: { sales_slope: 1.2, store_slope: 0.0 },
          is_mock: false,
        })}
        district="합정동"
      />,
    );
    expect(screen.getByText(/매출 ↑/)).toBeInTheDocument();
    expect(screen.getByText(/점포수 →/)).toBeInTheDocument();
  });

  it('change_ix → chip 미렌더 (summary 만으로 충분)', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'change_ix',
          raw: { change_ix: 'LH' },
          is_mock: false,
        })}
        district="합정동"
      />,
    );
    expect(screen.queryByText(/LH/)).toBeNull();
  });

  it('none → chip 미렌더', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'none', raw: {}, is_mock: true })}
        district="합정동"
      />,
    );
    expect(screen.queryByText(/지하철|청년|매출|점포수|신뢰도/)).toBeNull();
  });

  it('b1_trend 에서 raw 키 일부 누락 시 누락 chip 미렌더', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'b1_trend',
          raw: { subway_growth: 0.05 },
          is_mock: false,
        })}
        district="합정동"
      />,
    );
    expect(screen.getByText(/지하철 \+5\.0%/)).toBeInTheDocument();
    expect(screen.queryByText(/청년/)).toBeNull();
  });
});
