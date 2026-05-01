import { Save } from 'lucide-react';

interface SaveButtonProps {
  onClick: () => void;
  disabled?: boolean;
  saved?: boolean; // true면 "저장됨" 상태로 시각 표시
  label?: string;
}

export function SaveButton({ onClick, disabled = false, saved = false, label }: SaveButtonProps) {
  const text = label ?? (saved ? '저장됨' : '저장');
  const cls = saved
    ? 'bg-success text-primary-foreground hover:bg-success/90'
    : 'bg-primary text-primary-foreground hover:bg-primary/90';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${cls}`}
    >
      <Save className="h-4 w-4" />
      <span>{text}</span>
    </button>
  );
}
