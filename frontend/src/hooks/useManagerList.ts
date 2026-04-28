import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { createElement } from 'react';
import { useAuth } from '../auth/AuthContext';

/**
 * 매니저 타입 — HQCommandCenter와 일치 (중복 정의지만 순환 import 회피)
 */
export interface Manager {
  id: string;
  contact_name: string;
  position: string;
  email: string;
  phone: string;
  is_active: boolean;
  is_approved: boolean;
  created_at: string;
  assigned_gu: string | null;
  assigned_dongs: string[] | null;
}

/**
 * 상대 시간 표시 ("3분 전" / "2시간 전" / "어제" 등)
 */
export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '—';
  const diff = Date.now() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}일 전`;
  return date.toISOString().slice(0, 10);
}

/**
 * [v12.7 — DB 과부하 대응] 폴링 주기 5분으로 연장
 * - 이전: 30초. 여러 탭 × 여러 컴포넌트 × 여러 사용자 → RDS 커넥션 폭주
 * - 변경: 300초. 매니저 가입 이벤트는 하루 몇 건 수준이라 5분 주기도 충분
 */
const POLL_INTERVAL_MS = 300_000; // 5분

interface ManagerListState {
  managers: Manager[];
  pending: Manager[];
  active: Manager[];
  isLoading: boolean;
  refetch: () => Promise<void>;
}

const EMPTY_STATE: ManagerListState = {
  managers: [],
  pending: [],
  active: [],
  isLoading: false,
  refetch: async () => {},
};

const ManagerListContext = createContext<ManagerListState>(EMPTY_STATE);

/**
 * ManagerListProvider — 전역 단일 Polling 인스턴스
 *
 * 설계 목적:
 * - 여러 컴포넌트(GlobalLimelightNav, HQCommandCenter)가 useManagerList()를 호출해도
 *   실제 fetch + setInterval은 Provider 레벨에서 **1개만** 실행
 * - Page Visibility API로 탭 비활성 시 폴링 정지 → 브라우저 리소스 + RDS 부하 절감
 * - 매니저 role 이거나 비로그인 상태면 아예 fetch 안 함
 */
export function ManagerListProvider({ children }: { children: ReactNode }) {
  const { user, isLoggedIn } = useAuth();
  const [managers, setManagers] = useState<Manager[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // 최신 user.id를 closure 없이 안전하게 참조하기 위한 ref
  const userIdRef = useRef<string | null>(user?.id ?? null);
  useEffect(() => {
    userIdRef.current = user?.id ?? null;
  }, [user?.id]);

  const refetch = useCallback(async () => {
    const uid = userIdRef.current;
    if (!uid || !isLoggedIn || user?.role === 'manager') {
      setManagers([]);
      return;
    }
    setIsLoading(true);
    try {
      const res = await fetch(`/api/auth/managers?owner_id=${encodeURIComponent(uid)}`);
      const data = await res.json();
      if (data.status === 'success' && Array.isArray(data.managers)) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const normalized: Manager[] = data.managers.map((m: any) => {
          let dongs: string[] | null = null;
          const raw = m.assigned_dongs;
          if (Array.isArray(raw)) {
            dongs = raw.filter((d) => typeof d === 'string');
          } else if (typeof raw === 'string' && raw.trim().length > 0) {
            try {
              const parsed = JSON.parse(raw);
              if (Array.isArray(parsed)) {
                dongs = parsed.filter((d) => typeof d === 'string');
              }
            } catch {
              dongs = null;
            }
          }
          return { ...m, assigned_dongs: dongs } as Manager;
        });
        setManagers(normalized);
      }
    } catch {
      /* silent — 폴링 실패는 무시 */
    } finally {
      setIsLoading(false);
    }
  }, [isLoggedIn, user?.role]);

  useEffect(() => {
    // 비로그인/매니저면 폴링 전체 중지
    if (!isLoggedIn || user?.role === 'manager') {
      setManagers([]);
      return;
    }

    let timer: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      if (timer) return; // 중복 방지
      void refetch();
      timer = setInterval(() => {
        void refetch();
      }, POLL_INTERVAL_MS);
    };

    const stopPolling = () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };

    // Page Visibility: 탭 활성 시만 폴링
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        startPolling();
      }
    };

    // 초기: 현재 visibility 상태 따라 분기
    if (!document.hidden) {
      startPolling();
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isLoggedIn, user?.role, refetch]);

  const value = useMemo<ManagerListState>(() => {
    const pending = managers.filter((m) => m.is_active && !m.is_approved);
    const active = managers.filter((m) => m.is_active && m.is_approved);
    return { managers, pending, active, isLoading, refetch };
  }, [managers, isLoading, refetch]);

  return createElement(ManagerListContext.Provider, { value }, children);
}

/**
 * useManagerList — ManagerListProvider Context consumer.
 *
 * 사용처:
 * - HQCommandCenter: 사이드바 badge + TeamManagementView 상태 공유
 * - GlobalLimelightNav: Bell 아이콘 알림 점 + 드롭다운
 */
export function useManagerList() {
  return useContext(ManagerListContext);
}
