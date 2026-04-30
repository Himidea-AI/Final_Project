/**
 * DetailDrawer (v8.0) — KPI/차트 클릭 시 우측에서 슬라이드 인
 * App.tsx Phase C Round 3 코드 스플릿으로 추출 — 기능 변경 없음.
 */
import { X } from 'lucide-react';
import type { LegalRisk } from '../types';

/* ═══════════════════════════════════════════════════════
   DRILL-DOWN DRAWER — 지표별 상세 데이터 스키마
   ⚠️ 백엔드 `/api/details/:category` 엔드포인트 대기 중.
       실데이터 없으면 drawer 내부에 "구현 예정" empty state 노출.
   ═══════════════════════════════════════════════════════ */
export type DrawerKey =
  | 'revenue'
  | 'attractiveness'
  | 'traffic'
  | 'cannibalization'
  | 'insight_legal'
  | 'insight_traffic'
  | 'insight_target'
  | null;

interface DetailDataEntry {
  title: string;
  aiReasoning?: string;
  confidence?: string;
  rank?: string;
  trend?: string;
  peakTime?: string;
  mainTarget?: string;
  warning?: string;
}

// 각 drawer key 의 타이틀만 유지 — 본문 내용은 실제 응답/진행중 메시지로 채움
const DRAWER_TITLES: Record<Exclude<DrawerKey, null>, string> = {
  revenue: '예상 월 매출 상세',
  attractiveness: '상권 종합 매력도 상세',
  traffic: '일일 유동인구 상세',
  cannibalization: '카니발리제이션 위험 상세',
  insight_legal: '법률 리스크 상세 분석',
  insight_traffic: '피크 시간대 매출 집중 분석',
  insight_target: '주요 타겟 고객층 분석',
};

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

