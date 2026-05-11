import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { InfoTooltip } from './InfoTooltip';

type Props = {
  label: string;
  icon?: LucideIcon;
  info?: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
  /**
   * true → field 전체를 카드 외피(border + bg + padding)로 감쌈.
   * 작은 옵션(목표 객단가, 연령대, 성별 등)은 boxed=true 로 큰 옵션(분석 대상/업종)과 동일한
   * 시각 단위로 보이게 함. 큰 강조 박스 안에 들어가는 자리만 boxed=false.
   */
  boxed?: boolean;
};

/**
 * 옵션 화면의 모든 form field 외피.
 * - 상단: 아이콘 + 라벨 (검정 14px bold) + ⓘ 툴팁 (선택)
 * - 우측: hint/배지 (작은 muted 텍스트 — "복수 선택", "선택됨" 등)
 * - 하단: control slot (children)
 *
 * 모든 옵션이 동일한 외피로 감싸지면서 설문지 일관성을 만듭니다.
 */
export function FormField({
  label,
  icon: Icon,
  info,
  hint,
  children,
  className = '',
  boxed = false,
}: Props) {
  const wrapperCls = boxed
    ? `flex flex-col gap-2 rounded-xl border border-border bg-card/60 p-4 ${className}`
    : `flex flex-col gap-2 ${className}`;

  return (
    <div className={wrapperCls}>
      <div className="flex items-center justify-between gap-2 min-h-[20px]">
        <div className="flex items-center gap-1.5 min-w-0">
          {Icon ? <Icon size={13} className="text-primary shrink-0" /> : null}
          <label className="text-xs font-bold text-foreground tracking-tight truncate">
            {label}
          </label>
          {info ? <InfoTooltip text={info} /> : null}
        </div>
        {hint ? (
          <span className="text-[11px] text-muted-foreground shrink-0 font-medium">{hint}</span>
        ) : null}
      </div>
      <div>{children}</div>
    </div>
  );
}
