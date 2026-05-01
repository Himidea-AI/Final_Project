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
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl bg-card border border-border rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.5)] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Search Input */}
        <div className="flex items-center px-4 border-b border-border">
          <Search className="w-5 h-5 text-primary" />
          <input
            autoFocus
            type="text"
            placeholder="Type a command or search..."
            className="w-full bg-transparent border-none px-4 py-5 text-sm text-foreground placeholder-muted-foreground focus:outline-none"
          />
          <kbd className="px-2 py-1 bg-card border border-border rounded text-[0.625rem] font-mono text-muted-foreground">
            ESC
          </kbd>
        </div>
        {/* Commands */}
        <div className="max-h-[60vh] overflow-y-auto p-2 custom-scrollbar">
          <div className="px-3 py-2 text-[0.625rem] font-bold text-muted-foreground uppercase tracking-wider">
            Navigation
          </div>
          <button
            onClick={() => handleAction(() => onNavigate('accordion'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-card group transition-colors"
          >
            <div className="flex items-center gap-3">
              <LayoutDashboard className="w-4 h-4 text-muted-foreground group-hover:text-primary" />
              <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground">
                시뮬레이터 대시보드
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-border group-hover:text-primary" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('hq'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-card group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Building2 className="w-4 h-4 text-muted-foreground group-hover:text-primary" />
              <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground">
                HQ 커맨드 센터
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-border group-hover:text-primary" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('about'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-card group transition-colors"
          >
            <div className="flex items-center gap-3">
              <FileText className="w-4 h-4 text-muted-foreground group-hover:text-primary" />
              <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground">
                About SPOTTER
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-border group-hover:text-primary" />
          </button>
          <button
            onClick={() => handleAction(() => onNavigate('contact'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-card group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Mail className="w-4 h-4 text-muted-foreground group-hover:text-primary" />
              <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground">
                Contact
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-border group-hover:text-primary" />
          </button>

          <div className="px-3 py-2 mt-2 text-[0.625rem] font-bold text-muted-foreground uppercase tracking-wider">
            Quick Actions
          </div>
          <button
            onClick={() => handleAction(() => showToast('info', '테마 전환 기능은 준비 중입니다.'))}
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-card group transition-colors"
          >
            <div className="flex items-center gap-3">
              <Settings className="w-4 h-4 text-muted-foreground group-hover:text-primary" />
              <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground">
                다크/라이트 테마 전환
              </span>
            </div>
          </button>
          <button
            onClick={() =>
              handleAction(() => showToast('info', '로그아웃은 우측 상단 메뉴를 이용해주세요.'))
            }
            className="w-full flex items-center justify-between px-3 py-3 rounded-xl hover:bg-danger/10 group transition-colors"
          >
            <div className="flex items-center gap-3">
              <LogOut className="w-4 h-4 text-muted-foreground group-hover:text-danger" />
              <span className="text-sm font-medium text-muted-foreground group-hover:text-danger">
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
