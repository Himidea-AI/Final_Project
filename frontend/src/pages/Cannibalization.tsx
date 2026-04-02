/**
 * 카니발리제이션 분석 화면 — 기존 매장 영향권 시각화
 */

function Cannibalization() {
  // TODO: 기존 매장 목록 표시
  // TODO: 지도에 기존 매장 + 후보지 표시 (React-Leaflet)
  // TODO: 영향권 원 (500m/1km/1.5km) 표시
  // TODO: 매장별 잠식률 바 차트 (Recharts)
  // TODO: 본사 순증 매출 계산 결과

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">카니발리제이션 분석</h2>
      <p className="mt-2 text-gray-600">
        기존 매장과의 카니발리제이션 영향을 분석합니다.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-6">
        <div className="bg-gray-100 rounded-lg h-96 flex items-center justify-center">
          <p className="text-gray-500">영향권 지도</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-gray-700 mb-4">매장별 잠식률</h3>
          {/* TODO: 잠식률 바 차트 */}
          <p className="text-gray-400">차트 영역</p>
        </div>
      </div>
    </div>
  );
}

export default Cannibalization;
