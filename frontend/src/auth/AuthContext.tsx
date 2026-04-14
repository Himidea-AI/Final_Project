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