function DetailDrawer({
  isOpen,
  onClose,
  drawerKey,
  popData,
  analysisMetrics,
  legalRisks,
  selectedLegalType,
}: {
  isOpen: boolean;
  onClose: () => void;
  drawerKey: DrawerKey;
  popData?: any;
  analysisMetrics?: { main_target_age?: string; peak_time?: string };
  legalRisks?: LegalRisk[];
  selectedLegalType?: string | null;
}) {
  const drawerTitle = drawerKey ? DRAWER_TITLES[drawerKey] : '';
  const selectedRisk =
    drawerKey === 'insight_legal' && selectedLegalType
      ? (legalRisks ?? []).find((r) => r.type === selectedLegalType)
      : undefined;
  // 실 데이터만 사용. 없으면 null → drawer 내부에 "구현 예정" empty state 표시.
  const data: DetailDataEntry | null =
    drawerKey === 'insight_target' && analysisMetrics?.main_target_age
      ? {
          title: `${analysisMetrics.main_target_age} 타겟 권역 분석`,
          aiReasoning: `유동인구 분석 결과 주요 타겟층: ${analysisMetrics.main_target_age}. 피크 타임대 체류 인구 기반으로 메뉴·마케팅 전략을 해당 층에 집중하면 객단가 및 재방문율 향상이 기대됩니다.`,
          mainTarget: analysisMetrics.main_target_age,
          peakTime: analysisMetrics.peak_time,
        }
      : drawerKey === 'traffic' && popData
        ? {
            title: '일일 유동인구 상세',
            aiReasoning: `${popData.dong_name ?? ''} 실측 유동인구 데이터 기반. 일평균 ${(popData.daily_average ?? 0).toLocaleString()}명, 피크 ${analysisMetrics?.peak_time ?? '미정'}.`,
            peakTime: analysisMetrics?.peak_time,
            mainTarget: analysisMetrics?.main_target_age,
          }
        : drawerKey === 'insight_traffic' && analysisMetrics?.peak_time
          ? {
              title: `${analysisMetrics.peak_time} 피크 시간대 분석`,
              aiReasoning: `${analysisMetrics.peak_time} 피크 집중 상권. 주 소비층: ${analysisMetrics.main_target_age ?? '분석 결과 참조'}.`,
              peakTime: analysisMetrics.peak_time,
              mainTarget: analysisMetrics.main_target_age,
            }
          : drawerKey === 'insight_legal' && selectedRisk
            ? {
                title: `${LEGAL_TYPE_LABEL[selectedRisk.type] || selectedRisk.type} 상세 분석`,
                aiReasoning: selectedRisk.detail,
              }
            : null;

  return (
    <>
      {/* Backdrop Overlay */}
      <div
        className={`fixed inset-0 z-[100] bg-card/60 backdrop-blur-sm transition-opacity duration-500 ${
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <div
        className={`fixed top-0 right-0 w-full md:w-[480px] h-full bg-card border-l border-border z-[101] shadow-2xl flex flex-col transition-transform duration-[800ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {!data && drawerKey && (
          <>
            <div className="flex justify-between items-center p-6 border-b border-border shrink-0">
              <h2 className="text-xl font-bold text-foreground">{drawerTitle}</h2>
              <button
                onClick={onClose}
                className="p-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-colors"
                aria-label="Close drawer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 flex-1 flex items-center justify-center">
              <div className="rounded-lg border border-dashed border-border bg-card/50 p-10 text-center max-w-sm">
                <div className="mx-auto mb-3 h-8 w-8 animate-pulse rounded-full bg-border" />
                <div className="text-sm font-semibold text-foreground">구현 예정</div>
                <div className="mt-2 text-xs text-muted-foreground leading-relaxed">
                  지표별 drill-down 상세 분석은 백엔드 API (`/api/details`) 연동 후 제공됩니다.
                </div>
              </div>
            </div>
          </>
        )}

        {data && (
          <>
            {/* Header */}
            <div className="flex justify-between items-center p-6 border-b border-border shrink-0">
              <h2 className="text-xl font-bold text-foreground">{data.title}</h2>
              <button
                onClick={onClose}
                className="p-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-colors"
                aria-label="Close drawer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 overflow-y-auto custom-scrollbar flex-1 text-foreground">
              {/* AI 산출 근거 */}
              <div className="bg-card p-5 rounded-xl border border-border mb-4">
                <h3 className="text-xs font-bold text-primary tracking-widest uppercase mb-2">
                  AI 산출 근거
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {data.aiReasoning || '해당 지표에 대한 상세 분석 알고리즘 로그입니다.'}
                </p>
              </div>

              {/* 메타 데이터 */}
              {(data.confidence ||
                data.rank ||
                data.trend ||
                data.peakTime ||
                data.mainTarget ||
                data.warning) && (
                <div className="bg-card p-5 rounded-xl border border-border mb-4 space-y-3">
                  <h3 className="text-xs font-bold text-primary tracking-widest uppercase mb-3">
                    핵심 지표
                  </h3>
                  {data.confidence && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-muted-foreground">신뢰도</span>
                      <span className="text-sm font-bold text-foreground font-mono">
                        {data.confidence}
                      </span>
                    </div>
                  )}
                  {data.rank && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-muted-foreground">순위</span>
                      <span className="text-sm font-bold text-foreground">{data.rank}</span>
                    </div>
                  )}
                  {data.trend && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-muted-foreground">추세</span>
                      <span className="text-sm font-bold text-success">{data.trend}</span>
                    </div>
                  )}
                  {data.peakTime && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-muted-foreground">피크 타임</span>
                      <span className="text-sm font-bold text-foreground font-mono">
                        {data.peakTime}
                      </span>
                    </div>
                  )}
                  {data.mainTarget && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-muted-foreground">주 타겟층</span>
                      <span className="text-sm font-bold text-foreground">{data.mainTarget}</span>
                    </div>
                  )}
                  {data.warning && (
                    <div className="pt-3 border-t border-border">
                      <span className="text-xs text-danger leading-relaxed block">
                        {data.warning}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* 근거 조항 — 법률 리스크 drawer 전용 (선택된 법률 1건만) */}
              {drawerKey === 'insight_legal' &&
                (() => {
                  const risk = (legalRisks ?? []).find((r) => r.type === selectedLegalType);
                  if (!risk) return null;
                  const lv = (risk.risk_level || '').toLowerCase();
                  const isCritical = lv === 'danger' || lv === 'high';
                  // 문자열/객체 방어 렌더 — 백엔드 구버전 응답(list[str]) 시에도 조문 번호는 표시
                  const normalizedArticles = (risk.articles ?? []).map((a) =>
                    typeof a === 'string'
                      ? { article_ref: a, content: '' }
                      : { article_ref: a.article_ref ?? '', content: a.content ?? '' },
                  );
                  return (
                    <div className="bg-card p-5 rounded-xl border border-border mb-4 space-y-4">
                      {/* 창업 체크리스트 — 상단 배치 */}
                      {risk.recommendation && (
                        <div>
                          <div className="flex items-center gap-2 mb-3">
                            <h3 className="text-xs font-bold text-primary tracking-widest uppercase">
                              창업 체크리스트
                            </h3>
                            <span
                              className={`text-[0.5625rem] font-mono px-1.5 py-0.5 rounded ${
                                isCritical
                                  ? 'bg-danger/20 text-danger'
                                  : 'bg-warning/20 text-warning'
                              }`}
                            >
                              {isCritical ? '필수이행' : '확인필요'}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
                            {risk.recommendation}
                          </p>
                        </div>
                      )}

                      {/* 핵심 조항 — 하단 배치 */}
                      {normalizedArticles.length > 0 && (
                        <div className="pt-3 border-t border-border">
                          <h3 className="text-xs font-bold text-primary tracking-widest uppercase mb-3">
                            핵심 조항
                          </h3>
                          <ul className="space-y-2">
                            {normalizedArticles.map((a, ai) => (
                              <li key={ai} className="rounded border border-border bg-muted/60 p-3">
                                <div className="text-xs font-bold text-primary mb-1 font-mono">
                                  {a.article_ref || '조문 번호 없음'}
                                </div>
                                <div className="text-xs text-muted-foreground leading-relaxed">
                                  {a.content || (
                                    <span className="text-muted-foreground italic">
                                      데이터 없음
                                    </span>
                                  )}
                                </div>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })()}

              {/* Detailed Chart — 유동인구 동별 상세 (traffic drawer) */}
              {drawerKey === 'traffic' && popData?.dong_details ? (
                <div className="bg-card p-5 rounded-xl border border-border">
                  <h3 className="text-xs font-bold text-primary tracking-widest uppercase mb-3">
                    동별 유동인구 ({popData.date})
                  </h3>
                  <div className="space-y-2">
                    {popData.dong_details.map((d: any) => {
                      const maxPop = popData.dong_details[0]?.daily_total || 1;
                      const pct = Math.round((d.daily_total / maxPop) * 100);
                      return (
                        <div key={d.dong_name} className="flex items-center gap-3">
                          <span className="text-[0.6875rem] text-muted-foreground w-16 shrink-0">
                            {d.dong_name}
                          </span>
                          <div className="flex-1 bg-card rounded-full h-4 overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-primary to-primary rounded-full transition-all duration-700"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-[0.6875rem] text-white font-mono w-20 text-right">
                            {d.daily_total.toLocaleString()}
                          </span>
                          <span className="text-[0.5625rem] text-muted-foreground w-10">
                            피크 {d.peak_hour}시
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-[0.5625rem] text-muted-foreground mt-3">
                    ※ 서울시 생활인구 데이터 (KT 통신 기반) | {popData.data_delay_note}
                  </p>
                </div>
              ) : drawerKey !== 'insight_legal' ? (
                <div className="w-full h-48 bg-card border border-border rounded-xl flex items-center justify-center">
                  <span className="text-border font-mono text-xs tracking-[0.3em]">
                    DETAILED CHART AREA
                  </span>
                </div>
              ) : null}
            </div>
          </>
        )}
      </div>
    </>
  );
}

export default DetailDrawer;
