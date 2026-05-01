import { motion } from 'framer-motion';
import { Check, Minus } from 'lucide-react';
import type { Plan } from '../types';

interface Props {
  plan: Plan;
  onSelect: (id: Plan['id']) => void;
  isVisible: boolean;
}

export default function PricingCard({ plan, onSelect, isVisible }: Props) {
  return (
    <motion.div
      layout
      layoutId={`card-${plan.id}`}
      initial={{ opacity: 0, y: 30 }}
      animate={{
        opacity: isVisible ? 1 : 0,
        y: isVisible ? 0 : 20,
        scale: isVisible ? 1 : 0.95,
      }}
      whileHover={{ y: -8 }}
      transition={{ duration: 0.5, ease: [0.19, 1, 0.22, 1] }}
      className="group relative w-[340px] shrink-0 rounded-2xl overflow-hidden p-[2px]"
    >
      {/* 1. 회전하는 그라데이션 배경 (호버 시) */}
      <div
        className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{
          background:
            'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
        }}
      />

      {/* 2. 내부 카드 컨텐츠 */}
      <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] flex flex-col p-8 transition-colors duration-500">
        {/* Badge — 이름 + MOST POPULAR (Growth만) */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">{plan.badge}</span>
          <span className="text-[#e2e8f0] font-bold text-lg">{plan.name}</span>
          {plan.badgeLabel && (
            <span className="ml-auto px-2.5 py-0.5 rounded-full bg-[#818cf8]/10 border border-[#818cf8]/30 text-[#a5b4fc] text-[0.625rem] font-bold tracking-wider uppercase">
              {plan.badgeLabel}
            </span>
          )}
        </div>

        <p className="text-[#9ca3af] text-xs mb-6">{plan.target}</p>

        {/* Price */}
        <div className="flex items-baseline gap-1 mb-8">
          <span className="text-4xl font-bold text-[#e2e8f0] tabular-nums">{plan.price}</span>
          {plan.priceNote && <span className="text-[#9ca3af] text-sm">{plan.priceNote}</span>}
        </div>

        {/* Features */}
        <div className="flex flex-col gap-3 mb-8 flex-1">
          {plan.features.map((f, i) => (
            <div key={i} className="flex items-center gap-3 text-sm leading-relaxed">
              {f.included ? (
                <Check size={14} className="text-[#a5b4fc] shrink-0" />
              ) : (
                <Minus size={14} className="text-[#3a3633] shrink-0" />
              )}
              <span className={f.included ? 'text-[#9ca3af]' : 'text-[#3a3633]'}>{f.text}</span>
            </div>
          ))}
        </div>

        {/* CTA — 기본 스톤톤, 호버 시 인디고 점등 */}
        <button
          onClick={() => onSelect(plan.id)}
          className="w-full py-4 rounded-xl font-bold text-sm tracking-wider transition-all duration-300 bg-[#1e1b18] text-[#9ca3af] border border-[#3a3633] group-hover:bg-[#818cf8] group-hover:text-[#1e1b18] group-hover:border-transparent group-hover:shadow-[0_0_20px_rgba(129,140,248,0.4)] active:scale-[0.98]"
        >
          {plan.cta}
        </button>
      </div>
    </motion.div>
  );
}
