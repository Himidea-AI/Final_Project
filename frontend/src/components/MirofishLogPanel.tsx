import React, { useState, useEffect } from 'react';

interface Props {
  rawSummary: string;
  threatLevel: string;
}

export const MirofishLogPanel: React.FC<Props> = ({ rawSummary, threatLevel }) => {
  const [logs, setLogs] = useState<{id: number, time: string, agent: string, type: string, message: string}[]>([]);
  const [isTyping, setIsTyping] = useState(true);

  useEffect(() => {
    // Parse the rawSummary string from backend into log lines
    // Expected format: "[디지털트윈 경고] ... \n- 저가매장 대응: ... \n- 감성매장 대응: ..."
    const lines = rawSummary.split('\n').filter(line => line.trim() !== '');
    
    let delay = 500;
    const parsedLogs: any[] = [];
    
    lines.forEach((line, index) => {
      let agentName = "System";
      let logType = "SUCCESS";
      let message = line;
      
      if (line.includes("- ")) {
        const parts = line.split(":");
        if (parts.length >= 2) {
          agentName = parts[0].replace("- ", "").trim();
          logType = "발화";
          message = parts.slice(1).join(":").trim();
        }
      } else if (line.includes("경고")) {
        logType = "WARNING";
      }

      parsedLogs.push({
        id: index + 1,
        time: new Date().toLocaleTimeString('ko-KR', { hour12: false }),
        agent: agentName,
        type: logType,
        message: message,
      });
    });

    // Animate rendering
    parsedLogs.forEach((log, index) => {
      setTimeout(() => {
        setLogs(prev => [...prev, log]);
        if (index === parsedLogs.length - 1) {
          setIsTyping(false);
        }
      }, delay);
      delay += 1200;
    });
  }, [rawSummary]);

  return (
    <div className="w-96 max-h-[500px] bg-slate-900/85 backdrop-blur-md rounded-xl p-0 border border-slate-700/50 shadow-2xl overflow-hidden flex flex-col">
      <div className="bg-slate-800/80 px-4 py-3 border-b border-slate-700/50 flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold text-slate-100 flex items-center">
            <span className={`w-2 h-2 rounded-full mr-2 ${isTyping ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'}`}></span>
            MiroFish Live Logs (Server Sync)
          </h2>
          <p className="text-[10px] text-slate-400 mt-0.5">최종 위협도 레벨: {threatLevel}</p>
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
                log.type === 'WARNING' ? 'bg-red-900/50 text-red-300' :
                log.type === '발화' ? 'bg-purple-900/50 text-purple-300' :
                'bg-emerald-900/50 text-emerald-300'
              }`}>
                {log.type}
              </span>
              <span className={`flex-1 break-words ${log.type === '발화' ? 'text-green-300' : 'text-slate-300'}`}>
                {log.message}
              </span>
            </div>
          </div>
        ))}
        
        {isTyping && (
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
