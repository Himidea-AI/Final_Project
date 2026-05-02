import { useEffect, useRef, useState } from 'react';
import { MapPin, Loader2, Check, AlertCircle } from 'lucide-react';
import { useKakaoMap } from '../kakao/useKakaoMap';

/**
 * 출점 후보지 좌표 입력 — 학교환경위생정화구역(rule_school_zone) 거리 룰 트리거.
 *
 * 사용자 친화 UX:
 *   1) 주소 입력 + 카카오 services geocoder 로 자동 좌표 변환 (기본).
 *   2) 좌표 직접 입력 토글 — geocoding 실패 시 fallback.
 *
 * 미입력(null) 시 backend `rule_school_zone` 이 보수적 caution 처리.
 * 주점(pub)에서만 강제 차단 — cafe/restaurant 는 좌표 없어도 OK.
 */

type GeocoderResult = {
  address_name: string;
  road_address?: { address_name?: string } | null;
  x: string; // longitude (경도)
  y: string; // latitude (위도)
};

interface KakaoServices {
  Geocoder: new () => {
    addressSearch: (
      query: string,
      cb: (results: GeocoderResult[], status: 'OK' | 'ZERO_RESULT' | 'ERROR') => void,
    ) => void;
  };
  Status: { OK: 'OK'; ZERO_RESULT: 'ZERO_RESULT'; ERROR: 'ERROR' };
}

interface KakaoMaps {
  services: KakaoServices;
}

interface KakaoGlobal {
  maps: KakaoMaps;
}

type Props = {
  /** 현재 lat/lon. null 이면 미입력 상태. */
  lat: number | null;
  lon: number | null;
  /** 좌표 변경 콜백. 둘 다 null 이면 미입력으로 간주. */
  onChange: (lat: number | null, lon: number | null) => void;
};

export function StoreLocationInput({ lat, lon, onChange }: Props) {
  const { ready, error: sdkError } = useKakaoMap();
  const [address, setAddress] = useState('');
  const [resolvedAddress, setResolvedAddress] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [manualMode, setManualMode] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 외부에서 lat/lon 이 reset (null) 되면 내부 표시도 정리
  useEffect(() => {
    if (lat == null && lon == null) {
      setResolvedAddress(null);
    }
  }, [lat, lon]);

  const handleAddressLookup = (query: string) => {
    setSearchError(null);
    if (!query.trim()) {
      onChange(null, null);
      setResolvedAddress(null);
      return;
    }
    if (!ready) {
      setSearchError('카카오 지도 SDK 로딩 중입니다. 잠시 후 다시 시도해주세요.');
      return;
    }
    const w = window as unknown as { kakao?: KakaoGlobal };
    const services = w.kakao?.maps?.services;
    if (!services?.Geocoder) {
      setSearchError('카카오 services 라이브러리를 사용할 수 없습니다.');
      return;
    }
    setSearching(true);
    const geocoder = new services.Geocoder();
    geocoder.addressSearch(query, (results, status) => {
      setSearching(false);
      if (status !== 'OK' || !results.length) {
        setSearchError('주소를 찾을 수 없습니다. 다시 입력해주세요.');
        onChange(null, null);
        setResolvedAddress(null);
        return;
      }
      const first = results[0];
      const newLat = parseFloat(first.y);
      const newLon = parseFloat(first.x);
      if (Number.isNaN(newLat) || Number.isNaN(newLon)) {
        setSearchError('좌표 변환 실패');
        return;
      }
      onChange(newLat, newLon);
      setResolvedAddress(first.road_address?.address_name || first.address_name);
    });
  };

  const handleAddressChange = (val: string) => {
    setAddress(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    // 사용자 입력 멈춤 후 600ms 뒤 자동 조회
    debounceRef.current = setTimeout(() => handleAddressLookup(val), 600);
  };

  const handleManualLat = (v: string) => {
    const parsed = v === '' ? null : parseFloat(v);
    if (parsed != null && Number.isNaN(parsed)) return;
    onChange(parsed, lon);
  };

  const handleManualLon = (v: string) => {
    const parsed = v === '' ? null : parseFloat(v);
    if (parsed != null && Number.isNaN(parsed)) return;
    onChange(lat, parsed);
  };

  const hasCoord = lat != null && lon != null;

  return (
    <div className="flex flex-col gap-2">
      {!manualMode ? (
        <>
          <div className="relative">
            <input
              type="text"
              value={address}
              onChange={(e) => handleAddressChange(e.target.value)}
              placeholder="예: 서울 마포구 양화로 100"
              className="w-full h-10 pl-9 pr-3 rounded-lg text-xs bg-card border border-border text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/15 focus:outline-none transition-colors"
            />
            <MapPin
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            {searching && (
              <Loader2
                size={14}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-primary animate-spin"
              />
            )}
            {!searching && hasCoord && (
              <Check size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-success" />
            )}
          </div>
          {hasCoord && resolvedAddress && (
            <p className="text-[10px] text-muted-foreground tabular-nums">
              {resolvedAddress} ({lat?.toFixed(5)}, {lon?.toFixed(5)})
            </p>
          )}
          {(searchError || sdkError) && (
            <p className="text-[10px] text-danger flex items-center gap-1">
              <AlertCircle size={11} />
              {searchError || sdkError?.message}
            </p>
          )}
        </>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <input
            type="number"
            step="0.000001"
            value={lat ?? ''}
            onChange={(e) => handleManualLat(e.target.value)}
            placeholder="위도 (예: 37.5547)"
            className="w-full h-10 px-3 rounded-lg text-xs font-mono bg-card border border-border text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/15 focus:outline-none transition-colors"
          />
          <input
            type="number"
            step="0.000001"
            value={lon ?? ''}
            onChange={(e) => handleManualLon(e.target.value)}
            placeholder="경도 (예: 126.9135)"
            className="w-full h-10 px-3 rounded-lg text-xs font-mono bg-card border border-border text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/15 focus:outline-none transition-colors"
          />
        </div>
      )}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => {
            setManualMode((v) => !v);
            setSearchError(null);
          }}
          className="text-[10px] text-primary hover:underline"
        >
          {manualMode ? '주소 검색으로 전환' : '좌표 직접 입력'}
        </button>
        {hasCoord && (
          <button
            type="button"
            onClick={() => {
              onChange(null, null);
              setAddress('');
              setResolvedAddress(null);
            }}
            className="text-[10px] text-muted-foreground hover:text-danger"
          >
            지우기
          </button>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground/70 italic">
        * 미입력 시 학교환경위생정화구역 거리 룰이 보수적으로 평가됩니다 (주점만 영향).
      </p>
    </div>
  );
}
