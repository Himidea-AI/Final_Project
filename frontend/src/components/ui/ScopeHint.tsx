import { useEffect, useMemo, useState } from 'react';
import { Info } from 'lucide-react';
import apiClient from '../../api/client';

type Props = {
  selectedDongs: string[];
  /** 카카오 카테고리 prefix 필터 (옵션). */
  category?: string;
  /** Fallback 동 당 평균 점포 수 (백엔드 fetch 실패 시). */
  estimatePerDong?: number;
};

/**
 * 동적 피드백 박스 — 선택 동 실제 매장 수 표시.
 * `/stores/count-by-dongs` 백엔드 호출 → 실패 시 estimatePerDong 폴백.
 */
export function ScopeHint({ selectedDongs, category, estimatePerDong = 256 }: Props) {
  const [actualCount, setActualCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const dongsKey = useMemo(() => selectedDongs.join(','), [selectedDongs]);

  useEffect(() => {
    if (!dongsKey) {
      setActualCount(0);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    apiClient
      .get('/stores/count-by-dongs', {
        params: { dongs: dongsKey, category },
        signal: ctrl.signal,
      })
      .then((res) => {
        const t = res.data?.total;
        setActualCount(typeof t === 'number' ? t : null);
      })
      .catch((err) => {
        if (err?.name !== 'CanceledError' && err?.name !== 'AbortError') {
          console.warn('[ScopeHint] count fetch failed:', err);
        }
        setActualCount(null);
      })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [dongsKey, category]);

  const fallback = selectedDongs.length * estimatePerDong;
  const points = actualCount ?? fallback;

  return (
    <div className="box-glass rounded-2xl p-6 ring-1 ring-primary/20">
      <div className="flex gap-3">
        <Info size={18} className="text-primary shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-bold text-primary">현재 조건 분석 예상 규모</h3>
          <p className="text-sm text-primary/80 mt-1 leading-relaxed">
            선택된 {selectedDongs.length}개 행정동 기준,{' '}
            {loading && actualCount === null ? (
              <em className="text-primary/60">집계 중...</em>
            ) : (
              <>
                <strong>{points.toLocaleString()}개</strong>의 상점 데이터 포인트가 분석에
                포함됩니다.
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
