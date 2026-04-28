/**
 * AnalyzeAiSummaryTab — AI 분석 요약 (LLM 출처 통합 판단)
 *
 * 2026-04-28 IA 재구조 — SummaryTab 의 computeDecision + 창업 신호등 + synthesis 자연어 이관.
 *
 * 데이터 출처:
 *   - decision verdict: legal × entry signal 2D 매트릭스 (decisionThresholds SSOT)
 *   - entry signal: simResult.competitor_intel.market_entry_signal (green/yellow/red)
 *   - synthesis 자연어: simResult.final_report.summary || simResult.analysis_report
 *   - 최종 권고: simResult.final_report.final_recommendation || simResult.ai_recommendation
 *
 * 실데이터 원칙: 신호가 없으면 EntrySignalLight 가 "분석 대기" placeholder 자동 표시 (mock 'yellow' 주입 금지).
 */

import { BrainCircuit, ShieldAlert, AlertTriangle } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { EntrySignalLight } from '../../charts/EntrySignalLight';
import { DecisionCard } from '../../shared/DecisionCard';
import { NarrativeText } from '../../shared/NarrativeText';
import { computeDecision, DECISION_COPY } from '../../../../../constants/decisionThresholds';

interface Props {
  simResult: SimulationOutput;
}

const AGENT_ICON = {
  synthesis: { icon: BrainCircuit, color: 'text-white', borderCls: 'border-stone-300/60' },
  legal: { icon: AlertTriangle, color: 'text-rose-400', borderCls: 'border-rose-500/50' },
  competitor: { icon: ShieldAlert, color: 'text-amber-400', borderCls: 'border-amber-500/50' },
};

export function AnalyzeAiSummaryTab({ simResult }: Props) {
  const ci = simResult.competitor_intel as Record<string, any> | null | undefined;
  const legalRaw = simResult.overall_legal_risk ?? null;
  const entryRaw = (ci?.market_entry_signal as string | undefined) ?? null;

  const verdict = computeDecision(legalRaw, entryRaw);
  const verdictCopy = DECISION_COPY[verdict];
  const isVerdictUnknown = verdict === 'UNKNOWN';

  // EntrySignalLight 는 null/undefined 를 "분석 대기" placeholder 로 자동 처리 — mock fallback 주입 금지.
  const entrySignal = (ci?.market_entry_signal as 'green' | 'yellow' | 'red' | undefined) ?? null;

  const summary = simResult.final_report?.summary ?? simResult.analysis_report ?? '';
  const recommendation =
    simResult.final_report?.final_recommendation ?? simResult.ai_recommendation ?? '';

  return (
    <div className="space-y-6">
      {/* ═══ Row 1: Decision verdict + Entry signal ═══ */}
      <div className="grid grid-cols-3 gap-6">
        <DecisionCard
          title="LLM 출처 통합 판단"
          heroBadge={isVerdictUnknown ? verdictCopy.label : `${verdict} · ${verdictCopy.label}`}
          heroColor={verdictCopy.color}
          description={
            isVerdictUnknown
              ? '법률 분석 또는 경쟁 진입 신호 중 일부가 아직 수신되지 않았습니다. 해당 에이전트 실행이 완료되면 판정이 산출됩니다.'
              : '법률 리스크(safe/caution/danger) × 경쟁 진입 신호(green/yellow/red)의 2D 매트릭스로 GO / HOLD / STOP 3단계 판정을 도출합니다.'
          }
          items={[
            {
              text: `법률 리스크 ${legalRaw ?? '미수신'}`,
              highlight: legalRaw === 'safe',
            },
            {
              text: `진입 신호 ${entryRaw ?? '미수신'}`,
              highlight: entryRaw === 'green',
            },
            {
              text: `종합 판정 ${verdict}`,
              highlight: verdict === 'GO',
            },
          ]}
          footer={{
            agents: [AGENT_ICON.synthesis, AGENT_ICON.legal, AGENT_ICON.competitor].map((a, i) => ({
              id: `ai-summary-${i}`,
              ...a,
            })),
            methodology: 'synthesis + legal + competitor',
          }}
        />

        <div className="col-span-2 flex flex-col rounded-3xl border border-stone-800/60 bg-stone-900/40 p-6">
          <div className="mb-3 text-[10px] font-black uppercase tracking-widest text-stone-500">
            창업 진입 신호
          </div>
          <div className="flex flex-1 items-center">
            <EntrySignalLight signal={entrySignal} />
          </div>
        </div>
      </div>

      {/* ═══ synthesis 자연어 종합 ═══ */}
      {summary && (
        <div className="rounded-3xl border border-stone-800/60 bg-stone-900/40 p-8">
          <h4 className="mb-4 text-xs font-black uppercase tracking-widest text-stone-500">
            synthesis 종합 분석
          </h4>
          <NarrativeText text={summary} />
        </div>
      )}

      {/* ═══ 최종 권고 ═══ */}
      {recommendation && (
        <div className="rounded-3xl border border-indigo-500/20 bg-indigo-500/5 p-8">
          <h4 className="mb-4 text-xs font-black uppercase tracking-widest text-indigo-400">
            최종 권고
          </h4>
          <NarrativeText text={recommendation} />
        </div>
      )}
    </div>
  );
}
