import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAbmStore, type AbmStatus } from '../stores/abmStore';
import { useToastStore } from '../stores/toastStore';

export function useAbmCompletionToast() {
  const status = useAbmStore((s) => s.status);
  const error = useAbmStore((s) => s.error);
  const focusLabel = useAbmStore((s) => s.focusSpot?.label);
  const push = useToastStore((s) => s.push);
  const navigate = useNavigate();
  const prevRef = useRef<AbmStatus>('idle');

  useEffect(() => {
    const prev = prevRef.current;
    prevRef.current = status;

    if (prev === 'running' && status === 'done') {
      push({
        variant: 'success',
        title: 'ABM ANALYSIS COMPLETE',
        description: focusLabel
          ? `${focusLabel} 페르소나 시뮬 결과가 준비됐습니다.`
          : 'ABM 시뮬레이션 결과가 준비됐습니다.',
        action: { label: '결과 보기', onClick: () => navigate('/dashboard/abm') },
        dedupeKey: 'abm-success',
      });
    } else if (prev === 'running' && status === 'error') {
      push({
        variant: 'error',
        title: 'ABM SIMULATION FAILED',
        description: error ?? '알 수 없는 오류',
        dedupeKey: 'abm-error',
      });
    }
  }, [status, error, focusLabel, push, navigate]);
}
