/**
 * 동 vs 동 비교 화면 — 나란히 비교
 */

function Comparison() {
  // TODO: 비교 대상 동 2~3개 선택
  // TODO: 항목별 비교표 (매출, BEP, 생존율, 경쟁도)
  // TODO: 나란히 비교 바 차트 (Recharts)
  // TODO: 종합 추천 순위
  // TODO: ScoreCard 컴포넌트 활용

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">동 비교 분석</h2>
      <p className="mt-2 text-gray-600">비교할 동을 선택하세요.</p>

      <div className="mt-6 grid grid-cols-3 gap-6">
        {/* TODO: ScoreCard 3개 */}
        <div className="bg-white rounded-lg shadow p-6 h-48 flex items-center justify-center">
          <p className="text-gray-400">망원1동</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6 h-48 flex items-center justify-center">
          <p className="text-gray-400">공덕동</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6 h-48 flex items-center justify-center">
          <p className="text-gray-400">대흥동</p>
        </div>
      </div>
    </div>
  );
}

export default Comparison;
