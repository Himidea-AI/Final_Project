import { useEffect, useState } from 'react';

declare global {
  interface Window {
    kakao: unknown;
  }
}

const KAKAO_SDK_URL = (apiKey: string) =>
  `//dapi.kakao.com/v2/maps/sdk.js?appkey=${apiKey}&libraries=services,clusterer&autoload=false`;

let loadPromise: Promise<void> | null = null;

function loadKakaoSdk(apiKey: string): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('SSR'));
  const w = window as unknown as { kakao?: { maps?: unknown } };
  if (w.kakao?.maps) return Promise.resolve();
  if (loadPromise) return loadPromise;

  loadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = KAKAO_SDK_URL(apiKey);
    script.async = true;
    script.onload = () => {
      (
        window as unknown as { kakao: { maps: { load: (cb: () => void) => void } } }
      ).kakao.maps.load(() => resolve());
    };
    script.onerror = () => reject(new Error('Kakao Maps SDK 로드 실패'));
    document.head.appendChild(script);
  });
  return loadPromise;
}

export function useKakaoMap() {
  const w =
    typeof window !== 'undefined'
      ? (window as unknown as { kakao?: { maps?: unknown } })
      : undefined;
  const [ready, setReady] = useState<boolean>(!!w?.kakao?.maps);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const apiKey = import.meta.env.VITE_KAKAO_MAP_API_KEY as string | undefined;
    if (!apiKey) {
      setError(new Error('VITE_KAKAO_MAP_API_KEY 미설정'));
      return;
    }
    loadKakaoSdk(apiKey)
      .then(() => setReady(true))
      .catch((e) => setError(e as Error));
  }, []);

  return {
    ready,
    error,
    kakao: ready ? (window as unknown as { kakao: unknown }).kakao : null,
  };
}
