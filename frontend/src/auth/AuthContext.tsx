/**
 * Auth Context — 로그인 상태 관리
 *
 * 저장 위치: localStorage 'spotter_auth' = { user, brand, token }.
 * token은 백엔드가 발급한 JWT (HS256). axios interceptor가 Bearer로 자동 주입.
 */

import { createContext, useContext, useState, useCallback } from 'react';

interface User {
  id: string;
  company_name: string;
  contact_name: string;
  email: string;
  phone: string;
  position: string;
  store_count: string;
  plan: string;
  role?: 'master' | 'manager';
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
  token: string | null;
  login: (user: User, brand: Brand | null, token?: string | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  isLoggedIn: false,
  user: null,
  brand: null,
  token: null,
  login: () => {},
  logout: () => {},
});

// localStorage에서 인증 상태를 동기적으로 읽음 (SSR safe).
// 첫 렌더부터 올바른 isLoggedIn 반영 → ProtectedRoute의 잘못된 /login 리다이렉트 방지.
function _readStoredAuth(): { user: User | null; brand: Brand | null; token: string | null } {
  if (typeof window === 'undefined') return { user: null, brand: null, token: null };
  try {
    const stored = window.localStorage.getItem('spotter_auth');
    if (!stored) return { user: null, brand: null, token: null };
    const parsed = JSON.parse(stored);
    return {
      user: parsed.user ?? null,
      brand: parsed.brand ?? null,
      token: typeof parsed.token === 'string' ? parsed.token : null,
    };
  } catch {
    try {
      window.localStorage.removeItem('spotter_auth');
    } catch {
      /* noop */
    }
    return { user: null, brand: null, token: null };
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // lazy initial state — 첫 렌더부터 localStorage 반영
  const [user, setUser] = useState<User | null>(() => _readStoredAuth().user);
  const [brand, setBrand] = useState<Brand | null>(() => _readStoredAuth().brand);
  const [token, setToken] = useState<string | null>(() => _readStoredAuth().token);

  const login = useCallback((u: User, b: Brand | null, t?: string | null) => {
    setUser(u);
    setBrand(b);
    setToken(t ?? null);
    localStorage.setItem('spotter_auth', JSON.stringify({ user: u, brand: b, token: t ?? null }));
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setBrand(null);
    setToken(null);
    localStorage.removeItem('spotter_auth');
  }, []);

  return (
    <AuthContext.Provider
      value={{
        isLoggedIn: !!user,
        user,
        brand,
        token,
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
  | { success: true; role: 'master'; user: User; brand: Brand | null; token: string | null }
  | { success: true; role: 'manager'; user: User; token: string | null }
  | {
      success: false;
      reason: 'pending_approval' | 'invalid_credentials' | 'network_error';
      message?: string;
    };

export async function loginWithFallback(email: string, password: string): Promise<LoginResult> {
  try {
    // 1차: 마스터(users 테이블)
    const masterRes = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const masterData = await masterRes.json();
    if (masterData?.status === 'success' && masterData.user) {
      return {
        success: true,
        role: 'master',
        user: { ...masterData.user, role: 'master' },
        brand: masterData.brand ?? null,
        token: typeof masterData.access_token === 'string' ? masterData.access_token : null,
      };
    }

    // 2차: 매니저(manager_users 테이블) fallback
    const managerRes = await fetch('/api/auth/manager/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const managerData = await managerRes.json();
    if (managerData?.status === 'success' && managerData.user) {
      return {
        success: true,
        role: 'manager',
        user: {
          ...managerData.user,
          role: 'manager',
          plan: managerData.user.plan ?? '',
        },
        token: typeof managerData.access_token === 'string' ? managerData.access_token : null,
      };
    }

    // 두 엔드포인트 모두 실패 — 메시지 기반 pending_approval 구분
    const errorMsg: string =
      managerData?.message || managerData?.detail || masterData?.message || '';
    if (errorMsg.includes('승인') || errorMsg.includes('비활성')) {
      return { success: false, reason: 'pending_approval', message: errorMsg };
    }
    return {
      success: false,
      reason: 'invalid_credentials',
      message: errorMsg,
    };
  } catch {
    return { success: false, reason: 'network_error' };
  }
}
