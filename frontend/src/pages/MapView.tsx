/**
 * 마포구 16개 동 히트맵 + 경쟁점 표시
 */
import React from 'react';
import { useLocation } from 'react-router-dom';
import { MirofishLogPanel } from '../components/MirofishLogPanel';

function MapView() {
  const location = useLocation();
  const simData = location.state?.simData;

  // TODO: React-Leaflet 지도 렌더링
  // TODO: 마포구 16개 동 GeoJSON 히트맵 (점수 기반 색상)
  // TODO: 경쟁 매장 마커 표시
  // TODO: 기존 매장 마커 + 카니발리제이션 반경 원
  // TODO: 클릭 시 동별 요약 팝업

  return (
    <div className="relative w-full h-full"> {/* 패널 절대 배치를 위해 relative 추가 */}
      <h2 className="text-2xl font-bold text-gray-800">
        마포구 상권 지도 {simData && `- ${simData.district}`}
      </h2>
      <p className="mt-2 text-gray-600">
        {simData 
          ? `시뮬레이션 완료! 타겟 타좌표(Lat: ${simData.coordinates?.lat}, Lng: ${simData.coordinates?.lng})를 중심으로 지도가 렌더링될 예정입니다.`
          : '시뮬레이션 조건 입력 화면에서 실행 버튼을 누르면 맵 데이터 및 에이전트 로그가 수신됩니다.'}
      </p>

      {/* 팀원 원본 코드 유지 & 좌표계 연동 알림 */}
      <div className="mt-6 bg-gray-100 rounded-lg h-[600px] flex items-center justify-center">
        <p className="text-gray-500">React-Leaflet 지도</p>
      </div>
      
      {/* 반투명 미로피쉬 패널: 백엔드에서 날아온 실제 로그 데이터를 Props로 전달 */}
      {simData && (
        <div className="absolute top-0 right-0 mt-4 mr-4 z-[1000]">
          <MirofishLogPanel rawSummary={simData.mirofish_summary} threatLevel={simData.threat_level} />
        </div>
      )}
    </div>
  );
}

export default MapView;
