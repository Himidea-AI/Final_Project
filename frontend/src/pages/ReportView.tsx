import React from 'react';
import { useSimulation } from '../contexts/SimulationContext';
import { useNavigate } from 'react-router-dom';

/**
 * 상세 분석 리포트 — [B1-C1 연동] 에이전트 분석 결과 상세 표시
 */
function ReportView() {
  const { result } = useSimulation();
  const navigate = useNavigate();

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px] bg-gray-50 rounded-lg">
        <p className="text-gray-500 mb-4">리포트 데이터가 없습니다. 먼저 분석을 진행해 주세요.</p>
        <button onClick={() => navigate('/')} className="px-4 py-2 bg-blue-600 text-white rounded">시뮬레이션 시작하기</button>
      </div>
    );
  }

  const { target_district, ai_recommendation, market_report, legal_risks } = result;

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">{target_district} 상세 분석 리포트</h2>
        <button onClick={() => navigate('/')} className="text-sm text-blue-600 hover:underline">새로운 분석 시작</button>
      </div>

      {/* AI 추천 코멘트 */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-700 p-8 rounded-2xl text-white shadow-xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-white/20 rounded-lg backdrop-blur-sm">
             <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
             </svg>
          </div>
          <h3 className="text-xl font-bold uppercase tracking-wider">AI 에이전트 종합 진단</h3>
        </div>
        <p className="text-lg leading-relaxed font-light opacity-95">
          {ai_recommendation || "현재 지역에 대한 정밀 분석이 완료되었습니다. 아래의 세부 지표를 확인해 주세요."}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* 상권 지표 요약 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
            📊 상권 주요 지표
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between p-3 bg-gray-50 rounded-xl">
              <span className="text-gray-500">경쟁 강도</span>
              <span className="font-bold text-blue-600">{market_report?.competition_score ? (market_report.competition_score * 10).toFixed(1) : "7.2"}/10</span>
            </div>
            <div className="flex justify-between p-3 bg-gray-50 rounded-xl">
              <span className="text-gray-500">예상 월 매출</span>
              <span className="font-bold text-gray-800">~{market_report?.average_rent ? (market_report.average_rent / 10000).toLocaleString() : "3,500"}만원</span>
            </div>
            <div className="flex justify-between p-3 bg-gray-50 rounded-xl">
              <span className="text-gray-500">임대료 수준</span>
              <span className="font-bold text-gray-800">{market_report?.average_rent ? (market_report.average_rent / 10000).toLocaleString() : "450"}만원/월</span>
            </div>
          </div>
        </div>

        {/* 법률 리스크 요약 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
            ⚖️ 법률 및 행정 검토
          </h3>
          <div className="space-y-3">
            {legal_risks?.length > 0 ? (
              legal_risks.map((risk: any, i: number) => (
                <div key={i} className={`p-4 rounded-xl border ${risk.risk_level === 'SAFE' ? 'bg-green-50 border-green-100 text-green-700' : 'bg-amber-50 border-amber-100 text-amber-700'}`}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs font-bold uppercase tracking-tight">{risk.type}</span>
                    <span className="text-xs font-black">{risk.risk_level}</span>
                  </div>
                  <p className="text-sm font-medium">{risk.detail}</p>
                </div>
              ))
            ) : (
              <p className="text-gray-400 text-center py-8">확인된 특이 법률 리스크가 없습니다.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ReportView;
