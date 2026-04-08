import React, { useState, useEffect } from 'react';

// 시뮬레이션 상태 및 로그 목업 데이터 (백엔드 Ollama 응답 모사)
const INITIAL_LOGS = [
  { id: 1, time: '14:19:58', agent: 'System', type: 'THINKING', message: "타겟이 '망원1동'입니다. 미로피쉬 로컬 트윈을 가동합니다." },
  { id: 2, time: '14:19:58', agent: 'MiroFishAdapter', type: 'THINKING', message: "망원1동 디지털 트윈 시뮬레이션 환경(Ollama-Phi3) 초기화..." },
];

const AGENT_RESPONSES = [
  { id: 3, time: '14:19:59', agent: '저가프랜차이즈 점주', type: 'TOOL_CALL', message: "매출 방어 전략 계산 중..." },
  { id: 4, time: '14:20:01', agent: '저가프랜차이즈 점주', type: 'SUCCESS', message: "[발화] 즉시 아메리카노 500원 할인 이벤트와 쿠폰 폭격으로 골목 유동인구를 모두 빨아들이겠습니다." },
  { id: 5, time: '14:20:03', agent: '개인감성매장 점주', type: 'TOOL_CALL', message: "매출 방어 전략 계산 중..." },
  { id: 6, time: '14:20:07', agent: '개인감성매장 점주', type: 'SUCCESS', message: "[발화] 단골들에게 무료 디저트를 제공하고 인스타그램 광고 예산을 2배로 늘리겠습니다." },
  { id: 7, time: '14:20:10', agent: 'System', type: 'SUCCESS', message: "경쟁/카니발리제이션 분석 노드 처리 완료." },
];

export const MirofishDashboard: React.FC = () => {
  const [logs, setLogs] = useState(INITIAL_LOGS);
  const [threatLevel, setThreatLevel] = useState('Pending');

  // 애니메이션 효과로 로그가 실시간 추가되는 것처럼 보이게 함
  useEffect(() => {
    let delay = 1000;
    AGENT_RESPONSES.forEach((log, index) => {
      setTimeout(() => {
        setLogs(prev => [...prev, log]);
        if (index === AGENT_RESPONSES.length - 1) {
          setThreatLevel('High (위험도: 강함)');
        }
      }, delay);
      delay += 1500;
    });
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-8 font-sans">
      <header className="mb-8 border-b border-slate-700 pb-4">
        <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">
          MiroFish Digital Twin Dashboard (망원 1동)
        </h1>
        <p className="text-slate-400 mt-2">상권 경쟁 시뮬레이션 다중 에이전트 모니터링</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* State Summary Panel */}
        <div className="col-span-1 bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-xl">
          <h2 className="text-xl font-semibold mb-4 text-white flex items-center">
            <span className="w-3 h-3 rounded-full bg-green-400 mr-2 animate-pulse"></span>
            시뮬레이션 상태
          </h2>
          
          <div className="space-y-4">
            <div className="bg-slate-900 rounded p-4 border border-slate-800">
              <p className="text-slate-400 text-sm">타겟 지역</p>
              <p className="text-lg font-medium text-blue-300">서울시 마포구 망원1동</p>
            </div>
            
            <div className="bg-slate-900 rounded p-4 border border-slate-800">
              <p className="text-slate-400 text-sm">침투 업종</p>
              <p className="text-lg font-medium">카페 (창업자 페르소나)</p>
            </div>

            <div className="bg-slate-900 rounded p-4 border border-slate-800">
              <p className="text-slate-400 text-sm">경쟁 카니발리제이션 위협도</p>
              <p className={`text-xl font-bold ${threatLevel.includes('High') ? 'text-red-400' : 'text-slate-300'}`}>
                {threatLevel}
              </p>
            </div>
          </div>
        </div>

        {/* Live Agent Terminal */}
        <div className="col-span-2 bg-slate-950 rounded-xl p-0 border border-slate-700 shadow-xl overflow-hidden flex flex-col">
          <div className="bg-slate-800 px-6 py-3 border-b border-slate-700 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-slate-200">Live Agent Interactions (Phi-3)</h2>
            <div className="flex space-x-2">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
            </div>
          </div>
          
          <div className="p-6 h-[500px] overflow-y-auto space-y-4 font-mono text-sm">
            {logs.map((log) => (
              <div key={log.id} className="flex flex-col p-3 rounded bg-slate-900 border-l-4 border-slate-700 hover:bg-slate-800 transition-colors">
                <div className="flex justify-between text-slate-400 mb-1 text-xs">
                  <span className="font-bold text-blue-400">[{log.agent}]</span>
                  <span>{log.time}</span>
                </div>
                <div className="flex">
                  <span className={`mr-2 px-2 py-0.5 rounded text-xs font-bold ${
                    log.type === 'THINKING' ? 'bg-purple-900/50 text-purple-300' :
                    log.type === 'TOOL_CALL' ? 'bg-yellow-900/50 text-yellow-300' :
                    log.type === 'SUCCESS' ? 'bg-emerald-900/50 text-emerald-300' :
                    'bg-slate-700 text-slate-300'
                  }`}>
                    {log.type}
                  </span>
                  <span className={`${log.type === 'SUCCESS' && log.message.includes('발화') ? 'text-green-300 font-medium' : 'text-slate-300'}`}>
                    {log.message}
                  </span>
                </div>
              </div>
            ))}
            
            {threatLevel === 'Pending' && (
              <div className="flex items-center space-x-2 text-slate-500 p-2">
                <span className="animate-bounce">●</span>
                <span className="animate-bounce delay-100">●</span>
                <span className="animate-bounce delay-200">●</span>
                <span className="ml-2">에이전트 반응 생성 중...</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
