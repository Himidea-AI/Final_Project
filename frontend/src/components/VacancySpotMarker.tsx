import { useEffect, useRef } from 'react';

interface VacancySpotMarkerProps {
  /** 카카오맵 인스턴스 (kakao.maps.Map). null/undefined 시 noop. */
  map: any;
  lat: number;
  lng: number;
  /** 반경 원 크기 (m). default 500m — vacancy_pse cannibalization 반경과 일치. */
  radiusM?: number;
}

/**
 * vacancy 매장 위치 강조 — 빨간 펄스 마커 + 반경 500m 점선 원.
 * AbmPersonaMap 의 mode='vacancy' + vacancySpot 있을 때 렌더.
 *
 * 카카오맵 SDK 의 CustomOverlay (CSS keyframes 펄스) + Circle (반경) 를 사용한다.
 * map prop 이 없거나 (window as any).kakao 가 미로드된 환경 (jsdom 테스트 등) 에선
 * 안전하게 noop.
 */
export default function VacancySpotMarker({
  map,
  lat,
  lng,
  radiusM = 500,
}: VacancySpotMarkerProps) {
  const markerRef = useRef<any>(null);
  const circleRef = useRef<any>(null);

  useEffect(() => {
    if (!map || typeof window === 'undefined') return;
    const kakao = (window as any).kakao;
    if (!kakao?.maps?.LatLng || !kakao?.maps?.CustomOverlay || !kakao?.maps?.Circle) {
      return;
    }

    const position = new kakao.maps.LatLng(lat, lng);

    // 펄스 마커 (CSS keyframes 애니메이션 inline) — 카카오 CustomOverlay
    const content = `
      <div style="
        width: 24px;
        height: 24px;
        background: var(--danger);
        border: 3px solid white;
        border-radius: 50%;
        animation: vacancy-spot-pulse 1.5s infinite;
        box-shadow: 0 0 8px rgba(255, 56, 0, 0.8);
        pointer-events: none;
      "></div>
      <style>
        @keyframes vacancy-spot-pulse {
          0% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.3); opacity: 0.6; }
          100% { transform: scale(1); opacity: 1; }
        }
      </style>
    `;
    markerRef.current = new kakao.maps.CustomOverlay({
      position,
      content,
      yAnchor: 0.5,
      xAnchor: 0.5,
      zIndex: 5,
    });
    markerRef.current.setMap(map);

    // 반경 원 (default 500m) — 점선, 빨간 fill 5%
    circleRef.current = new kakao.maps.Circle({
      center: position,
      radius: radiusM,
      strokeWeight: 2,
      strokeColor: '#fb565b',
      strokeOpacity: 0.6,
      strokeStyle: 'dashed',
      fillColor: '#fb565b',
      fillOpacity: 0.05,
    });
    circleRef.current.setMap(map);

    return () => {
      try {
        markerRef.current?.setMap(null);
      } catch {
        /* noop */
      }
      try {
        circleRef.current?.setMap(null);
      } catch {
        /* noop */
      }
      markerRef.current = null;
      circleRef.current = null;
    };
  }, [map, lat, lng, radiusM]);

  return null;
}
