import { useState } from 'react';
import type { LegalRisk, SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';
import { LegalDrawer } from '../shared/LegalDrawer';

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
  fair_trade_law: '공정거래법',
  ftc_franchise: '공정위 정보공개서',
};

const LEVEL_CLS: Record<string, { border: string; text: string; label: string }> = {
  HIGH: { border: 'border-l-4 border-rose-500', text: 'text-rose-400', label: '위험' },
  MEDIUM: { border: 'border-l-4 border-yellow-500', text: 'text-yellow-400', label: '주의' },
  LOW: { border: 'border-l-4 border-emerald-500', text: 'text-emerald-400', label: '안전' },
};

function normalizeLevel(level: string): 'HIGH' | 'MEDIUM' | 'LOW' {
  const up = level.toUpperCase();
  if (up === 'HIGH' || up === 'MEDIUM' || up === 'LOW') return up;
  return 'MEDIUM';
}

export function InsightsGrid({ simResult, legalOnly }: Props) {
  const [tab, setTab] = useState<Tab>('legal');
  const [selected, setSelected] = useState<LegalRisk | null>(null);

  const risks = simResult.legal_risks ?? [];
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
        <div className="mb-4 flex gap-1 border-b border-stone-700">
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
                  ? 'border-indigo-500 text-indigo-500'
                  : 'border-transparent text-stone-400 hover:text-stone-100'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {activeTab === 'legal' && (
        <div className="overflow-x-auto rounded-lg border border-stone-700 bg-zinc-800">
          {risks.length === 0 ? (
            <div className="p-6 text-center text-sm text-stone-400">법률 리스크 데이터 없음</div>
          ) : (
            <table className="w-full min-w-[560px]">
              <thead className="border-b border-stone-700 bg-stone-900/60">
                <tr>
                  <th className="p-3 text-left text-xs font-semibold uppercase text-stone-400">
                    #
                  </th>
                  <th className="p-3 text-left text-xs font-semibold uppercase text-stone-400">
                    법률
                  </th>
                  <th className="p-3 text-left text-xs font-semibold uppercase text-stone-400">
                    위험도
                  </th>
                  <th className="p-3 text-right text-xs font-semibold uppercase text-stone-400">
                    조문
                  </th>
                  <th className="p-3 text-right text-xs font-semibold uppercase text-stone-400">
                    체크리스트
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {risks.map((r, i) => {
                  const lvl = normalizeLevel(r.risk_level);
                  const cls = LEVEL_CLS[lvl];
                  return (
                    <tr
                      key={`${r.type}-${i}`}
                      onClick={() => setSelected(r)}
                      className={`cursor-pointer border-b border-stone-700/50 last:border-b-0 hover:bg-stone-700/50 ${cls.border}`}
                    >
                      <td className="p-3 font-mono text-xs text-stone-400">{i + 1}</td>
                      <td className="p-3 text-sm font-semibold text-stone-100">
                        {LEGAL_TYPE_LABEL[r.type] || r.type}
                      </td>
                      <td className={`p-3 text-xs font-bold ${cls.text}`}>● {cls.label}</td>
                      <td className="p-3 text-right text-sm text-stone-300">
                        {r.articles?.length ?? 0}
                      </td>
                      <td className="p-3 text-right text-sm text-stone-300">
                        {r.checklist?.length ?? 0}
                      </td>
                      <td className="p-3 text-right text-stone-400">›</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'ai_insights' && (
        <div className="rounded-lg border border-stone-700 bg-stone-800 p-6">
          {aiRecommendation ? (
            <p className="whitespace-pre-line text-sm leading-relaxed text-stone-200">
              {aiRecommendation}
            </p>
          ) : (
            <div className="text-center text-sm text-stone-400">AI 인사이트 데이터 없음</div>
          )}
        </div>
      )}

      {activeTab === 'competitor_risks' && (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-stone-700 bg-stone-800 p-4">
            <h4 className="mb-3 text-sm font-semibold text-emerald-400">기회</h4>
            {opportunities.length > 0 ? (
              <ul className="space-y-1 text-sm text-stone-300">
                {opportunities.map((o, i) => (
                  <li key={i}>• {o}</li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-stone-500">데이터 없음</div>
            )}
          </div>
          <div className="rounded-lg border border-stone-700 bg-stone-800 p-4">
            <h4 className="mb-3 text-sm font-semibold text-rose-400">리스크</h4>
            {riskTexts.length > 0 ? (
              <ul className="space-y-1 text-sm text-stone-300">
                {riskTexts.map((r, i) => (
                  <li key={i}>• {r}</li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-stone-500">데이터 없음</div>
            )}
          </div>
        </div>
      )}

      <LegalDrawer
        risk={
          selected
            ? {
                type: LEGAL_TYPE_LABEL[selected.type] || selected.type,
                risk_level: normalizeLevel(selected.risk_level),
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
