import { useEffect } from 'react';
import { useSimulationStore } from '../../stores/simulationStore';

export function BeforeUnloadGuard() {
  const status = useSimulationStore((s) => s.status);

  useEffect(() => {
    if (status !== 'running') return;

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Chrome requires returnValue to be set.
      e.returnValue = '시뮬레이션이 진행 중입니다. 정말 나가시겠어요?';
      return e.returnValue;
    };

    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [status]);

  return null;
}
