/**
 * IntroScene — 메인 진입 화면 (`/`).
 * 전면 리디자인: 좌 로고 / 중앙 가로 메뉴(ABOUT·LOGIN·CONTACT) /
 * hero 큰 타이포(Don't Guess. Simulate.) + glass-btn(SIMULATOR).
 *
 * 환영 메시지·role 기반 이동 로직은 글로벌 헤더(GlobalNav)의 WelcomeWidget 으로 이전됨.
 * SIMULATOR glass-btn 인증 가드: 비로그인→/login, 로그인→/explore.
 */

import { useAuth } from '../../auth/AuthContext';
import WaveBackground from './WaveBackground';

interface IntroSceneProps {
  onAboutClick: () => void;
  onEngineClick: () => void;
  onLoginClick: () => void;
  onSimulatorClick: () => void;
  onContactClick: () => void;
}

export default function IntroScene({
  onAboutClick,
  onEngineClick,
  onLoginClick,
  onSimulatorClick,
  onContactClick,
}: IntroSceneProps) {
  const { isLoggedIn, logout } = useAuth();

  // SIMULATOR — 비로그인이면 /login, 로그인이면 onSimulatorClick (transitionTo('accordion') = /explore)
  const handleSimulatorClick = () => {
    if (!isLoggedIn) onLoginClick();
    else onSimulatorClick();
  };

  // LOGIN/LOGOUT 메뉴 — 로그인 상태 따라 라벨 + 동작 토글.
  // 로그아웃 시 main 페이지 그대로 유지 (redirect 안 함).
  const handleAuthMenuClick = () => {
    if (isLoggedIn) logout();
    else onLoginClick();
  };

  const menuCls =
    'text-xs font-semibold text-muted-foreground hover:text-primary tracking-widest transition-colors uppercase';

  return (
    <div className="relative z-10 h-full w-full overflow-hidden bg-white flex flex-col">
      {/* Background — Deep Blue 인터랙티브 웨이브 캔버스 (z-0) */}
      <WaveBackground />

      {/* Background — SVG 로고 워터마크 (z-0, wave 위에 살짝 얹힘) */}
      <div className="absolute inset-0 z-0 flex items-center justify-center pointer-events-none select-none">
        <img src="/logo.svg" alt="" className="w-[90vw] max-w-[1400px] h-auto opacity-[0.018]" />
      </div>

      {/* Header — 좌 로고 / 중앙 메뉴 (현대백화점-스타일) */}
      <header className="relative z-20 w-full px-6 md:px-12 py-8 flex items-center">
        {/* Left — Logo */}
        <div className="flex-1 flex items-center gap-3">
          <img src="/logo.svg" alt="SPOTTER" className="h-5 w-auto" />
          <span className="font-extrabold text-xl tracking-wide text-foreground">SPOTTER</span>
        </div>

        {/* Center — 4 메뉴 (ABOUT / ENGINE / LOGIN/LOGOUT / CONTACT) */}
        <nav className="hidden md:flex items-center gap-10">
          <button onClick={onAboutClick} className={menuCls}>
            ABOUT
          </button>
          <button onClick={onEngineClick} className={menuCls}>
            ENGINE
          </button>
          <button onClick={handleAuthMenuClick} className={menuCls}>
            {isLoggedIn ? 'LOGOUT' : 'LOGIN'}
          </button>
          <button onClick={onContactClick} className={menuCls}>
            CONTACT
          </button>
        </nav>

        {/* Right — Spacer (메뉴 정중앙 유지용) */}
        <div className="flex-1" />
      </header>

      {/* Hero — 중앙 큰 카피 + glass-btn */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 w-full text-center pb-32">
        <div className="mb-10" style={{ animation: 'fadeSlideIn 1s ease-out forwards' }}>
          <h1 className="text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter text-foreground mb-6 uppercase leading-[0.95]">
            Don&apos;t Guess.
            <br />
            <span className="text-primary">Simulate.</span>
          </h1>
          <p className="text-base md:text-xl font-medium text-muted-foreground max-w-2xl mx-auto break-keep leading-relaxed">
            당신의 비즈니스가 더 빛날 수 있도록,
            <br className="hidden sm:block" />
            데이터 기반 다중 에이전트 AI 시뮬레이터와 함께 미래를 예측하세요.
          </p>
        </div>

        {/* Glass Button — SIMULATOR (인증 가드 → /login or /explore) */}
        <div
          className="button-wrap mt-4"
          style={{ animation: 'fadeSlideIn 1.2s ease-out forwards' }}
        >
          <button onClick={handleSimulatorClick} className="glass-btn" aria-label="Start simulator">
            <span>SIMULATOR</span>
          </button>
          <div className="button-shadow" />
        </div>
      </main>

      {/* Bottom Marquee Strip — 그대로 유지 */}
      <div className="absolute bottom-0 left-0 w-full overflow-hidden border-t border-border/40 py-3 pointer-events-none z-20 bg-card/50 backdrop-blur-sm">
        <div className="flex animate-marquee whitespace-nowrap">
          {[...Array(2)].map((_, k) => (
            <div
              key={k}
              className="flex items-center gap-12 px-6 font-mono text-[0.625rem] uppercase tracking-[0.3em] shrink-0"
            >
              <span className="text-muted-foreground">AI Market Intelligence</span>
              <span className="text-border">●</span>
              <span className="text-primary">Mapo-Gu MVP</span>
              <span className="text-border">●</span>
              <span className="text-muted-foreground">Cannibalization Analysis</span>
              <span className="text-border">●</span>
              <span className="text-muted-foreground">12-Month Forecast</span>
              <span className="text-border">●</span>
              <span className="text-primary">Live Data · 19 Sources</span>
              <span className="text-border">●</span>
              <span className="text-muted-foreground">25 Districts</span>
              <span className="text-border">●</span>
              <span className="text-muted-foreground">LangGraph Multi-Agent</span>
              <span className="text-border">●</span>
              <span className="text-primary">Project SPOTTER v3.8</span>
              <span className="text-border">●</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
