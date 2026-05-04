import { useState } from 'react';
import type { LegalRisk, LegalSpotEvaluation, SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';
import { LegalDrawer } from '../shared/LegalDrawer';
import { AgentCard } from '../shared/AgentCard';

type Tab = 'legal' | 'ai_insights' | 'competitor_risks';

interface Props {
  simResult: SimulationOutput;
  legalOnly?: boolean;
}

const LEGAL_TYPE_LABEL: Record<string, string> = {
  franchise_law: '가맹사업법',
  commercial_lease_law: '상가임대차보호법',
  zoning_regulation: '용도지역 규제',
  food_hygiene: '식품위생법',
  safety_regulation: '안전규정',
  building_law: '건축법',
  fire_safety_law: '소방안전법',
  labor_law: '근로기준법',
  vat_law: '부가가치세법',
  privacy_law: '개인정보보호법',
  accessibility_law: '장애인편의법',
  sewage_law: '하수도법',
  school_zone: '학교환경위생정화구역',
  fair_trade_law: '공정거래법',
  ftc_franchise: '공정위 정보공개서',
};

// 카테고리 그룹 매핑 — backend `LEGAL_CATEGORY_GROUP` 와 일치 (응답 누락 시 폴백용).
// 단일 소스는 backend 이며 frontend 는 응답 `r.group` 우선, 없으면 이 매핑으로 폴백.
const LEGAL_TYPE_GROUP: Record<string, 'location' | 'operation'> = {
  // 입지 (출점 결정 critical)
  building_law: 'location',
  school_zone: 'location',
  safety_regulation: 'location',
  fire_safety_law: 'location',
  accessibility_law: 'location',
  franchise_law: 'location',
  fair_trade_law: 'location',
  commercial_lease_law: 'location',
  zoning_regulation: 'location',
  ftc_franchise: 'location',
  // 운영 (자영업자 통상 인지)
  food_hygiene: 'operation',
  labor_law: 'operation',
  vat_law: 'operation',
  privacy_law: 'operation',
  sewage_law: 'operation',
};

function resolveGroup(r: LegalRisk): 'location' | 'operation' {
  return r.group ?? LEGAL_TYPE_GROUP[r.type] ?? 'operation';
}

interface LegalGroupSectionProps {
  groupLabel: string;
  groupSubtitle: string;
  risks: LegalRisk[];
  hazardCount: number;
  expanded: boolean;
  primary: boolean;
  onToggleGroup?: () => void;
  onSelect: (r: LegalRisk) => void;
  expandedSafe: boolean;
  onToggleSafe: () => void;
}

/**
 * 입지/운영 그룹 단위 섹션 — 헤더(그룹명/카운트) + 테이블.
 * primary=true 면 항상 펼쳐진 상태(입지), false 면 헤더 클릭으로 토글(운영).
 */
function LegalGroupSection({
  groupLabel,
  groupSubtitle,
  risks,
  hazardCount,
  expanded,
  primary,
  onToggleGroup,
  onSelect,
  expandedSafe,
  onToggleSafe,
}: LegalGroupSectionProps) {
  const total = risks.length;
  const hazardRisks = risks.filter((r) => normalizeLevel(r.risk_level) !== 'LOW');
  const safeRisks = risks.filter((r) => normalizeLevel(r.risk_level) === 'LOW');

  const headerClickable = !primary && typeof onToggleGroup === 'function';

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div
        className={`flex items-center justify-between border-b border-border px-4 py-3 ${
          primary ? 'bg-primary/5' : 'bg-muted'
        } ${headerClickable ? 'cursor-pointer select-none' : ''}`}
        onClick={headerClickable ? onToggleGroup : undefined}
        role={headerClickable ? 'button' : undefined}
        tabIndex={headerClickable ? 0 : undefined}
        onKeyDown={
          headerClickable
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onToggleGroup?.();
                }
              }
            : undefined
        }
      >
        <div className="flex items-baseline gap-2">
          <span
            className={`text-sm font-black uppercase tracking-tight ${
              primary ? 'text-foreground' : 'text-muted-foreground'
            }`}
          >
            {groupLabel}
          </span>
          <span className="text-[0.625rem] font-medium text-muted-foreground">{groupSubtitle}</span>
        </div>
        <div className="flex items-center gap-3 text-[0.625rem] font-black uppercase">
          {hazardCount > 0 ? (
            <span className="text-danger">위험 {hazardCount}건</span>
          ) : (
            <span className="text-success/80">위험 0건</span>
          )}
          <span className="text-muted-foreground">총 {total}건</span>
          {!primary && <span className="text-muted-foreground">{expanded ? '▾' : '▸'}</span>}
        </div>
      </div>

      {expanded && (
        <div className="overflow-x-auto">
          {total === 0 ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              해당 그룹 리스크 없음
            </div>
          ) : (
            <table className="w-full min-w-[560px]">
              <thead className="border-b border-border bg-muted">
                <tr>
                  <th className="p-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                    #
                  </th>
                  <th className="p-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                    법률
                  </th>
                  <th className="p-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                    위험도
                  </th>
                  <th className="p-3 text-right text-xs font-semibold uppercase text-muted-foreground">
                    조문
                  </th>
                  <th className="p-3 text-right text-xs font-semibold uppercase text-muted-foreground">
                    체크리스트
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {/* 위험군 (HIGH/MEDIUM) */}
                {hazardRisks.map((r, i) => {
                  const lvl = normalizeLevel(r.risk_level);
                  const cls = LEVEL_CLS[lvl];
                  return (
                    <tr
                      key={`hazard-${r.type}-${i}`}
                      onClick={() => onSelect(r)}
                      className="cursor-pointer border-b border-border hover:bg-muted"
                    >
                      <td className="relative p-3 pl-4 font-mono text-xs text-muted-foreground">
                        <span
                          className={`absolute left-0 top-1 bottom-1 w-[3px] rounded-r ${cls.strip}`}
                          aria-hidden="true"
                        />
                        {i + 1}
                      </td>
                      <td className="p-3 text-sm font-semibold text-foreground">
                        {LEGAL_TYPE_LABEL[r.type] || r.type}
                      </td>
                      <td className={`p-3 text-xs font-bold ${cls.text}`}>● {cls.label}</td>
                      <td className="p-3 text-right text-sm text-foreground">
                        {r.articles?.length ?? 0}
                      </td>
                      <td className="p-3 text-right text-sm text-foreground">
                        {r.checklist?.length ?? 0}
                      </td>
                      <td className="p-3 text-right text-muted-foreground">›</td>
                    </tr>
                  );
                })}

                {/* 안전군 (LOW) toggle */}
                {safeRisks.length > 0 && (
                  <tr
                    onClick={onToggleSafe}
                    className="cursor-pointer border-b border-border bg-muted hover:bg-muted"
                  >
                    <td className="relative p-3 pl-4 font-mono text-xs text-muted-foreground">
                      <span
                        className="absolute left-0 top-1 bottom-1 w-[3px] rounded-r bg-success/60"
                        aria-hidden="true"
                      />
                      —
                    </td>
                    <td colSpan={4} className="p-3 text-xs font-bold text-success/80">
                      안전 항목 {safeRisks.length}건 검토됨
                      <span className="ml-2 text-muted-foreground font-normal">
                        (참고사항 — 위험군 아님)
                      </span>
                    </td>
                    <td className="p-3 text-right text-muted-foreground">
                      {expandedSafe ? '▾' : '▸'}
                    </td>
                  </tr>
                )}

                {/* 안전군 펼침 시 디테일 */}
                {expandedSafe &&
                  safeRisks.map((r, i) => {
                    const lvl = normalizeLevel(r.risk_level);
                    const cls = LEVEL_CLS[lvl];
                    return (
                      <tr
                        key={`safe-${r.type}-${i}`}
                        onClick={() => onSelect(r)}
                        className="cursor-pointer border-b border-border bg-muted last:border-b-0 hover:bg-muted"
                      >
                        <td className="relative p-3 pl-4 font-mono text-xs text-muted-foreground">
                          <span
                            className={`absolute left-0 top-1 bottom-1 w-[3px] rounded-r ${cls.strip}`}
                            aria-hidden="true"
                          />
                          {hazardRisks.length + i + 1}
                        </td>
                        <td className="p-3 text-sm text-foreground">
                          {LEGAL_TYPE_LABEL[r.type] || r.type}
                        </td>
                        <td className={`p-3 text-xs font-bold ${cls.text}`}>● {cls.label}</td>
                        <td className="p-3 text-right text-sm text-muted-foreground">
                          {r.articles?.length ?? 0}
                        </td>
                        <td className="p-3 text-right text-sm text-muted-foreground">
                          {r.checklist?.length ?? 0}
                        </td>
                        <td className="p-3 text-right text-muted-foreground">›</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

const LEVEL_CLS: Record<string, { strip: string; text: string; label: string }> = {
  HIGH: { strip: 'bg-danger', text: 'text-danger', label: '필수이행' },
  MEDIUM: { strip: 'bg-primary', text: 'text-warning', label: '확인필요' },
  LOW: { strip: 'bg-success', text: 'text-success', label: '참고사항' },
};

// risk_level 두 패턴 정규화: HIGH/MEDIUM/LOW + danger/caution/safe.
// safe → LOW (안전군), 기타 fallback → MEDIUM (보수적 처리)
function normalizeLevel(level: string): 'HIGH' | 'MEDIUM' | 'LOW' {
  const up = level.toUpperCase();
  if (up === 'HIGH' || up === 'DANGER') return 'HIGH';
  if (up === 'MEDIUM' || up === 'CAUTION') return 'MEDIUM';
  if (up === 'LOW' || up === 'SAFE') return 'LOW';
  return 'MEDIUM';
}

const SPOT_LEVEL_CLS: Record<string, { strip: string; text: string; bg: string; label: string }> = {
  danger: { strip: 'bg-danger', text: 'text-danger', bg: 'bg-danger/5', label: '침해' },
  caution: { strip: 'bg-warning', text: 'text-warning', bg: 'bg-warning/5', label: '주의' },
  safe: { strip: 'bg-success', text: 'text-success', bg: 'bg-success/5', label: '안전' },
};

function SpotEvaluationGrid({ spots }: { spots: LegalSpotEvaluation[] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h4 className="text-xs font-black uppercase tracking-tight text-foreground">
          후보지 영업구역 침해 점검
        </h4>
        <span className="text-[0.625rem] font-medium text-muted-foreground">
          가맹사업법 제12조의4 · 동일 브랜드 영업구역 기준
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {spots.map((s, i) => {
          const cls = SPOT_LEVEL_CLS[s.level] ?? SPOT_LEVEL_CLS.caution;
          return (
            <div
              key={`spot-${s.dong_name}-${i}`}
              className={`relative rounded-md border border-border ${cls.bg} p-3`}
            >
              <span
                className={`absolute left-0 top-2 bottom-2 w-[3px] rounded-r ${cls.strip}`}
                aria-hidden="true"
              />
              <div className="ml-2 flex items-baseline justify-between">
                <span className="text-[0.625rem] font-mono uppercase tracking-widest text-muted-foreground">
                  {s.rank_label}
                </span>
                <span className={`text-[0.625rem] font-bold uppercase ${cls.text}`}>
                  ● {cls.label}
                </span>
              </div>
              <div className="ml-2 mt-1 text-sm font-bold text-foreground">{s.dong_name}</div>
              <p className="ml-2 mt-1 text-[0.6875rem] leading-snug text-muted-foreground">
                {s.summary}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function InsightsGrid({ simResult, legalOnly }: Props) {
  const [tab, setTab] = useState<Tab>('legal');
  const [selected, setSelected] = useState<LegalRisk | null>(null);
  // 안전 항목 (LOW/safe) 펼침 토글 — 본부 영업팀 빠른 판단을 위한 노이즈 정리
  const [expandedSafe, setExpandedSafe] = useState(false);

  const legalAgent = simResult.agent_attributions?.find((a) => a.id === 'legal');
  const risks = simResult.legal_risks ?? [];
  // 입지(location) 그룹만 노출. 운영(operation) 카테고리는 사용자 요청에 따라 hide.
  const locationRisks = risks.filter((r) => resolveGroup(r) === 'location');
  const locationHazard = locationRisks.filter((r) => normalizeLevel(r.risk_level) !== 'LOW').length;
  // franchise_law risk 의 spot_evaluations — 후보지 4곳 영업구역 침해 평가 (rank/level/summary).
  // backend legal.py 가 vacancy_spot_analyses 를 가공해 attach.
  const franchiseRisk = risks.find((r) => r.type === 'franchise_law');
  const spotEvaluations = franchiseRisk?.spot_evaluations ?? [];
  const compIntel = simResult.competitor_intel as Record<string, any> | null | undefined;
  const opportunities = (compIntel?.key_opportunities ?? []) as string[];
  const riskTexts = (compIntel?.key_risks ?? []) as string[];
  const aiRecommendation = simResult.ai_recommendation ?? simResult.analysis_report ?? '';

  const activeTab = legalOnly ? 'legal' : tab;

  return (
    <section>
      <SectionLabel
        label="INSIGHTS & LEGAL"
        subtitle={legalOnly ? '법률 리스크' : '법률 리스크 · AI 인사이트 · 경쟁 리스크'}
      />

      {!legalOnly && (
        <div className="mb-4 flex gap-1 border-b border-border">
          {(
            [
              { key: 'legal', label: `법률 ${risks.length}` },
              { key: 'ai_insights', label: 'AI 인사이트' },
              { key: 'competitor_risks', label: '경쟁 리스크' },
            ] as const
          ).map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`border-b-2 px-4 py-2 text-sm font-semibold transition-colors ${
                tab === t.key
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {activeTab === 'legal' && (
        <div className="space-y-4">
          {risks.length === 0 ? (
            <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
              법률 리스크 데이터 없음
            </div>
          ) : (
            <>
              {/* ── 후보지 영업구역 침해 카드 (franchise_law spot_evaluations) ── */}
              {spotEvaluations.length > 0 && <SpotEvaluationGrid spots={spotEvaluations} />}

              {/* ── 입지(location) 섹션 — 출점 결정 critical, 항상 펼침 ── */}
              <LegalGroupSection
                groupLabel="입지 — 출점 시 검토"
                groupSubtitle="후보지·면적·임대차 등 출점 의사결정에 직접 영향"
                risks={locationRisks}
                hazardCount={locationHazard}
                expanded
                primary
                onSelect={setSelected}
                expandedSafe={expandedSafe}
                onToggleSafe={() => setExpandedSafe((v) => !v)}
              />
            </>
          )}
        </div>
      )}

      {tab === 'ai_insights' && (
        <div className="rounded-lg border border-border bg-card p-6">
          {aiRecommendation ? (
            <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
              {aiRecommendation}
            </p>
          ) : (
            <div className="text-center text-sm text-muted-foreground">AI 인사이트 데이터 없음</div>
          )}
        </div>
      )}

      {activeTab === 'competitor_risks' && (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-card p-4">
            <h4 className="mb-3 text-sm font-semibold text-success">기회</h4>
            {opportunities.length > 0 ? (
              <ul className="space-y-1 text-sm text-foreground">
                {opportunities.map((o, i) => (
                  <li key={i}>• {o}</li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-muted-foreground">데이터 없음</div>
            )}
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <h4 className="mb-3 text-sm font-semibold text-danger">리스크</h4>
            {riskTexts.length > 0 ? (
              <ul className="space-y-1 text-sm text-foreground">
                {riskTexts.map((r, i) => (
                  <li key={i}>• {r}</li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-muted-foreground">데이터 없음</div>
            )}
          </div>
        </div>
      )}

      {legalAgent && (
        <div className="mt-3">
          <AgentCard attribution={legalAgent} size="full" />
        </div>
      )}

      <LegalDrawer
        risk={
          selected
            ? {
                type: LEGAL_TYPE_LABEL[selected.type] || selected.type,
                risk_level: normalizeLevel(selected.risk_level),
                summary: selected.detail,
                articles: selected.articles,
                checklist: selected.checklist,
                recommendation: selected.recommendation,
              }
            : null
        }
        open={!!selected}
        onClose={() => setSelected(null)}
      />
    </section>
  );
}
