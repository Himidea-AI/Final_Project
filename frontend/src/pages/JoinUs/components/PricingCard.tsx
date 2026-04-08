import { motion } from "framer-motion";
import { Check, Minus } from "lucide-react";
import type { Plan } from "../types";

interface Props {
  plan: Plan;
  onSelect: (id: Plan["id"]) => void;
  isVisible: boolean;
}

export default function PricingCard({ plan, onSelect, isVisible }: Props) {
  const isGrowth = plan.highlighted;

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
      transition={{ duration: 0.5, ease: [0.19, 1, 0.22, 1] }}
      className={`relative w-[340px] shrink-0 rounded-2xl border p-8 flex flex-col transition-all duration-300 hover:-translate-y-1 ${
        isGrowth
          ? "bg-[#141414] border-[#818cf8] shadow-[0_0_30px_rgba(99,102,241,0.15)]"
          : "bg-[#141414] border-[#262626] hover:border-[#404040]"
      }`}
    >
      {/* Badge */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-lg">{plan.badge}</span>
        <span className="text-[#fafafa] font-bold text-lg">{plan.name}</span>
        {plan.badgeLabel && (
          <span className="ml-auto px-2.5 py-0.5 rounded-full bg-[#818cf8]/10 border border-[#818cf8]/30 text-[#a5b4fc] text-[10px] font-bold tracking-wider uppercase">
            {plan.badgeLabel}
          </span>
        )}
      </div>

      <p className="text-[#a1a1aa] text-xs mb-6">{plan.target}</p>

      {/* Price */}
      <div className="flex items-baseline gap-1 mb-8">
        <span className="text-4xl font-bold text-[#fafafa] tabular-nums">
          {plan.price}
        </span>
        {plan.priceNote && (
          <span className="text-[#a1a1aa] text-sm">{plan.priceNote}</span>
        )}
      </div>

      {/* Features */}
      <div className="flex flex-col gap-3 mb-8 flex-1">
        {plan.features.map((f, i) => (
          <div key={i} className="flex items-center gap-3 text-sm leading-relaxed">
            {f.included ? (
              <Check size={14} className="text-[#a5b4fc] shrink-0" />
            ) : (
              <Minus size={14} className="text-[#404040] shrink-0" />
            )}
            <span className={f.included ? "text-[#a1a1aa]" : "text-[#404040]"}>
              {f.text}
            </span>
          </div>
        ))}
      </div>

      {/* CTA */}
      <button
        onClick={() => onSelect(plan.id)}
        className={`w-full py-3 rounded-xl font-bold text-sm tracking-wider transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] ${
          isGrowth
            ? "bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white shadow-[0_0_20px_rgba(99,102,241,0.3)]"
            : "bg-[#262626] text-[#fafafa] border border-[#333333] hover:bg-[#333333]"
        }`}
      >
        {plan.cta}
      </button>

      {/* Ambient glow for Growth */}
      {isGrowth && (
        <div
          className="absolute -inset-px rounded-2xl pointer-events-none"
          style={{
            background:
              "linear-gradient(135deg, rgba(99,102,241,0.08), transparent, rgba(99,102,241,0.05))",
            animation: "energy-pulse 3s ease-in-out infinite",
          }}
        />
      )}
    </motion.div>
  );
}
