/**
 * AIVerdictBanner — 킬러 인사이트 메인 상단 한 줄 평
 *
 * 시뮬레이터 결과 화면 최상단에 배치.
 * synthesis_node의 ai_verdict 또는 summary 필드를 표시.
 * 직영/가맹 분기 + severity 색상 분기.
 */

import { Zap, Shield, AlertTriangle, TrendingUp } from "lucide-react";

type Severity = "positive" | "neutral" | "warning" | "critical";

interface AIVerdictBannerProps {
  headline: string;
  severity: Severity;
  reason?: string;
  isDirect?: boolean;
}

const SEVERITY_CONFIG: Record<
  Severity,
  { icon: React.ReactNode; borderColor: string; bgColor: string; textColor: string; glowColor: string }
> = {
  positive: {
    icon: <TrendingUp className="w-5 h-5" />,
    borderColor: "border-emerald-500/40",
    bgColor: "bg-emerald-500/[0.06]",
    textColor: "text-emerald-400",
    glowColor: "shadow-[0_0_30px_rgba(16,185,129,0.1)]",
  },
  neutral: {
    icon: <Shield className="w-5 h-5" />,
    borderColor: "border-[#818cf8]/40",
    bgColor: "bg-[#818cf8]/[0.06]",
    textColor: "text-[#818cf8]",
    glowColor: "shadow-[0_0_30px_rgba(129,140,248,0.1)]",
  },
  warning: {
    icon: <AlertTriangle className="w-5 h-5" />,
    borderColor: "border-amber-500/40",
    bgColor: "bg-amber-500/[0.06]",
    textColor: "text-amber-400",
    glowColor: "shadow-[0_0_30px_rgba(245,158,11,0.1)]",
  },
  critical: {
    icon: <AlertTriangle className="w-5 h-5" />,
    borderColor: "border-rose-500/40",
    bgColor: "bg-rose-500/[0.06]",
    textColor: "text-rose-400",
    glowColor: "shadow-[0_0_30px_rgba(244,63,94,0.1)]",
  },
};

export default function AIVerdictBanner({
  headline,
  severity,
  reason,
  isDirect,
}: AIVerdictBannerProps) {
  const config = SEVERITY_CONFIG[severity];

  return (
    <div
      className={`rounded-xl border p-5 ${config.borderColor} ${config.bgColor} ${config.glowColor} transition-all`}
    >
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div
          className={`shrink-0 mt-0.5 ${config.textColor}`}
        >
          {isDirect ? <Shield className="w-5 h-5" /> : config.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Tag */}
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-3 h-3 text-[#818cf8]" />
            <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-[#818cf8]">
              AI VERDICT
            </span>
            {isDirect && (
              <span className="px-2 py-0.5 text-[9px] font-bold bg-[#818cf8]/15 text-[#818cf8] border border-[#818cf8]/30 rounded-full">
                직영 브랜드
              </span>
            )}
          </div>

          {/* Headline */}
          <h2 className="text-lg font-black text-[#e2e8f0] leading-snug mb-1">
            {headline}
          </h2>

          {/* Reason */}
          {reason && (
            <p className="text-xs text-[#9ca3af] leading-relaxed">
              {reason}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
