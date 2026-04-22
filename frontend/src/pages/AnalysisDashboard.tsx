// 🚨 [AI 개발 규칙: TEAMMATE UI PROTECTED]
// 1. 이 파일의 JSX 구조, Tailwind 클래스, 컴포넌트 배치는 프론트엔드 팀원의 자산입니다.
// 2. 안티그래비티는 오직 '데이터 바인딩(value, onChange)'과 '결과 출력 로직'만 수정할 수 있습니다.
// 3. UI 레이아웃을 변경해야 할 경우 반드시 사용자(담당자)에게 먼저 허락을 구하십시오.

import React, { useState, useEffect } from 'react';
import { useSimulation } from '../hooks/useSimulation';
import MetricCharts from '../components/SimulationResult/MetricCharts';
import ReportViewer from '../components/SimulationResult/ReportViewer';
import {
  Loader2,
  MapPin,
  Coffee,
  AlertTriangle,
  ShieldCheck,
  Users,
  BarChart3,
  FileText,
  Play,
  Activity,
} from 'lucide-react';

import { motion, AnimatePresence } from 'framer-motion';

const LOADING_STEPS = [
  {
    p: 10,
    m: '상권 전문가(Market Analyst)가 지역 기반 데이터를 수집 중입니다...',
    icon: <BarChart3 className="text-blue-500" />,
  },
  {
    p: 35,
    m: '인구 전문가(Population Analyst)가 유동인구 및 배후세대 추이를 분석 중입니다...',
    icon: <Users className="text-emerald-500" />,
  },
  {
    p: 65,
    m: '법률 전문가(Legal Advisor)가 상가임대차 법령 및 리스크를 검토 중입니다...',
    icon: <ShieldCheck className="text-indigo-500" />,
  },
  {
    p: 85,
    m: '감독관(Supervisor)이 모든 분석 결과를 취합하여 종합 리포트를 생성 중입니다...',
    icon: <FileText className="text-indigo-500" />,
  },
  {
    p: 95,
    m: '최종 리포트 인쇄 및 대시보드 시뮬레이션 준비 중...',
    icon: <Loader2 className="text-gray-400 animate-spin" />,
  },
];

