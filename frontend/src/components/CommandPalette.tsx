/**
 * CommandPalette — Cmd+K 전역 커맨드 팔레트
 * App.tsx Phase C Round 3 코드 스플릿으로 추출 — 기능 변경 없음.
 */
import {
  Search,
  LogOut,
  LayoutDashboard,
  Building2,
  FileText,
  Mail,
  ArrowRight,
  Settings,
} from 'lucide-react';
import { useToast } from './Toast';

function CommandPalette({
  isOpen,
  onClose,
  onNavigate,
}: {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (path: string) => void;
}) {
  const { showToast } = useToast();
  if (!isOpen) return null;

  const handleAction = (action: () => void) => {
    action();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[99999] flex items-start justify-center pt-[15vh] sm:pt-[20vh] px-4">
      <div className="absolute inset-0 bg-[#050505]/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl bg-[#1e1b18] border border-[#3a3633] rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.5)] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Search Input */}
        <div className="flex items-center px-4 border-b border-[#3a3633]">
          <Search className="w-5 h-5 text-[#818cf8]" />
          <input
            autoFocus
            type="text"
            placeholder="Type a command or search..."
            className="w-full bg-transparent border-none px-4 py-5 text-sm text-[#e2e8f0] placeholder-[#9ca3af] focus:outline-none"
          />
          <kbd className="px-2 py-1 bg-[#2c2825] border border-[#3a3633] rounded text-[10px] font-mono text-[#9ca3af]">
            ESC
          </kbd>
        </div>
        {/* Commands */}
        <div className="max-h-[60vh] overflow-y-auto p-2 custom-scrollbar">
          <div className="px-3 py-2 text-[10px] font-bold text-[#9ca3af] uppercase tracking-wider">
            Navigation
          </div>
          <button
            onClick={() => handleAction(() => onNavigate('accordion'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <LayoutDashboard className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                시뮬레이터 대시보드
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[#3a3633] group-hover:text-[#818cf8]" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('hq'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Building2 className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                HQ 커맨드 센터
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[#3a3633] group-hover:text-[#818cf8]" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('about'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <FileText className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                About SPOTTER
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[#3a3633] group-hover:text-[#818cf8]" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('contact'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Mail className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                Contact
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[#3a3633] group-hover:text-[#818cf8]" />
          </button>

          <div className="px-3 py-2 mt-2 text-[10px] font-bold text-[#9ca3af] uppercase tracking-wider">
            Quick Actions
          </div>
          <button
            onClick={() => handleAction(() => showToast('info', '테마 전환 기능은 준비 중입니다.'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-[#2c2825] group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Settings className="w-4 h-4 text-[#9ca3af] group-hover:text-[#818cf8]" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-white">
                다크/라이트 테마 전환
              </span>
            </div>
          </button>
          <button
            onClick={() =>
              handleAction(() => showToast('info', '로그아웃은 우측 상단 메뉴를 이용해주세요.'))
            }
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-rose-500/10 group transition-colors"
          >
            <div className="flex items-center gap-3">
              <LogOut className="w-4 h-4 text-[#9ca3af] group-hover:text-rose-500" />
              <span className="text-sm font-medium text-[#d1d5db] group-hover:text-rose-500">
                로그아웃
              </span>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
