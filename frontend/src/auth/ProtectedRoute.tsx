/**
 * ProtectedRoute — 비로그인 시 /login으로 리다이렉트
 *
 * requireRole 을 지정하면 역할 기반 접근 제어까지 수행:
 *   - requireRole="master"  → 마스터만 접근 가능. 매니저는 /simulator 로 리다이렉트.
 *   - requireRole="manager" → 매니저만 접근 가능. 마스터는 /hq 로 리다이렉트.
 *   - requireRole 미지정    → 로그인만 확인 (기존 동작 유지).
 */

import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

type Role = "master" | "manager";

export default function ProtectedRoute({
  children,
  requireRole,
}: {
  children: React.ReactNode;
  requireRole?: Role;
}) {
  const { isLoggedIn, user } = useAuth();

  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }

  if (requireRole && user?.role && user.role !== requireRole) {
    // 역할 불일치 시 각자의 기본 착륙지로
    const fallback = user.role === "manager" ? "/simulator" : "/hq";
    return <Navigate to={fallback} replace />;
  }

  return <>{children}</>;
}
