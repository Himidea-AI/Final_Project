/**
 * 마포구 16개 동 히트맵 + 경쟁점 표시
 */

function MapView() {
  // TODO: React-Leaflet 지도 렌더링
  // TODO: 마포구 16개 동 GeoJSON 히트맵 (점수 기반 색상)
  // TODO: 경쟁 매장 마커 표시
  // TODO: 기존 매장 마커 + 카니발리제이션 반경 원
  // TODO: 클릭 시 동별 요약 팝업

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">마포구 상권 지도</h2>
      <p className="mt-2 text-gray-600">
        시뮬레이션 실행 후 지도가 표시됩니다.
      </p>

      <div className="mt-6 bg-gray-100 rounded-lg h-[600px] flex items-center justify-center">
        <p className="text-gray-500">React-Leaflet 지도</p>
      </div>
    </div>
  );
}

export default MapView;
