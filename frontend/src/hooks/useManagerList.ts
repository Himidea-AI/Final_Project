import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";

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
  if (isNaN(date.getTime())) return "—";
  const diff = Date.now() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "방금 전";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}일 전`;
  return date.toISOString().slice(0, 10);
}

const POLL_INTERVAL_MS = 30000; // 30s

/**
 * useManagerList — 현재 로그인한 마스터 소속 매니저 목록을 가져온다.
 *
 * - 매니저 로그인 상태(role === "manager")이거나 비로그인이면 빈 배열 반환
 * - 30초 polling + 수동 refetch 제공
 * - assigned_dongs 방어적 정규화 (백엔드가 JSON string으로 보낼 수도 있음)
 *
 * 사용처:
 * - HQCommandCenter: 사이드바 badge + TeamManagementView 상태 공유
 * - GlobalLimelightNav: Bell 아이콘 알림 점 + 드롭다운
 */
export function useManagerList() {
  const { user, isLoggedIn } = useAuth();
  const [managers, setManagers] = useState<Manager[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const refetch = useCallback(async () => {
    if (!isLoggedIn || user?.role === "manager" || !user?.id) {
      setManagers([]);
      return;
    }
    setIsLoading(true);
    try {
      const res = await fetch(
        `/api/auth/managers?owner_id=${encodeURIComponent(user.id)}`,
      );
      const data = await res.json();
      if (data.status === "success" && Array.isArray(data.managers)) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const normalized: Manager[] = data.managers.map((m: any) => {
          let dongs: string[] | null = null;
          const raw = m.assigned_dongs;
          if (Array.isArray(raw)) {
            dongs = raw.filter((d) => typeof d === "string");
          } else if (typeof raw === "string" && raw.trim().length > 0) {
            try {
              const parsed = JSON.parse(raw);
              if (Array.isArray(parsed)) {
                dongs = parsed.filter((d) => typeof d === "string");
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
  }, [isLoggedIn, user?.id, user?.role]);

  useEffect(() => {
    refetch();
    const timer = setInterval(refetch, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refetch]);

  const pending = managers.filter((m) => m.is_active && !m.is_approved);
  const active = managers.filter((m) => m.is_active && m.is_approved);

  return { managers, pending, active, isLoading, refetch };
}
