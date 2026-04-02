/**
 * React-Leaflet 지도 컴포넌트 — 마포구 히트맵, 경쟁점 마커, 영향권 원 표시
 */

// TODO: MapContainer, TileLayer, GeoJSON, Circle, Marker 임포트
// TODO: 마포구 중심 좌표 (37.5636, 126.9084)
// TODO: GeoJSON 오버레이 (16개 동 경계)
// TODO: 동별 점수 기반 색상 그라데이션
// TODO: 경쟁 매장 마커 + 팝업
// TODO: 카니발리제이션 반경 원 (500m/1km/1.5km)

function MapComponent() {
  return (
    <div className="w-full h-96 bg-gray-200 rounded-lg flex items-center justify-center">
      <p className="text-gray-500">지도 컴포넌트 (React-Leaflet)</p>
    </div>
  );
}

export default MapComponent;
