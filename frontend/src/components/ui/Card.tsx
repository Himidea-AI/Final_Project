import type { ReactNode } from 'react';

type Props = {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  /**
   * 'plain' (default) — bg-card + border + shadow-sm. T2 nested 카드, 일반 패널.
   * 'glass' — `.box-glass` painted glass (multi-bg shine + multi-shadow + ::before conic).
   *           T1 hero wrapper. 페이지당 5~10 개 권장 (효과 흐려짐 + 성능).
   *           glass-on-glass 금지 (안에 또 glass 카드 X — 시각 위계 무너짐).
   */
  variant?: 'plain' | 'glass';
};

/**
 * Light SaaS card primitive — 통일 룰: rounded-2xl 만 사용.
 * T3 (테이블 row, 리스트 아이템) 은 Card 안 쓰고 직접 처리.
 */
export function Card({ children, className = '', padded = false, variant = 'plain' }: Props) {
  const base =
    variant === 'glass'
      ? 'box-glass rounded-2xl'
      : 'bg-card rounded-2xl border border-border shadow-sm';
  const pad = padded ? 'p-5' : '';
  return <div className={`${base} ${pad} ${className}`}>{children}</div>;
}
