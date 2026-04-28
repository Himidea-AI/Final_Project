import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSimulationStore, type SimulationStatus } from '../stores/simulationStore';
import { useToastStore } from '../stores/toastStore';

export function useCompletionToast() {
  const status = useSimulationStore((s) => s.status);
  const error = useSimulationStore((s) => s.error);
  const push = useToastStore((s) => s.push);
  const navigate = useNavigate();
  const prevRef = useRef<SimulationStatus>('idle');

  useEffect(() => {
    const prev = prevRef.current;
    prevRef.current = status;

    if (prev === 'running' && status === 'done') {
      push({
        variant: 'success',
        title: 'ANALYSIS COMPLETE',
        description: '시뮬레이션 결과가 준비됐습니다.',
        action: { label: '결과 보기', onClick: () => navigate('/dashboard') },
      });
    } else if (prev === 'running' && status === 'error') {
      push({
        variant: 'error',
        title: 'SIMULATION FAILED',
        description: error ?? '알 수 없는 오류',
      });
    }
  }, [status, error, push, navigate]);
}
