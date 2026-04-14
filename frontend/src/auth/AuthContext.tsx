/**
 * Auth Context — 로그인 상태 관리
 *
 * 현재: localStorage 기반 (JWT 미구현)
 * TODO: 백엔드 JWT 발급 후 토큰 기반으로 교체
 */

import { createContext, useContext, useState, useEffect, useCallback } from "react";

interface User {
  id: string;
  company_name: string;
  contact_name: string;
  email: string;
  phone: string;
  position: string;
  store_count: string;
  plan: string;
  role?: "master" | "manager";
}

interface Brand {
  brand_name: string;
  franchise_count: number;
  avg_sales: number;
  mapo_store_count: number;
}

interface AuthState {
  isLoggedIn: boolean;
  user: User | null;
  brand: Brand | null;
  login: (user: User, brand: Brand | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  isLoggedIn: false,
  user: null,
  brand: null,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [brand, setBrand] = useState<Brand | null>(null);

  // 앱 시작 시 localStorage에서 복원
  useEffect(() => {
    try {
      const stored = localStorage.getItem("spotter_auth");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.user) setUser(parsed.user);
        if (parsed.brand) setBrand(parsed.brand);
      }
    } catch {
      localStorage.removeItem("spotter_auth");
    }
  }, []);

  const login = useCallback((u: User, b: Brand | null) => {
    setUser(u);
    setBrand(b);
    localStorage.setItem("spotter_auth", JSON.stringify({ user: u, brand: b }));
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setBrand(null);
    localStorage.removeItem("spotter_auth");
  }, []);

  return (
    <AuthContext.Provider
      value={{
        isLoggedIn: !!user,
        user,
        brand,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

/* ─────────────────────────────────────────────────────────
   loginWithFallback
   ─────────────────────────────────────────────────────────
   마스터(users) 로그인 시도 → 실패 시 매니저(manager_users)로 fallback.
   백엔드는 실패 시 HTTP 200 + {status:"error", message}를 반환하므로
   res.ok 가 아닌 body.status 로 분기한다.
*/

export type LoginResult =
  | { success: true; role: "master"; user: User; brand: Brand | null }
  | { success: true; role: "manager"; user: User }
  | {
      success: false;
      reason: "pending_approval" | "invalid_credentials" | "network_error";
      message?: string;
    };

export async function loginWithFallback(
  email: string,
  password: string
): Promise<LoginResult> {
  try {
    // 1차: 마스터(users 테이블)
    const masterRes = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const masterData = await masterRes.json();
    if (masterData?.status === "success" && masterData.user) {
      return {
        success: true,
        role: "master",
        user: { ...masterData.user, role: "master" },
        brand: masterData.brand ?? null,
      };
    }

    // 2차: 매니저(manager_users 테이블) fallback
    const managerRes = await fetch("/api/auth/manager/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const managerData = await managerRes.json();
    if (managerData?.status === "success" && managerData.user) {
      return {
        success: true,
        role: "manager",
        user: {
          ...managerData.user,
          role: "manager",
          plan: managerData.user.plan ?? "",
        },
      };
    }

    // 두 엔드포인트 모두 실패 — 메시지 기반 pending_approval 구분
    const errorMsg: string =
      managerData?.message ||
      managerData?.detail ||
      masterData?.message ||
      "";
    if (errorMsg.includes("승인") || errorMsg.includes("비활성")) {
      return { success: false, reason: "pending_approval", message: errorMsg };
    }
    return {
      success: false,
      reason: "invalid_credentials",
      message: errorMsg,
    };
  } catch {
    return { success: false, reason: "network_error" };
  }
}
