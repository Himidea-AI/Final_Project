import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';

interface TabButtonProps {
  id: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  onClick: (id: string) => void;
}

export function TabButton({ id, label, icon: Icon, active, onClick }: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={() => onClick(id)}
      className={`flex items-center gap-2 px-6 py-4 text-sm font-bold transition-all relative ${
        active ? 'text-indigo-400' : 'text-stone-500 hover:text-stone-300'
      }`}
    >
      <Icon size={16} />
      {label}
      {active && (
        <motion.div
          layoutId="activeTabIndicator"
          className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.6)]"
        />
      )}
    </button>
  );
}
