/**
 * AnalyzeAiSummaryTab — AI 분석 요약 (synthesis 종합 + 최종 권고)
 *
 * 2026-04-28 IA 재구조 — SummaryTab 의 synthesis 자연어 이관.
 * 2026-04-28 H6 — LLM 산출 "1등 추천 동" + Top 3 칩 카드 추가.
 * 2026-04-29 IM3-263 — LLM 출처 통합 판단 + 창업 진입 신호 카드를 LegalTab 으로 이관.
 *   synthesis 종합 분석을 최상단에 강조, 최종 권고를 그 밑에 배치.
 *
 * 데이터 출처:
 *   - 1등 추천 동: simResult.winner_district (district_ranking 에이전트 산출)
 *   - Top 3 후보: simResult.top_3_candidates (district_ranking 에이전트 산출)
 *   - synthesis 자연어: simResult.final_report.summary || simResult.analysis_report
 *   - 최종 권고: simResult.final_report.final_recommendation || simResult.ai_recommendation
 *
 * 실데이터 원칙: winner_district 가 없으면 추천 동 카드 자체를 hide.
 */

import { MapPin, Trophy } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { NarrativeText } from '../../shared/NarrativeText';
import { SynthesisSections } from '../../shared/SynthesisSections';

interface Props {
  simResult: SimulationOutput;
}

export function AnalyzeAiSummaryTab({ simResult }: Props) {
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
              <div className="mb-3 flex items-center gap-2 text-[0.625rem] font-black uppercase tracking-widest text-indigo-300">
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
              <span className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
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

      {/* ═══ synthesis 종합 분석 (최상단, 섹션별 블록 구조) ═══ */}
      {summary && (
        <div className="rounded-3xl border border-stone-700/60 bg-stone-900/60 p-8">
          <h3 className="mb-6 text-base font-black uppercase tracking-widest text-stone-300">
            synthesis 종합 분석
          </h3>
          <SynthesisSections text={summary} />
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
