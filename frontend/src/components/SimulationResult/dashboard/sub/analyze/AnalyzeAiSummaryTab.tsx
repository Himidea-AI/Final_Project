/**
 * AnalyzeAiSummaryTab — AI 분석 요약 (LLM 출처 통합 판단)
 *
 * 2026-04-28 IA 재구조 — SummaryTab 의 computeDecision + 창업 신호등 + synthesis 자연어 이관.
 * 2026-04-28 H6 — LLM 산출 "1등 추천 동" + Top 3 칩 카드 추가.
 *
 * 데이터 출처:
 *   - 1등 추천 동: simResult.winner_district (district_ranking 에이전트 산출)
 *   - Top 3 후보: simResult.top_3_candidates (district_ranking 에이전트 산출)
 *   - decision verdict: legal × entry signal 2D 매트릭스 (decisionThresholds SSOT)
 *   - entry signal: simResult.competitor_intel.market_entry_signal (green/yellow/red)
 *   - synthesis 자연어: simResult.final_report.summary || simResult.analysis_report
 *   - 최종 권고: simResult.final_report.final_recommendation || simResult.ai_recommendation
 *
 * 실데이터 원칙: 신호가 없으면 EntrySignalLight 가 "분석 대기" placeholder 자동 표시 (mock 'yellow' 주입 금지).
 *   winner_district 가 없으면 추천 동 카드 자체를 hide (값 없으면 — 표시 정책 + 빈 자리 어색 회피).
 */

import { BrainCircuit, ShieldAlert, AlertTriangle, MapPin, Trophy } from 'lucide-react';
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

  // ═══ H6 — 1등 추천 동 + Top 3 (district_ranking 산출) ═══
  // winner_district 는 LLM 이 산출한 1순위. target_district 는 사용자 입력 — 명확히 구분.
  const winnerDistrict = simResult.winner_district?.trim() || null;
  const topCandidatesRaw = Array.isArray(simResult.top_3_candidates)
    ? simResult.top_3_candidates.filter(
        (d): d is string => typeof d === 'string' && d.trim() !== '',
      )
    : [];
  // Top 3 칩에서 1등 강조 표시할 수 있도록 정렬 유지 (백엔드 순서 = 랭킹 순서)
  const topCandidates = topCandidatesRaw.length > 0 ? topCandidatesRaw : null;
  const showTopChips = topCandidates !== null && topCandidates.length >= 2;
  // 1등 동 한줄 요약 — winner_district 의 DistrictRanking 엔트리에서 추출 (있을 때만)
  const winnerRanking = winnerDistrict
    ? simResult.district_rankings?.find((r) => r.district === winnerDistrict)
    : undefined;
  const winnerSubText = (() => {
    if (!winnerDistrict) return null;
    if (winnerRanking?.score != null) {
      return `종합 점수 ${winnerRanking.score.toFixed(1)} · 추천 1순위 입지`;
    }
    return '추천 1순위 입지';
  })();

  return (
    <div className="space-y-6">
      {/* ═══ H6: 1등 추천 동 카드 (winner_district 있을 때만) ═══ */}
      {winnerDistrict && (
        <div className="rounded-3xl border border-indigo-500/30 bg-gradient-to-br from-indigo-500/10 via-stone-900/40 to-stone-900/40 p-8">
          <div className="flex items-start justify-between gap-6">
            <div className="flex-1">
              <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-indigo-300">
                <Trophy className="h-3.5 w-3.5" />
                추천 1순위
              </div>
              <div className="flex items-baseline gap-3">
                <span className="text-5xl font-black tracking-tight text-indigo-300">
                  {winnerDistrict}
                </span>
                {simResult.target_district && simResult.target_district !== winnerDistrict && (
                  <span className="text-xs text-stone-500">
                    (요청 동: {simResult.target_district})
                  </span>
                )}
              </div>
              {winnerSubText && <div className="mt-2 text-sm text-stone-400">{winnerSubText}</div>}
            </div>
            <MapPin className="h-10 w-10 shrink-0 text-indigo-400/60" />
          </div>

          {showTopChips && (
            <div className="mt-6 flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-black uppercase tracking-widest text-stone-500">
                Top {topCandidates!.length}
              </span>
              {topCandidates!.map((d, i) => {
                const isWinner = d === winnerDistrict;
                return (
                  <span
                    key={`${d}-${i}`}
                    className={
                      isWinner
                        ? 'rounded-full border border-indigo-400/60 bg-indigo-500/20 px-3 py-1 text-xs font-bold text-indigo-200'
                        : 'rounded-full border border-stone-700 bg-stone-800/60 px-3 py-1 text-xs text-stone-300'
                    }
                  >
                    {i + 1}. {d}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}

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
