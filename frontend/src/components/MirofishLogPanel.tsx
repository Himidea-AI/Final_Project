import React, { useState, useEffect } from 'react';

const INITIAL_LOGS = [
  { id: 1, time: '14:19:58', agent: 'System', type: 'THINKING', message: "타겟이 '망원1동'입니다. 미로피쉬 로컬 트윈을 가동합니다." },
  { id: 2, time: '14:19:58', agent: 'MiroFishAdapter', type: 'THINKING', message: "디지털 트윈 시뮬레이션 환경(Ollama-Phi3) 초기화..." },
];

const AGENT_RESPONSES = [
  { id: 3, time: '14:19:59', agent: '저가프랜차이즈', type: 'TOOL_CALL', message: "매출 방어 전략 계산 중..." },
  { id: 4, time: '14:20:01', agent: '저가프랜차이즈', type: 'SUCCESS', message: "[발화] 즉시 아메리카노 500원 할인 이벤트와 쿠폰 폭격으로 대응하겠습니다." },
  { id: 5, time: '14:20:03', agent: '개인감성매장', type: 'TOOL_CALL', message: "매출 방어 전략 계산 중..." },
  { id: 6, time: '14:20:07', agent: '개인감성매장', type: 'SUCCESS', message: "[발화] 단골들에게 무료 디저트를 제공하고 인스타 광고 위주로 방어하겠습니다." },
  { id: 7, time: '14:20:10', agent: 'System', type: 'SUCCESS', message: "경쟁/카니발리제이션 분석 노드 완료." },
];

export const MirofishLogPanel: React.FC = () => {
  const [logs, setLogs] = useState(INITIAL_LOGS);
  const [threatLevel, setThreatLevel] = useState('Pending');

  useEffect(() => {
    let delay = 1000;
    AGENT_RESPONSES.forEach((log, index) => {
      setTimeout(() => {
        setLogs(prev => [...prev, log]);
        if (index === AGENT_RESPONSES.length - 1) {
          setThreatLevel('🔴 위험도: 강함');
        }
      }, delay);
      delay += 1500;
    });
  }, []);

  return (
    <div className="absolute top-4 right-4 w-96 max-h-[500px] bg-slate-900/85 backdrop-blur-md rounded-xl p-0 border border-slate-700/50 shadow-2xl overflow-hidden flex flex-col z-[1000]">
      <div className="bg-slate-800/80 px-4 py-3 border-b border-slate-700/50 flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold text-slate-100 flex items-center">
            <span className="w-2 h-2 rounded-full bg-green-400 mr-2 animate-pulse"></span>
            MiroFish Live Logs (망원1동)
          </h2>
          <p className="text-[10px] text-slate-400 mt-0.5">{threatLevel === 'Pending' ? '에이전트 토론 중...' : threatLevel}</p>
        </div>
        <div className="flex space-x-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-slate-600 hover:bg-red-500 cursor-pointer"></div>
        </div>
      </div>
      
      <div className="p-4 flex-1 overflow-y-auto space-y-3 font-mono text-[11px] scrollbar-thin scrollbar-thumb-slate-700">
        {logs.map((log) => (
          <div key={log.id} className="flex flex-col p-2.5 rounded bg-slate-950/50 border-l-2 border-slate-600">
            <div className="flex justify-between text-slate-400 mb-1">
              <span className="font-bold text-blue-400">[{log.agent}]</span>
              <span>{log.time}</span>
            </div>
            <div className="flex flex-wrap items-start">
              <span className={`mr-1.5 px-1.5 py-[1px] rounded text-[9px] font-bold mt-0.5 ${
                log.type === 'THINKING' ? 'bg-purple-900/50 text-purple-300' :
                log.type === 'TOOL_CALL' ? 'bg-yellow-900/50 text-yellow-300' :
                log.type === 'SUCCESS' ? 'bg-emerald-900/50 text-emerald-300' :
                'bg-slate-700 text-slate-300'
              }`}>
                {log.type}
              </span>
              <span className={`flex-1 break-words ${log.type === 'SUCCESS' && log.message.includes('발화') ? 'text-green-300' : 'text-slate-300'}`}>
                {log.message}
              </span>
            </div>
          </div>
        ))}
        
        {threatLevel === 'Pending' && (
          <div className="flex items-center space-x-1.5 text-slate-500 p-1 pl-2">
            <span className="animate-bounce">●</span>
            <span className="animate-bounce delay-100">●</span>
            <span className="animate-bounce delay-200">●</span>
          </div>
        )}
      </div>
    </div>
  );
};
