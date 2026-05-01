/**
 * LegalTab — 법률·규제 전용 탭
 *
 * MarketTab에서 법률 섹션 이관. 가맹사업법·임대차보호법 등 규제 리스크를
 * 전용 공간에서 드릴다운할 수 있도록 분리. 본부 영업팀 법무 확인용.
 *
 * 2026-04-30 — LLM 출처 통합 판단(GO/HOLD/STOP) 카드 제거.
 *
 * 구성:
 * 1) 헤더: 위험/안전 카운트 + 전체 리포트 보기
 * 2) 등급 분포 막대 (HIGH/MEDIUM/LOW 한눈에)
 * 3) 하단: InsightsGrid legalOnly — 표 + LegalDrawer 상세
 */

import { AlertTriangle, Maximize2 } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { InsightsGrid } from '../../sections/InsightsGrid';
import { LegalDistributionBar } from '../charts/LegalDistributionBar';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

const AGENT_ICON = {
  synthesis: { icon: BrainCircuit, color: 'text-foreground', borderCls: 'border-border/60' },
  legal: { icon: AlertTriangle, color: 'text-danger', borderCls: 'border-danger/50' },
  competitor: { icon: ShieldAlert, color: 'text-warning', borderCls: 'border-warning/50' },
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

  return (
    <div className="space-y-6">
      {/* ═══ 법률·규제 검토 본문 ═══ */}
      <div className="bg-card/40 border border-border/60 p-8 rounded-3xl">
        <div className="flex justify-between items-center mb-6">
          <h4 className="text-sm font-black text-foreground flex items-center gap-2 uppercase tracking-tight">
            <AlertTriangle size={16} className="text-danger" /> 법률·규제 검토
            {totalCount > 0 && (
              <span className="text-[0.625rem] font-black normal-case tracking-normal">
                <span className="text-danger">위험 {hazardCount}건</span>
                <span className="text-muted-foreground mx-1">·</span>
                <span className="text-success/80">안전 {safeCount}건</span>
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
              className="text-[0.625rem] font-black text-muted-foreground hover:text-primary flex items-center gap-1 uppercase transition-colors"
            >
              <Maximize2 size={12} /> 전체 리포트 보기
            </button>
          )}
        </div>

        {/* 등급 분포 막대 */}
        <div className="bg-card/40 border border-border/60 rounded-2xl p-6 mb-4">
          <h5 className="text-xs font-black text-muted-foreground uppercase tracking-widest mb-3">
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