const AnalysisDashboard: React.FC = () => {
  const { execute, loading, error, result } = useSimulation();
  const [district, setDistrict] = useState('서교동');
  const [brandName, setBrandName] = useState('메가커피');

  // Progress state for procedural loading
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState(LOADING_STEPS[0].m);
  const [currentStepIdx, setCurrentStepIdx] = useState(0);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (loading) {
      interval = setInterval(() => {
        setProgress((prev) => {
          let increment = 2.5;
          if (prev > 70) increment = 0.8;
          if (prev > 90) increment = 0.2;
          if (prev > 98) increment = 0.05;
          return Math.min(prev + increment, 99.9);
        });
      }, 100);
    } else if (result) {
      setProgress(100);
    } else {
      setProgress(0);
    }
    return () => clearInterval(interval);
  }, [loading, result]);

  useEffect(() => {
    if (!loading) return;
    const stepIdx = LOADING_STEPS.findIndex((s, idx) => {
      const nextStep = LOADING_STEPS[idx + 1];
      return progress >= s.p && (!nextStep || progress < nextStep.p);
    });
    if (stepIdx !== -1) {
      setCurrentStepIdx(stepIdx);
      setStatusMessage(LOADING_STEPS[stepIdx].m);
    }
  }, [progress, loading]);

  const handleAnalyze = () => {
    execute({
      business_type: 'cafe',
      brand_name: brandName,
      target_district: district,
      existing_stores: [],
      initial_investment: 150000000,
      monthly_rent: 0,
      simulation_months: 12,
      scenarios: ['base'],
    });
  };

  // 🚨 [DANGER ZONE: DO NOT TOUCH UI STRUCTURE]
  // 이 아래 return 문 내부의 JSX 구조는 절대 수정 금지입니다.
  return (
    <div className="min-h-screen bg-[#1e1b18] text-[#e2e8f0] font-sans selection:bg-indigo-500/30">
      {/* 글로벌 헤더 높이만큼 패딩 추가 (pt-24) */}
      <div className="max-w-7xl mx-auto px-6 md:px-10 pt-32 pb-20">
        {/* 상단 컨트롤 바 */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12 bg-[#2c2825] p-6 rounded-3xl border border-[#3a3633] shadow-2xl">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white flex items-center gap-3">
              <span className="w-2 h-8 bg-indigo-500 rounded-full" />
              SPOTTER <span className="text-indigo-400">INSIGHTS</span>
            </h1>
            <p className="text-gray-500 mt-1 font-mono text-xs tracking-widest uppercase">
              Multi-Agent Simulation Engine
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap items-center gap-4"
          >
            <div className="flex items-center gap-3 bg-[#1e1b18] px-4 py-2.5 rounded-2xl border border-[#3a3633] focus-within:border-indigo-500/50 transition-colors">
              <MapPin size={16} className="text-indigo-400" />
              <div className="flex flex-col">
                <span className="text-[10px] text-gray-500 font-bold uppercase tracking-tighter">
                  District
                </span>
                <input
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                  className="bg-transparent border-none focus:ring-0 text-sm font-bold w-24 text-white p-0"
                  placeholder="지역"
                />
              </div>
            </div>
            <div className="flex items-center gap-3 bg-[#1e1b18] px-4 py-2.5 rounded-2xl border border-[#3a3633] focus-within:border-indigo-500/50 transition-colors">
              <Coffee size={16} className="text-indigo-400" />
              <div className="flex flex-col">
                <span className="text-[10px] text-gray-500 font-bold uppercase tracking-tighter">
                  Brand
                </span>
                <input
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  className="bg-transparent border-none focus:ring-0 text-sm font-bold w-32 text-white p-0"
                  placeholder="브랜드"
                />
              </div>
            </div>

            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-8 py-4 rounded-2xl text-sm font-black transition-all flex items-center gap-2 disabled:opacity-50 shadow-lg shadow-indigo-500/20 active:scale-95"
            >
              {loading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <Play size={20} fill="currentColor" />
              )}
              분석 시작
            </button>
          </motion.div>
        </header>

        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.05 }}
              className="h-[50vh] flex flex-col items-center justify-center text-center px-4"
            >
              <div className="w-full max-w-xl mb-12">
                <div className="flex justify-between items-end mb-6">
                  <div className="flex items-center gap-4">
                    <div className="p-4 bg-[#2c2825] rounded-2xl border border-[#3a3633] shadow-xl text-indigo-400">
                      {LOADING_STEPS[currentStepIdx]?.icon || <Activity />}
                    </div>
                    <div className="text-left">
                      <p className="text-xs font-bold text-indigo-400 uppercase tracking-[0.2em] mb-1 animate-pulse">
                        Processing Simulation
                      </p>
                      <h3 className="text-xl font-black text-white">에이전트 군단 협업 분석 중</h3>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="text-4xl font-black text-indigo-400 tabular-nums">
                      {Math.floor(progress)}%
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono tracking-tighter">
                      SYNCING DATA...
                    </span>
                  </div>
                </div>

                {/* Custom Procedural Progress Bar */}
                <div className="w-full h-3 bg-[#2c2825] rounded-full overflow-hidden border border-[#3a3633] p-[2px]">
                  <motion.div
                    className="h-full bg-gradient-to-r from-indigo-600 via-purple-500 to-indigo-400 rounded-full shadow-[0_0_15px_rgba(99,102,241,0.5)]"
                    style={{ width: `${progress}%` }}
                    transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
                  />
                </div>
              </div>

              <motion.div
                key={statusMessage}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-[#2c2825] px-8 py-6 rounded-3xl border border-[#3a3633] shadow-2xl max-w-2xl relative overflow-hidden"
              >
                <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500" />
                <p className="text-gray-300 font-bold leading-relaxed text-lg">{statusMessage}</p>
                <div className="flex justify-center gap-2 mt-6">
                  {LOADING_STEPS.map((_, i) => (
                    <div
                      key={i}
                      className={`h-1 rounded-full transition-all duration-500 ${
                        i <= currentStepIdx ? 'w-8 bg-indigo-500' : 'w-4 bg-[#3a3633]'
                      }`}
                    />
                  ))}
                </div>
              </motion.div>
            </motion.div>
          ) : error ? (
            <motion.div
              key="error"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-red-500/5 border border-red-500/20 p-12 rounded-[2.5rem] text-red-400 flex flex-col items-center gap-6 text-center"
            >
              <div className="p-5 bg-[#2c2825] rounded-full shadow-2xl border border-red-500/30">
                <AlertTriangle size={48} />
              </div>
              <div>
                <h3 className="text-2xl font-black mb-2">분석 엔진 오류</h3>
                <p className="text-sm text-gray-400 max-w-md leading-relaxed">{error}</p>
              </div>
              <button
                onClick={handleAnalyze}
                className="mt-4 bg-red-600 hover:bg-red-500 text-white px-10 py-3 rounded-2xl font-black text-sm transition-all shadow-lg shadow-red-600/20"
              >
                엔진 재가동
              </button>
            </motion.div>
          ) : result ? (
            <motion.div
              key="result"
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start"
            >
              {/* 좌측: 정량 지표 패널 */}
              <div className="lg:col-span-4 space-y-8 h-full">
                <MetricCharts metrics={result.analysis_metrics} />

                {/* 법률 리스크 카드 — Premium Dark Style */}
                <div className="bg-[#2c2825] p-8 rounded-[2rem] border border-[#3a3633] shadow-2xl relative overflow-hidden group">
                  <div className="absolute -top-10 -right-10 w-40 h-40 bg-indigo-500/5 rounded-full blur-3xl group-hover:bg-indigo-500/10 transition-colors duration-700" />
                  <h3 className="text-lg font-black mb-8 flex items-center gap-3 text-white border-b border-[#3a3633] pb-4">
                    <ShieldCheck className="text-indigo-400" size={24} />
                    LEGAL RISK REPORT
                  </h3>
                  <div className="space-y-4">
                    {result.legal_risks?.map((risk, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="flex items-start gap-4 p-5 rounded-2xl bg-[#1e1b18] border border-[#3a3633] hover:border-indigo-500/30 transition-colors"
                      >
                        <div
                          className={`mt-1.5 w-2 h-2 rounded-full shrink-0 shadow-[0_0_8px] ${
                            risk.risk_level === 'HIGH'
                              ? 'bg-red-500 shadow-red-500/50'
                              : risk.risk_level === 'MEDIUM'
                                ? 'bg-indigo-500 shadow-indigo-500/50'
                                : 'bg-green-500 shadow-green-500/50'
                          }`}
                        />
                        <div>
                          <p className="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1">
                            {risk.type}
                          </p>
                          <p className="text-sm font-bold text-gray-300 leading-snug">
                            {risk.detail}
                          </p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 우측: 정성 리포트 패널 */}
              <div className="lg:col-span-8 h-[calc(100vh-280px)] min-h-[600px] sticky top-32">
                <ReportViewer report={result.analysis_report} />
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="h-[60vh] flex flex-col items-center justify-center border-2 border-dashed border-[#3a3633] rounded-[3rem] bg-[#2c2825]/30 backdrop-blur-md relative overflow-hidden"
            >
              <div
                className="absolute inset-0 opacity-10 pointer-events-none"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23818cf8' fill-opacity='0.1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
                }}
              />

              <div className="relative">
                <div className="absolute inset-0 bg-indigo-500 blur-[60px] opacity-20 animate-pulse" />
                <div className="bg-[#2c2825] p-8 rounded-[2.5rem] shadow-2xl mb-8 transform rotate-3 border border-[#3a3633] relative z-10">
                  <Activity size={64} className="text-indigo-400" />
                </div>
              </div>

              <h2 className="text-3xl font-black text-white mb-4 tracking-tight">
                Ready for <span className="text-indigo-400 italic">Insights?</span>
              </h2>
              <p className="text-gray-500 font-medium max-w-sm text-center leading-relaxed">
                상단 제어 패널에서 분석할 지역과 브랜드를 설정하세요.
                <br />
                SPOTTER의 멀티 에이전트 인텔리전스가 가동을 기다리고 있습니다.
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      </div>
    </div>
  );
};

export default AnalysisDashboard;
