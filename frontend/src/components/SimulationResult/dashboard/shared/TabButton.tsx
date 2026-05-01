import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';

export type TabAccent = 'primary' | 'chart-2' | 'chart-3' | 'chart-4' | 'hot-pink';

interface TabButtonProps {
  id: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  onClick: (id: string) => void;
  /**
   * 탭별 정체성 색 — 활성 시 텍스트/하단 indicator 가 이 색.
   * 12색 시스템 안에서 카테고리별 의미 매핑 (예: AI=Vibrant Purple, 법률=Vivid Red).
   * 미지정 시 primary (Deep Blue).
   */
  accent?: TabAccent;
}

const ACCENT: Record<TabAccent, { text: string; bg: string; shadow: string }> = {
  primary: {
    text: 'text-primary',
    bg: 'bg-primary',
    shadow: 'shadow-[0_0_8px_rgb(0,44,209,0.35)]',
  },
  'chart-2': {
    text: 'text-chart-2',
    bg: 'bg-chart-2',
    shadow: 'shadow-[0_0_8px_rgb(255,56,0,0.30)]',
  },
  'chart-3': {
    text: 'text-chart-3',
    bg: 'bg-chart-3',
    shadow: 'shadow-[0_0_8px_rgb(0,186,122,0.30)]',
  },
  'chart-4': {
    text: 'text-chart-4',
    bg: 'bg-chart-4',
    shadow: 'shadow-[0_0_8px_rgb(179,92,255,0.35)]',
  },
  'hot-pink': {
    text: 'text-decor-hot-pink',
    bg: 'bg-decor-hot-pink',
    shadow: 'shadow-[0_0_8px_rgb(255,0,112,0.30)]',
  },
};

export function TabButton({
  id,
  label,
  icon: Icon,
  active,
  onClick,
  accent = 'primary',
}: TabButtonProps) {
  const a = ACCENT[accent];
  return (
    <button
      type="button"
      onClick={() => onClick(id)}
      className={`flex items-center gap-2 px-6 py-4 text-sm font-bold transition-all relative ${
        active ? a.text : 'text-muted-foreground hover:text-foreground'
      }`}
    >
      <Icon size={16} />
      {label}
      {active && (
        <motion.div
          layoutId="activeTabIndicator"
          className={`absolute bottom-0 left-0 right-0 h-[3px] rounded-t-full ${a.bg} ${a.shadow}`}
        />
      )}
    </button>
  );
}
