import React, { createContext, useContext, useState, ReactNode } from 'react';

/** [B1-C1 연동] 분석 결과 데이터를 전역으로 관리하는 컨텍스트 */
interface SimulationContextType {
  result: any | null;
  setSimulationResult: (data: any) => void;
  resetResult: () => void;
}

const SimulationContext = createContext<SimulationContextType | undefined>(undefined);

export const SimulationProvider = ({ children }: { children: ReactNode }) => {
  const [result, setResult] = useState<any | null>(null);

  const setSimulationResult = (data: any) => {
    console.log("[SimulationContext] 결과 업데이트:", data);
    setResult(data);
  };

  const resetResult = () => {
    setResult(null);
  };

  return (
    <SimulationContext.Provider value={{ result, setSimulationResult, resetResult }}>
      {children}
    </SimulationContext.Provider>
  );
};

export const useSimulation = () => {
  const context = useContext(SimulationContext);
  if (context === undefined) {
    throw new Error('useSimulation must be used within a SimulationProvider');
  }
  return context;
};
