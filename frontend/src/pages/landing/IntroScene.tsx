/**
 * IntroScene — 메인 진입 화면 (App.tsx에서 추출, Phase C Round 1).
 * 좌측: OHZI 스타일 타이포그래피 메뉴 / 우측: 로고 플로팅 + 앰버 글로우.
 */

import { useNavigate } from 'react-router-dom';
import { LogIn } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';

const MENU_ITEMS = ['ABOUT SPOTTER', 'SIMULATOR', 'CONTACT'];

interface IntroSceneProps {
  activeMenuIndex: number;
  setActiveMenuIndex: (i: number) => void;
  onAboutClick: () => void;
  onLoginClick: () => void;
  onSimulatorClick: () => void;
  onContactClick: () => void;
}

/* ═══════════════════════════════════════════════════════
   Scene 1: Intro — 메인 진입 화면
   ═══════════════════════════════════════════════════════
   - 좌측: OHZI 스타일 타이포그래피 메뉴 (4개: About, Join Us, Simulator, Contact)
   - 우측: 로고 플로팅 + 앰버 글로우
   - 메뉴 클릭 시 transitionTo()로 해당 씬 이동 (암전 트랜지션)
*/

export default function IntroScene({
  activeMenuIndex,
  setActiveMenuIndex,
  onAboutClick,
  onLoginClick,
  onSimulatorClick,
  onContactClick,
}: IntroSceneProps) {
  const { isLoggedIn, user, brand } = useAuth();
  const nav = useNavigate();
  // 환영 메시지: "(회사명) 담당자명 직급님 환영합니다"
  // 직급은 사용자 입력(position) 우선, 없으면 role 기반 기본값(master→팀장, manager→매니저)
  const brandName = brand?.brand_name || user?.company_name || '';
  const personName = user?.contact_name || '';
  const roleTitle = user?.position || (user?.role === 'master' ? '팀장' : '매니저');
  const showWelcome = isLoggedIn && (brandName || personName);
  const handleWelcomeClick = () => {
    nav(user?.role === 'master' ? '/hq' : '/simulator');
  };

  return (
    <div className="relative z-10 h-full w-full overflow-hidden">
      {/* 🔐 Top-right — 비로그인 시 Login 버튼, 로그인 시 환영 메시지 (클릭 시 역할별 홈) */}
      {showWelcome ? (
        <button
          onClick={handleWelcomeClick}
          className="absolute top-6 right-6 z-40 flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#1e1b18]/70 backdrop-blur-md border border-[#3a3633] hover:border-[#818cf8] hover:bg-[#1e1b18] hover:shadow-[0_0_15px_rgba(129,140,248,0.25)] transition-all duration-200 text-[#e2e8f0] hover:text-[#818cf8]"
          title={`${user?.role === 'master' ? 'HQ 지휘소' : '시뮬레이터'}로 이동`}
        >
          <span className="text-[0.6875rem] font-medium tracking-wide">
            {brandName && <span className="text-[#818cf8]">{brandName}</span>}
            {brandName && personName && <span className="text-[#9ca3af]"> · </span>}
            {personName && (
              <span>
                {personName} {roleTitle}
              </span>
            )}
            <span className="text-[#9ca3af]">님 환영합니다</span>
          </span>
        </button>
      ) : (
        <button
          onClick={onLoginClick}
          className="absolute top-6 right-6 z-40 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#1e1b18]/70 backdrop-blur-md border border-[#3a3633] hover:border-[#818cf8] hover:bg-[#1e1b18] hover:shadow-[0_0_15px_rgba(129,140,248,0.25)] transition-all duration-200 text-[#9ca3af] hover:text-[#818cf8]"
          title="Login"
        >
          <LogIn className="w-3 h-3" />
          <span className="text-[0.6875rem] font-bold tracking-wider uppercase">Login</span>
        </button>
      )}

      {/* Background Watermark Logo (idea 5) — 화면을 가로지르는 거대한 반투명 로고 */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
        <img src="/logo.svg" alt="" className="w-[90vw] max-w-[1400px] h-auto opacity-[0.018]" />
      </div>

      {/* Right section — Floating Logo with Glow (원래 위치 복원) */}
      <div className="absolute right-[10%] top-1/2 -translate-y-1/2 p-10 cursor-pointer group hidden md:flex flex-col items-center pointer-events-auto z-30">
        <div className="relative animate-float-logo">
          <div className="absolute inset-0 bg-[#818cf8] blur-[50px] opacity-0 group-hover:opacity-30 transition-all duration-700 ease-out scale-75 group-hover:scale-125" />
          <img
            src="/logo.svg"
            alt="SPOTTER"
            className="w-48 h-auto relative z-10 opacity-90 transition-all duration-500 group-hover:scale-105 group-hover:drop-shadow-[0_0_30px_rgba(99,102,241,0.6)]"
          />
        </div>
        <div className="mt-8 text-center transition-all duration-500 group-hover:scale-105">
          <h1 className="text-4xl md:text-5xl font-black tracking-[0.2em] text-[#e2e8f0]">
            SPOTTER
          </h1>
          <p className="text-[#818cf8] font-mono text-xs tracking-widest mt-3 uppercase opacity-60 transition-opacity duration-500 group-hover:opacity-100">
            AI Franchise Simulator
          </p>
        </div>
      </div>

      {/* Left section — Typography menu (uniform single column) */}
      <div className="relative z-20 h-full flex flex-col justify-center pl-12 md:pl-20 lg:pl-32 pt-[18vh] pb-20">
        {/* Sub-copy */}
        <div className="flex items-center gap-4 mb-10 text-xs tracking-[0.3em] text-gray-500 uppercase">
          <div className="w-px h-4 bg-gray-600" />
          <span>
            0{activeMenuIndex + 1} / 0{MENU_ITEMS.length} — GET TO KNOW
          </span>
        </div>

        {/* Menu — SIMULATOR가 핵심이라 1단계 더 큼, 나머지는 보조 사이즈 */}
        <nav className="flex flex-col gap-3">
          {MENU_ITEMS.map((item, i) => {
            const isActive = activeMenuIndex === i;
            const isSimulator = i === 1;
            const sizeClasses = isSimulator
              ? 'text-3xl sm:text-5xl md:text-6xl lg:text-7xl'
              : 'text-2xl sm:text-4xl md:text-5xl lg:text-6xl';
            return (
              <button
                key={item}
                className="relative text-left group self-start whitespace-nowrap"
                style={{ width: 'fit-content', maxWidth: 'fit-content' }}
                onMouseEnter={() => setActiveMenuIndex(i)}
                onClick={() => {
                  if (i === 0) onAboutClick();
                  if (i === 1) onSimulatorClick();
                  if (i === 2) onContactClick();
                }}
              >
                {/* Indicator bar */}
                <div
                  className={`absolute -left-10 top-1/2 -translate-y-1/2 w-1.5 h-[80%] bg-[#818cf8] rounded-full transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] origin-top ${
                    isActive ? 'scale-x-100' : 'scale-x-0'
                  }`}
                />
                <span
                  className={`inline-block ${sizeClasses} font-black uppercase tracking-tight leading-none whitespace-nowrap origin-left transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                    isActive
                      ? 'text-[#e2e8f0] translate-x-0'
                      : 'text-[#3a3633] -translate-x-2 group-hover:text-[#9ca3af]'
                  }`}
                >
                  {item}
                </span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Marquee Strip (idea 4) — 화면 하단 가로 스크롤 데이터 띠 */}
      <div className="absolute bottom-0 left-0 w-full overflow-hidden border-t border-[#3a3633]/40 py-3 pointer-events-none z-20 bg-[#1e1b18]/50 backdrop-blur-sm">
        <div className="flex animate-marquee whitespace-nowrap">
          {[...Array(2)].map((_, k) => (
            <div
              key={k}
              className="flex items-center gap-12 px-6 font-mono text-[0.625rem] uppercase tracking-[0.3em] shrink-0"
            >
              <span className="text-[#9ca3af]">AI Market Intelligence</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#818cf8]">Mapo-Gu MVP</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#9ca3af]">Cannibalization Analysis</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#9ca3af]">12-Month Forecast</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#818cf8]">Live Data · 19 Sources</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#9ca3af]">25 Districts</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#9ca3af]">LangGraph Multi-Agent</span>
              <span className="text-[#3a3633]">●</span>
              <span className="text-[#818cf8]">Project SPOTTER v3.8</span>
              <span className="text-[#3a3633]">●</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
