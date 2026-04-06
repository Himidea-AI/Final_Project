import React from 'react';
import { useSimulation } from '../contexts/SimulationContext';
import { useNavigate } from 'react-router-dom';

/**
 * 마포구 상권 지도 뷰 — [B1-C1 연동] 실시간 분석 결과 표시
 */
function MapView() {
  const { result } = useSimulation();
  const navigate = useNavigate();

  // 데이터가 없을 경우 입력 페이지로 안내
  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px] bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
        <p className="text-gray-500 mb-4">분석된 상권 정보가 없습니다.</p>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
        >
          시뮬레이션 시작하기
        </button>
      </div>
    );
  }

  const { map_data, summary, target_district } = result;
  
  // 좌표 추출 (기본값: 홍대입구역)
  const lat = map_data?.center?.lat || 37.5565;
  const lng = map_data?.center?.lng || 126.9239;
  const markers = map_data?.markers || [];

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold text-gray-800">
            {target_district} 상권 분석 지도
          </h2>
          <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
            분석 완료
          </span>
        </div>
        <p className="text-gray-600 leading-relaxed">
          {summary || "선택하신 지역의 상권 분석 결과입니다."}
        </p>
      </div>

      {/* 지도 영역 (이곳에 실제 Leaflet 지도가 통합될 예정입니다) */}
      <div className="relative bg-gray-200 rounded-xl overflow-hidden h-[500px] shadow-inner border border-gray-300 group">
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-100/50">
          <div className="text-center p-8 bg-white/90 backdrop-blur rounded-2xl shadow-xl border border-blue-100 max-w-md">
            <div className="text-blue-600 mb-4">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">지도 데이터 매핑 완료</h3>
            <p className="text-sm text-gray-600 mb-4">
              위도: <code className="font-mono text-blue-600 bg-blue-50 px-1 rounded">{lat}</code><br/>
              경도: <code className="font-mono text-blue-600 bg-blue-50 px-1 rounded">{lng}</code>
            </p>
            <div className="space-y-2">
              {markers.map((marker: any) => (
                <div key={marker.id} className="text-xs text-gray-500 bg-gray-50 p-2 rounded border border-gray-100">
                  마커 감지: <strong>{marker.label}</strong> ({marker.type})
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* 실제 지도 라이브러리 연동 시 주석 해제 */}
        {/* <MapContainer center={[lat, lng]} zoom={15} style={{ height: "100%", width: "100%" }}>...</MapContainer> */}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button onClick={() => navigate('/report')} className="p-4 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition shadow-sm text-center font-medium">상세 리포트 보기</button>
        <button onClick={() => navigate('/bep')} className="p-4 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition shadow-sm text-center font-medium">수익성 시뮬레이션</button>
        <button onClick={() => navigate('/')} className="p-4 bg-blue-50 border border-blue-100 rounded-lg hover:bg-blue-100 transition shadow-sm text-center font-medium text-blue-700">새 분석 시작하기</button>
      </div>
    </div>
  );
}

export default MapView;
