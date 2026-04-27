/**
 * GradeCard — 헤더 우측 Premium Grade 카드 (참고 v4.3 배치)
 *
 * analysis_metrics.district_grade → A+/B+/C+/D 매핑.
 * 신뢰도는 agent_attributions[synthesis].confidence × 100.
 */

interface GradeCardProps {
  letter: string;
  /** Tailwind color 토큰 (emerald/indigo/amber/rose/stone) */
  color: string;
  /** 신뢰도 % (0~100) */
  confidencePct: number | null;
}

const COLOR_CLS: Record<string, { gradient: string; text: string; border: string; glow: string }> =
  {
    emerald: {
      gradient: 'from-emerald-500/10',
      text: 'text-emerald-400',
      border: 'border-emerald-500/20',
      glow: 'drop-shadow-[0_0_15px_rgba(16,185,129,0.3)]',
    },
    indigo: {
      gradient: 'from-indigo-500/10',
      text: 'text-indigo-400',
      border: 'border-indigo-500/20',
      glow: 'drop-shadow-[0_0_15px_rgba(99,102,241,0.3)]',
    },
    amber: {
      gradient: 'from-amber-500/10',
      text: 'text-amber-400',
      border: 'border-amber-500/20',
      glow: 'drop-shadow-[0_0_15px_rgba(245,158,11,0.3)]',
    },
    rose: {
      gradient: 'from-rose-500/10',
      text: 'text-rose-400',
      border: 'border-rose-500/20',
      glow: 'drop-shadow-[0_0_15px_rgba(244,63,94,0.3)]',
    },
    stone: {
      gradient: 'from-stone-700/10',
      text: 'text-stone-400',
      border: 'border-stone-700/30',
      glow: '',
    },
  };

export function GradeCard({ letter, color, confidencePct }: GradeCardProps) {
  const cls = COLOR_CLS[color] ?? COLOR_CLS.stone;
  return (
    <div
      className={`bg-gradient-to-br ${cls.gradient} to-transparent ${cls.border} border rounded-2xl p-6 w-32 text-center flex flex-col justify-center shadow-2xl shrink-0`}
    >
      <div
        className={`text-[10px] font-black ${cls.text} opacity-60 uppercase tracking-widest mb-1`}
      >
        GRADE
      </div>
      <div className={`text-5xl font-black ${cls.text} tracking-tighter ${cls.glow}`}>{letter}</div>
      {confidencePct != null && (
        <div className="mt-2 text-[10px] font-bold text-stone-500 tracking-tighter">
          신뢰도 {confidencePct}%
        </div>
      )}
    </div>
  );
}
