import { Info } from 'lucide-react';

type Props = {
  selectedDongCount: number;
  /** 동 당 평균 점포 수. 기본값은 마포구 16동 평균 추정치. */
  estimatePerDong?: number;
};

/**
 * 동적 피드백 박스 — 옵션으로 N동 선택 시 분석 데이터 추정.
 * 백엔드 호출 없음 (클라이언트 추정). 백엔드 정확한 카운트는 후속 작업.
 */
export function ScopeHint({ selectedDongCount, estimatePerDong = 537 }: Props) {
  const points = selectedDongCount * estimatePerDong;
  return (
    <div className="bg-card rounded-2xl border border-primary/20 shadow-sm bg-primary/5 p-5">
      <div className="flex gap-3">
        <Info size={18} className="text-primary shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-bold text-primary">현재 조건 분석 예상 규모</h3>
          <p className="text-sm text-primary/80 mt-1 leading-relaxed">
            선택된 {selectedDongCount}개 행정동 기준, 약{' '}
            <strong>{points.toLocaleString()}개</strong>의 상점 데이터 포인트가 분석에 포함됩니다.
          </p>
        </div>
      </div>
    </div>
  );
}
