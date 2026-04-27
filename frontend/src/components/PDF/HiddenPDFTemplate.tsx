/**
 * HiddenPDFTemplate (v12.0) — App.tsx에서 추출한 A4 프린트 최적화 라이트 템플릿.
 * 화면에는 보이지 않고 (absolute top-[-9999px]) html2canvas 캡처 전용.
 * 각 페이지는 794x1123 고정 → jsPDF로 페이지별 변환.
 */

import { forwardRef } from 'react';
import { formatDocumentId } from '../../types/simulationHistory';
import type { CustomerSegment } from '../../types';

/* ═══════════════════════════════════════════════════════
   상세 데이터 테이블 — 정렬 가능한 row data (Mock)
   ═══════════════════════════════════════════════════════ */
export interface CannRow {
  [key: string]: string;
  name: string;
  distance: string;
  impact: string;
  status: string;
}
export interface NeighborhoodRow {
  [key: string]: string;
  name: string;
  score: string;
  closureRate: string;
  bep: string;
}

interface HiddenPDFTemplateProps {
  districtFull: string;
  stats: { title: string; value: string; trend: string }[];
  cannibalizationRows: CannRow[];
  neighborhoodRows: NeighborhoodRow[];
  insights: { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[];
  reportDate: string;
  /** 저장된 이력 ID(BIGINT) — null이면 "SPTR-DRAFT-…" 표시. Saved면 "SPTR-000142" 같은 정식 번호. */
  savedHistoryId?: number | null;
  /** customer_revenue P1-C 타겟 고객 매출 분석 — null 이면 PDF 페이지 자체 생략 */
  customerSegment?: CustomerSegment | null;
}

// 인디고 SPOTTER 로고 SVG 경로 (Light 테마 버전 — #6366f1)
const SPOTTER_LOGO_PATHS = (
  <>
    <path
      d="M18.5147 0C15.4686 0 12.5473 1.21005 10.3934 3.36396L3.36396 10.3934C1.21005 12.5473 0 15.4686 0 18.5147C0 24.8579 5.14214 30 11.4853 30C14.5314 30 17.4527 28.7899 19.6066 26.636L24.4689 21.7737C24.469 21.7738 24.4689 21.7736 24.4689 21.7737L38.636 7.6066C39.6647 6.57791 41.0599 6 42.5147 6C44.9503 6 47.0152 7.58741 47.7311 9.78407L52.2022 5.31296C50.1625 2.11834 46.586 0 42.5147 0C39.4686 0 36.5473 1.21005 34.3934 3.36396L15.364 22.3934C14.3353 23.4221 12.9401 24 11.4853 24C8.45584 24 6 21.5442 6 18.5147C6 17.0599 6.57791 15.6647 7.6066 14.636L14.636 7.6066C15.6647 6.57791 17.0599 6 18.5147 6C20.9504 6 23.0152 7.58748 23.7311 9.78421L28.2023 5.31307C26.1626 2.1184 22.5861 0 18.5147 0Z"
      fill="#6366f1"
    />
    <path
      d="M39.364 22.3934C38.3353 23.4221 36.9401 24 35.4853 24C33.05 24 30.9853 22.413 30.2692 20.2167L25.7982 24.6877C27.838 27.8819 31.4143 30 35.4853 30C38.5314 30 41.4527 28.7899 43.6066 26.636L62.636 7.6066C63.6647 6.57791 65.0599 6 66.5147 6C69.5442 6 72 8.45584 72 11.4853C72 12.9401 71.4221 14.3353 70.3934 15.364L63.364 22.3934C62.3353 23.4221 60.9401 24 59.4853 24C57.0498 24 54.985 22.4127 54.269 20.2162L49.798 24.6873C51.8377 27.8818 55.4141 30 59.4853 30C62.5314 30 65.4527 28.7899 67.6066 26.636L74.636 19.6066C76.7899 17.4527 78 14.5314 78 11.4853C78 5.14214 72.8579 0 66.5147 0C63.4686 0 60.5473 1.21005 58.3934 3.36396L39.364 22.3934Z"
      fill="#6366f1"
    />
  </>
);

function PDFPageHeader({
  pageNumber,
  totalPages,
  districtFull,
}: {
  pageNumber: number;
  totalPages: number;
  districtFull: string;
}) {
  return (
    <div className="flex justify-between items-center border-b border-slate-200 pb-4">
      <div className="flex items-center gap-2.5">
        <svg width="36" height="14" viewBox="0 0 78 30" fill="none">
          {SPOTTER_LOGO_PATHS}
        </svg>
        <span className="text-[13px] font-black tracking-[0.18em] text-slate-900">SPOTTER</span>
        <span className="text-[10px] text-slate-400 ml-1">/ {districtFull} 상권 분석 리포트</span>
      </div>
      <span className="text-[10px] text-slate-400 font-mono tracking-wider">
        PAGE {pageNumber} / {totalPages}
      </span>
    </div>
  );
}

function PDFPageFooter({ reportDate }: { reportDate: string }) {
  return (
    <div className="text-[9px] text-slate-400 font-mono border-t border-slate-200 pt-3 flex justify-between tracking-wider">
      <span>© PROJECT SPOTTER · CONFIDENTIAL</span>
      <span>GENERATED {reportDate}</span>
    </div>
  );
}

export const HiddenPDFTemplate = forwardRef<HTMLDivElement, HiddenPDFTemplateProps>(
  (
    {
      districtFull,
      stats,
      cannibalizationRows,
      neighborhoodRows,
      insights,
      reportDate,
      savedHistoryId = null,
      customerSegment = null,
    },
    ref,
  ) => {
    // customer_segment 없으면 4페이지, 있으면 5페이지
    const TOTAL_PAGES = customerSegment ? 5 : 4;
    const pageClass = 'w-[794px] h-[1123px] p-12 bg-white text-slate-900 relative flex flex-col';
    const docId = formatDocumentId(savedHistoryId);

    const severityStyle = {
      critical: { dot: 'bg-rose-500', bg: 'bg-rose-50 border-rose-200' },
      advisory: { dot: 'bg-[#6366f1]', bg: 'bg-indigo-50 border-indigo-200' },
      opportunity: { dot: 'bg-emerald-500', bg: 'bg-emerald-50 border-emerald-200' },
    };

    return (
      <div
        ref={ref}
        className="absolute top-[-9999px] left-[-9999px] w-[794px] bg-white font-sans"
        style={{ fontFamily: 'Pretendard, sans-serif' }}
      >
        {/* ─────────── Page 1: Cover ─────────── */}
        <div className={pageClass}>
          <div className="flex-1 flex flex-col items-center justify-center">
            <svg width="200" height="78" viewBox="0 0 78 30" fill="none" className="mb-10">
              {SPOTTER_LOGO_PATHS}
            </svg>
            <p className="text-[#6366f1] font-mono text-[11px] tracking-[0.3em] border border-[#6366f1] px-5 py-1.5 rounded-full bg-indigo-50 mb-16">
              AI FRANCHISE INTELLIGENCE REPORT
            </p>
            <h1 className="text-[44px] font-black text-slate-900 text-center leading-[1.2] tracking-tight">
              {districtFull}
              <br />
              상권 분석 결과
            </h1>
            <p className="text-sm text-slate-500 mt-6 tracking-wide">
              SPOTTER AI Multi-Agent Analysis · LangGraph
            </p>
          </div>

          <div className="flex justify-between items-end font-mono text-[10px] text-slate-500 pt-6 border-t border-slate-200">
            <div className="space-y-1.5">
              <p className="tracking-wider">GENERATED · {reportDate}</p>
              <p className="tracking-wider">REQUESTED BY · SPOTTER-HQ</p>
              <p className="tracking-wider">DOCUMENT ID · {docId}</p>
            </div>
            <div className="font-bold text-rose-500 text-sm tracking-[0.25em]">CONFIDENTIAL</div>
          </div>
        </div>

        {/* ─────────── Page 2: 종합 요약 + 차트 ─────────── */}
        <div className={pageClass}>
          <PDFPageHeader pageNumber={2} totalPages={TOTAL_PAGES} districtFull={districtFull} />

          <div className="flex-1 pt-8">
            <h2 className="text-[22px] font-black text-slate-900 mb-1">01. 상권 종합 요약</h2>
            <p className="text-xs text-slate-500 mb-6">
              Executive Summary · 핵심 KPI 및 시계열 분석
            </p>

            {/* KPI Grid */}
            <div className="grid grid-cols-4 gap-3 mb-8">
              {stats.map((s, i) => (
                <div key={i} className="border border-slate-200 bg-slate-50 p-4 rounded-lg">
                  <div className="text-[9px] text-slate-500 mb-2 uppercase tracking-wider">
                    {s.title}
                  </div>
                  <div className="text-[15px] font-black text-slate-900 leading-tight">
                    {s.value}
                  </div>
                  <div className="text-[9px] text-emerald-600 mt-1.5 font-mono">{s.trend}</div>
                </div>
              ))}
            </div>

            {/* Time Series Chart (Light Theme) */}
            <h3 className="text-sm font-bold mb-3 text-slate-900">
              시간대별 유동인구 및 매출 (24H)
            </h3>
            <div className="border border-slate-200 bg-slate-50 rounded-lg p-5 h-[220px] mb-6 relative">
              <svg
                viewBox="0 0 1000 300"
                className="absolute inset-5 w-[calc(100%-40px)] h-[calc(100%-40px)]"
                preserveAspectRatio="none"
              >
                <path
                  d="M 0 280 C 100 280, 150 200, 250 180 C 350 160, 400 250, 500 240 C 600 230, 700 80, 800 100 C 900 120, 950 200, 1000 220 L 1000 300 L 0 300 Z"
                  fill="url(#pdfGrayGrad)"
                  opacity="0.4"
                />
                <path
                  d="M 0 280 C 100 280, 150 200, 250 180 C 350 160, 400 250, 500 240 C 600 230, 700 80, 800 100 C 900 120, 950 200, 1000 220"
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth="3"
                />
                <path
                  d="M 0 290 C 150 290, 200 150, 300 120 C 400 90, 450 200, 550 180 C 650 160, 750 40, 850 50 C 950 60, 980 150, 1000 160 L 1000 300 L 0 300 Z"
                  fill="url(#pdfIndigoGrad)"
                  opacity="0.35"
                />
                <path
                  d="M 0 290 C 150 290, 200 150, 300 120 C 400 90, 450 200, 550 180 C 650 160, 750 40, 850 50 C 950 60, 980 150, 1000 160"
                  fill="none"
                  stroke="#6366f1"
                  strokeWidth="4"
                />
                <defs>
                  <linearGradient id="pdfIndigoGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity="0.5" />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="pdfGrayGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#94a3b8" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#94a3b8" stopOpacity="0" />
                  </linearGradient>
                </defs>
              </svg>
            </div>

            {/* Radar Chart */}
            <h3 className="text-sm font-bold mb-3 text-slate-900">
              상권 종합 지표 분석 (7 Core Metrics)
            </h3>
            <div className="border border-slate-200 bg-slate-50 rounded-lg p-5 flex items-center justify-center">
              <svg viewBox="0 0 200 200" width="240" height="240">
                <polygon
                  points="100,40 147,63 158,113 126,154 74,154 42,113 53,63"
                  fill="#ffffff"
                  stroke="#cbd5e1"
                  strokeWidth="1"
                />
                <polygon
                  points="100,70 123.5,81.5 129,106.5 113,127 87,127 71,106.5 76.5,81.5"
                  fill="none"
                  stroke="#cbd5e1"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                />
                <line x1="100" y1="100" x2="100" y2="40" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="147" y2="63" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="158" y2="113" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="126" y2="154" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="74" y2="154" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="42" y2="113" stroke="#cbd5e1" />
                <line x1="100" y1="100" x2="53" y2="63" stroke="#cbd5e1" />
                <polygon
                  points="100,50 140,70 145,110 115,140 85,130 60,105 70,75"
                  fill="rgba(99,102,241,0.25)"
                  stroke="#6366f1"
                  strokeWidth="2"
                />
                <circle cx="100" cy="50" r="3" fill="#6366f1" />
                <circle cx="140" cy="70" r="3" fill="#6366f1" />
                <circle cx="145" cy="110" r="3" fill="#6366f1" />
                <circle cx="115" cy="140" r="3" fill="#6366f1" />
                <circle cx="85" cy="130" r="3" fill="#6366f1" />
                <circle cx="60" cy="105" r="3" fill="#6366f1" />
                <circle cx="70" cy="75" r="3" fill="#6366f1" />
                <text
                  x="100"
                  y="32"
                  fill="#1e293b"
                  fontSize="10"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  유동인구
                </text>
                <text x="157" y="60" fill="#64748b" fontSize="10" textAnchor="start">
                  매출
                </text>
                <text x="168" y="117" fill="#64748b" fontSize="10" textAnchor="start">
                  성장성
                </text>
                <text x="133" y="166" fill="#64748b" fontSize="10" textAnchor="middle">
                  폐업률
                </text>
                <text x="67" y="166" fill="#64748b" fontSize="10" textAnchor="middle">
                  임대료
                </text>
                <text x="32" y="117" fill="#64748b" fontSize="10" textAnchor="end">
                  경쟁강도
                </text>
                <text x="43" y="60" fill="#64748b" fontSize="10" textAnchor="end">
                  접근성
                </text>
              </svg>
            </div>
          </div>

          <PDFPageFooter reportDate={reportDate} />
        </div>

        {/* ─────────── Page 3: 상세 데이터 테이블 ─────────── */}
        <div className={pageClass}>
          <PDFPageHeader pageNumber={3} totalPages={TOTAL_PAGES} districtFull={districtFull} />

          <div className="flex-1 pt-8 space-y-10">
            <div>
              <h2 className="text-[22px] font-black text-slate-900 mb-1">02. 가맹점 간섭도 분석</h2>
              <p className="text-xs text-slate-500 mb-4">
                Cannibalization Analysis · 반경 내 동일 브랜드 영향도
              </p>
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                    <th className="py-2.5 font-medium">가맹점명</th>
                    <th className="py-2.5 font-medium">거리</th>
                    <th className="py-2.5 font-medium">예상 매출 하락</th>
                    <th className="py-2.5 font-medium">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {cannibalizationRows.map((r, i) => (
                    <tr key={i} className="border-b border-slate-200">
                      <td className="py-3 font-medium text-slate-900">{r.name}</td>
                      <td className="py-3 text-slate-600 font-mono">{r.distance}</td>
                      <td className="py-3 font-mono font-bold text-slate-900">{r.impact}</td>
                      <td className="py-3">
                        <span
                          className={`px-2 py-0.5 text-[9px] rounded-full border font-bold ${
                            r.status === 'Safe'
                              ? 'bg-emerald-50 text-emerald-600 border-emerald-200'
                              : 'bg-slate-100 text-slate-600 border-slate-300'
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div>
              <h2 className="text-[22px] font-black text-slate-900 mb-1">03. 행정동 비교 분석</h2>
              <p className="text-xs text-slate-500 mb-4">
                Neighborhood Comparison · 인근 동 AI 점수 / 폐업률 / 손익분기점
              </p>
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b-2 border-slate-300 text-slate-500 text-left uppercase tracking-wider">
                    <th className="py-2.5 font-medium">행정동</th>
                    <th className="py-2.5 font-medium">AI 점수</th>
                    <th className="py-2.5 font-medium">폐업률</th>
                    <th className="py-2.5 font-medium">예상 BEP</th>
                  </tr>
                </thead>
                <tbody>
                  {neighborhoodRows.map((r, i) => (
                    <tr key={i} className="border-b border-slate-200">
                      <td className="py-3 font-medium text-slate-900">{r.name}</td>
                      <td className="py-3 font-mono text-slate-900">{r.score}</td>
                      <td className="py-3 font-mono text-slate-900">{r.closureRate}</td>
                      <td className="py-3 font-mono text-[#6366f1] font-bold">{r.bep}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <PDFPageFooter reportDate={reportDate} />
        </div>

        {/* ─────────── Page 4: AI 인사이트 ─────────── */}
        <div className={pageClass}>
          <PDFPageHeader pageNumber={4} totalPages={TOTAL_PAGES} districtFull={districtFull} />

          <div className="flex-1 pt-8">
            <h2 className="text-[22px] font-black text-slate-900 mb-1">04. SPOTTER AI 인사이트</h2>
            <p className="text-xs text-slate-500 mb-6">
              LangGraph Multi-Agent Analysis · 에이전트 노드별 인사이트
            </p>

            {insights.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-10 text-center">
                <p className="text-[12px] font-semibold text-slate-600">인사이트 데이터 없음</p>
                <p className="mt-1 text-[10px] text-slate-500">
                  시뮬레이션 실행 후 법률/인구/경쟁 에이전트 결과가 준비되면 자동으로 채워집니다.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {insights.map((insight, i) => {
                  const style = severityStyle[insight.severity];
                  return (
                    <div key={i} className={`border rounded-lg p-5 ${style.bg}`}>
                      <div className="flex items-start justify-between mb-3">
                        <h3 className="text-[14px] font-bold text-slate-900 flex-1">
                          {insight.title}
                        </h3>
                        <span className="inline-flex items-center gap-1.5 shrink-0 ml-3">
                          <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                          <span className="text-[9px] font-mono uppercase tracking-[0.15em] text-slate-500">
                            {insight.severity.toUpperCase()}
                          </span>
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-700 leading-relaxed">{insight.desc}</p>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="mt-10 pt-6 border-t border-slate-200">
              <h4 className="text-[11px] font-bold text-slate-700 mb-2 uppercase tracking-wider">
                분석 방법론 (Methodology)
              </h4>
              <p className="text-[10px] text-slate-500 leading-relaxed">
                본 리포트는 SPOTTER AI 멀티 에이전트 시스템(LangGraph 기반)의 시뮬레이션 결과입니다.
                market_analyst, population_analyst, legal_advisor, financial_insight 4개 노드의 통합
                분석 결과를 포함하며, KT 통신사 셀룰러 데이터,
                공공데이터(상가정보·인구통계·임대시세), 그리고 A2 봉환 팀의 법률 RAG 시스템 (14개
                영역 3,775 청크)을 교차 검증하여 도출되었습니다.
              </p>
              <p className="text-[9px] text-slate-400 mt-3 font-mono">
                DOC ID · {docId} · SPOTTER v3.9 · LangGraph 0.2.x
              </p>
            </div>
          </div>

          <PDFPageFooter reportDate={reportDate} />
        </div>

        {/* ─────────── Page 5: 타겟 고객 매출 분석 (customer_segment 있을 때만) ─────────── */}
        {customerSegment && (
          <div className={pageClass}>
            <PDFPageHeader pageNumber={5} totalPages={TOTAL_PAGES} districtFull={districtFull} />

            <div className="flex-1 pt-8">
              <h2 className="text-[22px] font-black text-slate-900 mb-1">
                05. 타겟 고객 매출 분석
              </h2>
              <p className="text-xs text-slate-500 mb-6">
                Target Customer Segmentation · 연령·성별·시간대·요일 프로필별 매출 기여
              </p>

              {customerSegment.profile_summary && (
                <div className="mb-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                    프로필 요약
                  </div>
                  <p className="text-[12px] text-slate-800 leading-relaxed">
                    {customerSegment.profile_summary}
                  </p>
                </div>
              )}

              {/* KPI 4종 — 금액 없으면 비율만 표시 */}
              <div className="grid grid-cols-4 gap-3 mb-6">
                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="text-[9px] text-slate-500 uppercase tracking-wider">
                    세그먼트 비율
                  </div>
                  <div className="mt-1 text-[18px] font-black text-[#6366f1]">
                    {typeof customerSegment.segment_ratio === 'number'
                      ? `${(customerSegment.segment_ratio * 100).toFixed(2)}%`
                      : '—'}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="text-[9px] text-slate-500 uppercase tracking-wider">
                    타겟 매출
                  </div>
                  <div className="mt-1 text-[14px] font-bold text-emerald-600 font-mono">
                    {customerSegment.segment_sales != null
                      ? `₩${customerSegment.segment_sales.toLocaleString('ko-KR')}`
                      : '—'}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="text-[9px] text-slate-500 uppercase tracking-wider">
                    식별 매출
                  </div>
                  <div className="mt-1 text-[14px] font-bold text-sky-600 font-mono">
                    {customerSegment.identified_sales != null
                      ? `₩${customerSegment.identified_sales.toLocaleString('ko-KR')}`
                      : '—'}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="text-[9px] text-slate-500 uppercase tracking-wider">
                    참조 월매출
                  </div>
                  <div className="mt-1 text-[14px] font-bold text-slate-900 font-mono">
                    {customerSegment.total_sales_ref != null
                      ? `₩${customerSegment.total_sales_ref.toLocaleString('ko-KR')}`
                      : '—'}
                  </div>
                </div>
              </div>

              {/* 4개 분포 차트 — 2×2 그리드 */}
              <div className="grid grid-cols-2 gap-4">
                <PDFRatioChart
                  title="연령대 분포"
                  items={[
                    { key: 'age_10_ratio', label: '10대' },
                    { key: 'age_20_ratio', label: '20대' },
                    { key: 'age_30_ratio', label: '30대' },
                    { key: 'age_40_ratio', label: '40대' },
                    { key: 'age_50_ratio', label: '50대' },
                    { key: 'age_60_above_ratio', label: '60대+' },
                  ]}
                  ratios={customerSegment.dimension_ratios ?? {}}
                />
                <PDFRatioChart
                  title="성별 분포"
                  items={[
                    { key: 'male_ratio', label: '남성' },
                    { key: 'female_ratio', label: '여성' },
                  ]}
                  ratios={customerSegment.dimension_ratios ?? {}}
                />
                <PDFRatioChart
                  title="시간대 분포"
                  items={[
                    { key: 'time_00_06_ratio', label: '심야' },
                    { key: 'time_06_11_ratio', label: '오전' },
                    { key: 'time_11_14_ratio', label: '점심' },
                    { key: 'time_14_17_ratio', label: '오후' },
                    { key: 'time_17_21_ratio', label: '저녁' },
                    { key: 'time_21_24_ratio', label: '야간' },
                  ]}
                  ratios={customerSegment.dimension_ratios ?? {}}
                />
                <PDFRatioChart
                  title="요일 분포"
                  items={[
                    { key: 'weekday_ratio', label: '평일' },
                    { key: 'weekend_ratio', label: '주말' },
                  ]}
                  ratios={customerSegment.dimension_ratios ?? {}}
                />
              </div>

              <div className="mt-6 text-[9px] text-slate-400 font-mono">
                Analysis · customer_revenue MLP + living_population 실측 데이터 기반
              </div>
            </div>

            <PDFPageFooter reportDate={reportDate} />
          </div>
        )}
      </div>
    );
  },
);
HiddenPDFTemplate.displayName = 'HiddenPDFTemplate';

function PDFRatioChart({
  title,
  items,
  ratios,
}: {
  title: string;
  items: { key: string; label: string }[];
  ratios: Record<string, number>;
}) {
  const maxRatio = Math.max(
    0.01,
    ...items.map((it) => {
      const v = ratios[it.key];
      return typeof v === 'number' && Number.isFinite(v) ? v : 0;
    }),
  );
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-3">
        {title}
      </div>
      <div className="space-y-1.5">
        {items.map((it) => {
          const raw = ratios[it.key];
          const v = typeof raw === 'number' && Number.isFinite(raw) ? raw : 0;
          const width = Math.min(100, Math.round((v / maxRatio) * 100));
          return (
            <div key={it.key} className="flex items-center gap-2">
              <div className="w-14 shrink-0 text-[10px] text-slate-700">{it.label}</div>
              <div className="relative flex-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-[#6366f1]" style={{ width: `${width}%` }} />
              </div>
              <div className="w-12 shrink-0 text-right text-[10px] font-mono text-slate-700">
                {(v * 100).toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
