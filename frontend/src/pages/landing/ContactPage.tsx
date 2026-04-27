/**
 * ContactPage — 벤토 박스 디지털 명함 (App.tsx에서 추출, Phase C Round 1).
 * Mega Typography + Bento Grid (Workspace 4링크, Team, Location, Direct Inquiry).
 */

import { ChevronRight, GitFork, ExternalLink, Mail, MapPin, Phone } from 'lucide-react';

/* ═══════════════════════════════════════════════════════
   Contact Page — 벤토 박스 디지털 명함
   ═══════════════════════════════════════════════════════
   - 좌측: Mega Typography (GET IN TOUCH.)
   - 우측: Bento Grid (Workspace 4링크, Team, Location, Direct Inquiry)
   - 100vh One-page Fit (스크롤 없음)
*/

export default function ContactPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col bg-[#1e1b18]/95 backdrop-blur-sm text-[#e2e8f0] pb-10">
      {/* Header */}
      <div className="fixed top-0 left-0 w-full h-24 border-b border-[#3a3633]/50 flex items-center px-8 md:px-16 bg-[#1e1b18]/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.svg" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-[#e2e8f0]">SPOTTER</span>
          </button>
          <span className="text-[#3a3633]">/</span>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-[#9ca3af] hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex flex-col justify-center pt-24 px-8 md:px-16 overflow-hidden">
        <div className="max-w-6xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left — Mega Typography */}
          <div
            className="lg:col-span-5 flex flex-col justify-center"
            style={{ animation: 'fadeSlideIn 1s ease-out' }}
          >
            <span className="font-mono text-indigo-400 tracking-widest mb-4 text-xs">
              PROJECT SPOTTER
            </span>
            <h1 className="text-5xl lg:text-7xl xl:text-8xl font-black uppercase leading-none mb-8">
              GET IN
              <br />
              <span className="text-[#818cf8]">TOUCH.</span>
            </h1>
            <p className="text-[#d1d5db] leading-relaxed text-sm max-w-sm">
              AI 기반 프랜차이즈 상권분석 시뮬레이터 프로젝트에 대한 상세한 코드와 기획 문서는 아래
              워크스페이스에서 확인하실 수 있습니다.
            </p>
          </div>

          {/* Right — Bento Box */}
          <div className="lg:col-span-7 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Card 1: Workspace — full width */}
            <div
              className="group/card md:col-span-2 relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: 'fadeSlideIn 1s ease-out 100ms both' }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-5 md:p-6 flex flex-col justify-center">
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-4 block">
                  Workspace
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                    <div
                      className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                      style={{
                        background:
                          'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                      }}
                    />
                    <a
                      href="https://github.com/Himidea-AI/Final_Project"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <GitFork
                          size={18}
                          className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors"
                        />
                        <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">
                          GitHub
                        </span>
                      </div>
                      <ExternalLink
                        size={14}
                        className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors"
                      />
                    </a>
                  </div>
                  <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                    <div
                      className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                      style={{
                        background:
                          'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                      }}
                    />
                    <a
                      href="https://www.notion.so/333ac2a0181b802b807cf7de2447b890"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <ExternalLink
                          size={18}
                          className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors"
                        />
                        <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">
                          Notion
                        </span>
                      </div>
                      <ExternalLink
                        size={14}
                        className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors"
                      />
                    </a>
                  </div>
                  <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                    <div
                      className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                      style={{
                        background:
                          'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                      }}
                    />
                    <a
                      href="https://www.figma.com/board/lkjvfmKP4FU5XWBAyWR52a/%EC%A0%9C%EB%AA%A9-%EC%97%86%EC%9D%8C?node-id=0-1&p=f&t=ZITF88ooGHZ2rrHV-0"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <ExternalLink
                          size={18}
                          className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors"
                        />
                        <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">
                          Figma
                        </span>
                      </div>
                      <ExternalLink
                        size={14}
                        className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors"
                      />
                    </a>
                  </div>
                  <div className="group/btn relative rounded-xl overflow-hidden p-[2px]">
                    <div
                      className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
                      style={{
                        background:
                          'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                      }}
                    />
                    <a
                      href="https://bat981120.atlassian.net/jira/software/projects/IM3/boards/2"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative z-10 bg-[#1e1b18] group-hover/btn:bg-[#818cf8] rounded-[10px] p-4 flex justify-between items-center transition-colors duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <ExternalLink
                          size={18}
                          className="text-[#9ca3af] group-hover/btn:text-[#1e1b18] transition-colors"
                        />
                        <span className="font-bold text-[#e2e8f0] group-hover/btn:text-[#1e1b18] text-sm transition-colors">
                          Jira
                        </span>
                      </div>
                      <ExternalLink
                        size={14}
                        className="text-[#3a3633] group-hover/btn:text-[#1e1b18] transition-colors"
                      />
                    </a>
                  </div>
                </div>
              </div>
            </div>

            {/* Card 2: Team Info */}
            <div
              className="group/card relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: 'fadeSlideIn 1s ease-out 200ms both' }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-5 md:p-6 flex flex-col justify-center">
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-2 block">
                  Team
                </span>
                <p className="text-lg font-bold text-white mb-4">
                  AI 심화과정 6인 팀 프로젝트 (3조)
                </p>
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-2 block">
                  Mentor
                </span>
                <p className="text-lg font-bold text-white">황태림</p>
              </div>
            </div>

            {/* Card 3: Location */}
            <div
              className="group/card relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: 'fadeSlideIn 1s ease-out 300ms both' }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-5 md:p-6 flex flex-col justify-center">
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-4 block">
                  Location
                </span>
                <div className="flex items-center gap-3">
                  <MapPin className="text-indigo-400 w-6 h-6 shrink-0" />
                  <span className="text-lg font-bold text-white leading-tight">
                    강남 하이미디어
                    <br />
                    아카데미
                  </span>
                </div>
              </div>
            </div>

            {/* Card 4: Direct Inquiry — full width */}
            <div
              className="group/card md:col-span-2 relative rounded-2xl overflow-hidden p-[2px]"
              style={{ animation: 'fadeSlideIn 1s ease-out 400ms both' }}
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-5 md:p-6 flex flex-col justify-center">
                <span className="font-mono text-xs text-[#9ca3af] uppercase tracking-widest mb-4 block">
                  Direct Inquiry
                </span>
                <div className="flex flex-wrap gap-8">
                  <a
                    href="mailto:bat981120@gmail.com"
                    className="text-xl md:text-2xl font-black hover:text-indigo-400 transition-colors flex items-center gap-3"
                  >
                    <Mail className="w-5 h-5 text-[#9ca3af] shrink-0" />
                    bat981120@gmail.com
                  </a>
                  <a
                    href="tel:01067790080"
                    className="text-xl md:text-2xl font-black hover:text-indigo-400 transition-colors flex items-center gap-3"
                  >
                    <Phone className="w-5 h-5 text-[#9ca3af] shrink-0" />
                    010.6779.0080
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
