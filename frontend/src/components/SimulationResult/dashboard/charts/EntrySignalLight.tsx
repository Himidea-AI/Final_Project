import { CheckCircle2, AlertCircle, XCircle, HelpCircle } from 'lucide-react';

export type EntrySignal = 'green' | 'yellow' | 'red';

const SIGNAL_META: Record<
  EntrySignal,
  { label: string; colorBg: string; colorText: string; Icon: typeof CheckCircle2 }
> = {
  green: {
    label: '진입 권장',
    colorBg: 'bg-emerald-500/10 border-emerald-500/40',
    colorText: 'text-emerald-400',
    Icon: CheckCircle2,
  },
  yellow: {
    label: '조건부 진입',
    colorBg: 'bg-amber-500/10 border-amber-500/40',
    colorText: 'text-amber-400',
    Icon: AlertCircle,
  },
  red: {
    label: '진입 비권장',
    colorBg: 'bg-rose-500/10 border-rose-500/40',
    colorText: 'text-rose-400',
    Icon: XCircle,
  },
};

interface Props {
  signal: EntrySignal | null | undefined;
}

export function EntrySignalLight({ signal }: Props) {
  if (!signal || !(signal in SIGNAL_META)) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl border border-dashed border-stone-700 bg-stone-900/40 text-stone-500 text-xs">
        <HelpCircle size={14} />
        <span>competitor_intel 분석 대기 — 데이터 부재</span>
      </div>
    );
  }
  const meta = SIGNAL_META[signal];
  const Icon = meta.Icon;
  return (
    <div className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border ${meta.colorBg}`}>
      <Icon className={meta.colorText} size={18} />
      <div className="flex flex-col">
        <span className={`text-[0.625rem] font-black uppercase tracking-widest ${meta.colorText}`}>
          Entry Signal
        </span>
        <span className={`text-sm font-black ${meta.colorText}`}>{meta.label}</span>
      </div>
    </div>
  );
}
