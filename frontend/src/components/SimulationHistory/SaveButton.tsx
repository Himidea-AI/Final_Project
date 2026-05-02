import { Save } from 'lucide-react';

interface SaveButtonProps {
  onClick: () => void;
  disabled?: boolean;
  saved?: boolean; // true면 "저장됨" 상태로 시각 표시
  label?: string;
}

export function SaveButton({ onClick, disabled = false, saved = false, label }: SaveButtonProps) {
  const text = label ?? (saved ? '저장됨' : '저장');
  // DashboardHub 의 "분석 조건" 버튼과 동일 사이즈/모양 (rounded-xl, px-5 py-2.5, text-sm font-bold).
  // 색만 분기 — primary(저장) / success(저장됨).
  const cls = saved
    ? 'bg-success text-primary-foreground hover:bg-success/90'
    : 'bg-primary text-primary-foreground hover:bg-primary/90';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold tracking-wider transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-40 ${cls}`}
    >
      <Save className="h-4 w-4" />
      <span>{text}</span>
    </button>
  );
}
