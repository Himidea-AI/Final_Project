/**
 * 공통 레이아웃 컴포넌트 — 좌측 사이드바 네비게이션 + 우측 메인 컨텐츠 영역
 *
 * 모든 페이지를 감싸는 레이아웃. 사이드바에 6개 페이지 링크를 표시하고,
 * 현재 활성 페이지를 하이라이트. children으로 전달된 페이지 컴포넌트를
 * 우측 메인 영역에 렌더링.
 *
 * navItems 배열을 수정하여 메뉴 항목 추가/변경 가능.
 */
import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

const navItems = [
  { path: "/", label: "조건 입력" },
  { path: "/map", label: "지도 보기" },
  { path: "/report", label: "상세 리포트" },
  { path: "/bep", label: "손익분기점" },
  { path: "/comparison", label: "동 비교" },
  { path: "/cannibalization", label: "카니발리제이션" },
];

interface LayoutProps {
  children: ReactNode;
}

function Layout({ children }: LayoutProps) {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 사이드바 */}
      <aside className="w-64 bg-white shadow-md">
        <div className="p-6">
          <h1 className="text-lg font-bold text-gray-800">
            마포구 상권분석
          </h1>
          <p className="text-sm text-gray-500 mt-1">프랜차이즈 시뮬레이터</p>
        </div>
        <nav className="mt-2">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`block px-6 py-3 text-sm transition-colors ${
                location.pathname === item.path
                  ? "bg-blue-50 text-blue-700 border-r-2 border-blue-700 font-medium"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 overflow-auto p-8">{children}</main>
    </div>
  );
}

export default Layout;
