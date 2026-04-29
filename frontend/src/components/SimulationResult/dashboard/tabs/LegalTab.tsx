/**
 * LegalTab — 법률·규제 전용 탭
 *
 * MarketTab에서 법률 섹션 이관. 가맹사업법·임대차보호법 등 규제 리스크를
 * 전용 공간에서 드릴다운할 수 있도록 분리. 본부 영업팀 법무 확인용.
 *
 * 2026-04-29 IM3-263 — AnalyzeAiSummaryTab의 LLM 출처 통합 판단 카드(legal × entry 2D)를
 *   법률 탭 최상단으로 이관. 법률 리스크 등급과 진입 신호를 같은 화면에서 종합 판정.
 *
 * 구성:
 * 1) 최상단: LLM 출처 통합 판단 (legal × entry → GO/HOLD/STOP)
 * 2) 헤더: 위험/안전 카운트 + 전체 리포트 보기
 * 3) 등급 분포 막대 (HIGH/MEDIUM/LOW 한눈에)
 * 4) 하단: InsightsGrid legalOnly — 표 + LegalDrawer 상세
 */

import { AlertTriangle, BrainCircuit, Maximize2, ShieldAlert } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { InsightsGrid } from '../../sections/InsightsGrid';
import { LegalDistributionBar } from '../charts/LegalDistributionBar';
import { DecisionCard } from '../shared/DecisionCard';
import { computeDecision, DECISION_COPY } from '../../../../constants/decisionThresholds';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

const AGENT_ICON = {
  synthesis: { icon: BrainCircuit, color: 'text-white', borderCls: 'border-stone-300/60' },
  legal: { icon: AlertTriangle, color: 'text-rose-400', borderCls: 'border-rose-500/50' },
  competitor: { icon: ShieldAlert, color: 'text-amber-400', borderCls: 'border-amber-500/50' },
};

// risk_level 두 패턴 정규화 — InsightsGrid.normalizeLevel 와 동일 매핑
function isHazard(level: string): boolean {
  const up = level.toUpperCase();
  return up === 'HIGH' || up === 'DANGER' || up === 'MEDIUM' || up === 'CAUTION';
}

export function LegalTab({ simResult, openModal }: Props) {
  const risks = simResult.legal_risks ?? [];
  const totalCount = risks.length;
  const hazardCount = risks.filter((r) => isHazard(r.risk_level)).length;
  const safeCount = totalCount - hazardCount;

  // ═══ LLM 출처 통합 판단 (legal × entry 2D 매트릭스) ═══
  const ci = simResult.competitor_intel as Record<string, unknown> | null | undefined;
  const legalRaw = simResult.overall_legal_risk ?? null;
  const entryRaw = (ci?.market_entry_signal as string | undefined) ?? null;
  const verdict = computeDecision(legalRaw, entryRaw);
  const verdictCopy = DECISION_COPY[verdict];
  const isVerdictUnknown = verdict === 'UNKNOWN';

  return (
    <div className="space-y-6">
      {/* ═══ LLM 출처 통합 판단 (AnalyzeAiSummaryTab → 이관) ═══ */}
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
            id: `legal-decision-${i}`,
            ...a,
          })),
          methodology: 'synthesis + legal + competitor',
        }}
      />

      {/* ═══ 법률·규제 검토 본문 ═══ */}
      <div className="bg-stone-900/40 border border-stone-800/60 p-8 rounded-3xl">
        <div className="flex justify-between items-center mb-6">
          <h4 className="text-sm font-black text-stone-100 flex items-center gap-2 uppercase tracking-tight">
            <AlertTriangle size={16} className="text-rose-400" /> 법률·규제 검토
            {totalCount > 0 && (
              <span className="text-[0.625rem] font-black normal-case tracking-normal">
                <span className="text-rose-400">위험 {hazardCount}건</span>
                <span className="text-stone-600 mx-1">·</span>
                <span className="text-emerald-400/80">안전 {safeCount}건</span>
              </span>
            )}
          </h4>
          {totalCount > 0 && (
            <button
              type="button"
              onClick={() =>
                openModal({
                  title: '법률 리스크 종합 검토',
                  content: risks
                    .map(
                      (r, i) =>
                        `${i + 1}. [${r.risk_level}] ${r.type}\n   ${r.detail || r.recommendation || ''}`,
                    )
                    .join('\n\n'),
                })
              }
              className="text-[0.625rem] font-black text-stone-500 hover:text-indigo-400 flex items-center gap-1 uppercase transition-colors"
            >
              <Maximize2 size={12} /> 전체 리포트 보기
            </button>
          )}
        </div>

        {/* 등급 분포 막대 */}
        <div className="bg-stone-950/40 border border-stone-800/60 rounded-2xl p-6 mb-4">
          <h5 className="text-xs font-black text-stone-500 uppercase tracking-widest mb-3">
            법률 리스크 등급 분포
          </h5>
          <LegalDistributionBar risks={risks} />
        </div>

        {/* 상세 테이블 + Drawer */}
        <InsightsGrid simResult={simResult} legalOnly />
      </div>
    </div>
  );
}
