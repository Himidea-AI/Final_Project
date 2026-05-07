/**
 * HQ Command Center — 프랜차이즈 본사 관리 대시보드 (Phase 2)
 *
 * [Tier 1 MVP] 프론트엔드 mock only, 백엔드 미연동
 * - 팀 및 권역 관리 (승인 대기 + 활성 멤버)
 * - 출점 파이프라인 칸반 보드 (4단계)
 * - 브랜드 AI 튜닝 (AOV, 타겟층, 배달비중)
 * - 결제 및 API 토큰 (placeholder)
 *
 * TODO (Phase 2+): 실제 JWT 인증 + workspace API 연동
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useToast } from '../components/Toast';
import { useAuth } from '../auth/AuthContext';
import { useTransition } from '../contexts/TransitionContext';
import { BrandLogo } from '../components/BrandLogo';
import { SEOUL_REGIONS } from '../data/seoulRegions';
import {
  useManagerList,
  formatRelativeTime,
  type Manager as HookManager,
} from '../hooks/useManagerList';
import {
  Building2,
  Users,
  LayoutTemplate,
  SlidersHorizontal,
  CreditCard,
  Plus,
  MapPin,
  MoreVertical,
  CheckCircle2,
  XCircle,
  BarChart3,
  Zap,
  ChevronDown,
  ChevronRight,
  Trash2,
  Pencil,
  AlertTriangle,
  ShieldAlert,
  UserCog,
  Shield,
  Loader2,
  History,
  Receipt,
  Download,
  Key,
  Copy,
  Eye,
  EyeOff,
} from 'lucide-react';
import { HistoryList } from '../components/SimulationHistory/HistoryList';
import { TokenBurnrateSection } from '../components/TokenBurnrate/TokenBurnrateSection';
import { getOperatedIndustries } from '../api/client';

/* ═══════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════ */
type MenuId = 'team' | 'pipeline' | 'tuning' | 'history' | 'billing' | 'mypage';

/* ═══════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════ */
export default function HQCommandCenter() {
  const { user } = useAuth();

  // 매니저는 별도의 워크스페이스 (시뮬레이션 기록 + 의뢰 목록)
  if (user?.role === 'manager') {
    return <ManagerWorkspace />;
  }

  return <MasterCommandCenter />;
}

function MasterCommandCenter() {
  const [searchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab') as MenuId | null;
  const [activeMenu, setActiveMenu] = useState<MenuId>(tabFromUrl || 'team');
  const { showToast } = useToast();
  const { user } = useAuth();
  const [isIssuing, setIsIssuing] = useState(false);

  // 매니저 목록 공유 (사이드바 badge + TeamManagementView 동기화)
  const managerList = useManagerList();
  const pendingCount = managerList.pending.length;

  // URL ?tab= 파라미터 변경 시 탭 동기화
  useEffect(() => {
    if (
      tabFromUrl &&
      ['team', 'pipeline', 'tuning', 'history', 'billing', 'mypage'].includes(tabFromUrl)
    ) {
      setActiveMenu(tabFromUrl);
    }
  }, [tabFromUrl]);

  const handleIssueInviteCode = async () => {
    if (isIssuing) return;
    if (!user?.id) {
      showToast('error', '로그인 정보를 확인할 수 없습니다. 다시 로그인해주세요.');
      return;
    }
    setIsIssuing(true);
    try {
      const res = await fetch('/api/auth/invite-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ owner_id: user.id, max_uses: 10 }),
      });
      const data = await res.json();
      if (data.status === 'success' && data.invite_code) {
        await navigator.clipboard.writeText(data.invite_code);
        showToast(
          'success',
          `초대 코드가 복사되었습니다: ${data.invite_code} (최대 ${data.max_uses}회 사용)`,
        );
      } else {
        showToast('error', data.message || '초대 코드 발급에 실패했습니다.');
      }
    } catch {
      showToast('error', '서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsIssuing(false);
    }
  };

  return (
    <div className="absolute inset-0 z-20 flex bg-card text-foreground font-sans overflow-hidden select-none pt-20">
      {/* ==========================================
          좌측 사이드바 (LNB) — bg-muted (cream zone, 메인 bg-card 와 hue 분리).
          외곽 pt-20 으로 LNB가 App 헤더(80px) 아래에서 시작 → cream이 헤더 영역으로 안 새어남.
          ========================================== */}
      <div className="w-64 bg-muted border-r border-border flex flex-col z-20 shrink-0">
        {/* 워크스페이스 로고 영역 — auth.user 기반 동적. font-size text-lg.
            (mt-20 제거됨 — 외곽 pt-20 으로 통합) */}
        <div className="h-20 flex items-center px-6 border-b border-border gap-3 cursor-pointer group">
          <BrandLogo
            name={user?.company_name || 'SPOTTER'}
            isUser={false}
            className="w-9 h-9 text-sm rounded-lg shrink-0"
          />
          <div className="flex flex-col min-w-0">
            <span
              className="font-black text-lg text-foreground group-hover:text-primary transition-colors truncate leading-tight"
              title={user?.company_name || 'SPOTTER Workspace'}
            >
              {user?.company_name || 'SPOTTER Workspace'}
            </span>
            <span className="text-[0.5625rem] text-muted-foreground font-mono tracking-widest uppercase">
              SPOTTER-HQ
            </span>
          </div>
        </div>

        {/* 메뉴 리스트 */}
        <div className="flex-1 overflow-y-auto py-6 px-4 flex flex-col gap-2">
          <p className="px-2 text-[0.625rem] font-bold text-muted-foreground mb-2 tracking-widest">
            COMMAND CENTER
          </p>

          <MenuButton
            active={activeMenu === 'team'}
            onClick={() => setActiveMenu('team')}
            icon={<Users className="w-4 h-4" />}
            label="팀 및 권역 관리"
            badge={pendingCount > 0 ? String(pendingCount) : undefined}
          />
          <MenuButton
            active={activeMenu === 'pipeline'}
            onClick={() => setActiveMenu('pipeline')}
            icon={<LayoutTemplate className="w-4 h-4" />}
            label="출점 파이프라인"
          />
          <MenuButton
            active={activeMenu === 'tuning'}
            onClick={() => setActiveMenu('tuning')}
            icon={<SlidersHorizontal className="w-4 h-4" />}
            label="브랜드 설정"
          />
          <MenuButton
            active={activeMenu === 'history'}
            onClick={() => setActiveMenu('history')}
            icon={<History className="w-4 h-4" />}
            label="내 시뮬 이력"
          />

          <p className="px-2 text-[0.625rem] font-bold text-muted-foreground mt-6 mb-2 tracking-widest">
            SETTINGS
          </p>
          <MenuButton
            active={activeMenu === 'billing'}
            onClick={() => setActiveMenu('billing')}
            icon={<CreditCard className="w-4 h-4" />}
            label="결제 및 API 토큰"
          />
          <MenuButton
            active={activeMenu === 'mypage'}
            onClick={() => setActiveMenu('mypage')}
            icon={<UserCog className="w-4 h-4" />}
            label="내 정보 관리"
          />
        </div>

        {/* 하단 유저 프로필 — auth.user 기반 동적 (master / manager 분기).
            T2 white card on LNB cream zone + chevron affordance + 클릭 시 mypage 메뉴로. */}
        <div className="p-4">
          <button
            onClick={() => setActiveMenu('mypage')}
            className="w-full bg-card rounded-xl shadow-md hover:shadow-lg p-3 flex items-center gap-3 cursor-pointer transition-all duration-200 group text-left"
          >
            <BrandLogo
              name={user?.contact_name || '사용자'}
              isUser={true}
              tone="accent"
              className="w-9 h-9 text-sm rounded-full shrink-0"
            />
            <div className="flex flex-col min-w-0 flex-1 gap-0.5">
              <span className="text-sm font-bold text-foreground truncate">
                {user?.contact_name || '사용자'}
              </span>
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="text-[0.5625rem] font-bold text-primary uppercase tracking-wider shrink-0">
                  {user?.role === 'manager' ? 'Manager' : 'Master'}
                </span>
                <span className="text-[0.5625rem] text-muted-foreground shrink-0">·</span>
                <span className="text-[0.5625rem] text-muted-foreground truncate">
                  {user?.role === 'manager' ? 'Regional Access' : `${user?.plan || 'Pro'} Plan`}
                </span>
              </div>
            </div>
            <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/40 group-hover:text-primary transition-colors shrink-0" />
          </button>
        </div>
      </div>

      {/* ==========================================
          우측 메인 콘텐츠 영역
          ========================================== */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-card">
        {/* 상단 툴바 — 좌측 LNB 회사명과 같은 높이.
            (mt-20 제거됨 — 외곽 pt-20 으로 통합) */}
        <header className="h-20 border-b border-border flex items-center justify-between px-8 bg-card/80 backdrop-blur-md z-10 shrink-0">
          <h2 className="text-lg font-bold flex items-center gap-2">
            {activeMenu === 'team' && '팀 및 권역 관리'}
            {activeMenu === 'pipeline' && '출점 파이프라인 보드'}
            {activeMenu === 'tuning' && '브랜드 설정'}
            {activeMenu === 'history' && '내 시뮬 이력'}
            {activeMenu === 'billing' && '결제 및 API 토큰 관리'}
            {activeMenu === 'mypage' && '내 정보 관리'}
          </h2>

          <div className="flex items-center gap-4">
            {activeMenu !== 'mypage' && activeMenu !== 'history' && (
              <button
                onClick={() => {
                  if (activeMenu === 'team') {
                    void handleIssueInviteCode();
                  } else {
                    showToast('info', '해당 기능은 정식 서비스에서 제공됩니다.');
                  }
                }}
                disabled={activeMenu === 'team' && isIssuing}
                className="h-9 px-4 bg-primary hover:bg-primary text-primary-foreground text-xs font-bold rounded-full flex items-center gap-2 shadow-[0_0_15px_rgba(0,44,209,0.3)] hover:shadow-[0_0_20px_rgba(0,44,209,0.5)] transition-all duration-200 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {activeMenu === 'team' && isIssuing ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin" />
                    발급 중...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    {activeMenu === 'team'
                      ? '초대코드 발급'
                      : activeMenu === 'pipeline'
                        ? '새 시뮬레이션'
                        : '저장'}
                  </>
                )}
              </button>
            )}
          </div>
        </header>

        {/* 렌더링 영역 */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-8">
          <div className="max-w-[1920px] w-full mx-auto xl:px-10 2xl:px-16">
            {activeMenu === 'team' && (
              <TeamManagementView
                managers={managerList.managers}
                pending={managerList.pending}
                active={managerList.active}
                isLoading={managerList.isLoading}
                refetch={managerList.refetch}
              />
            )}
            {activeMenu === 'pipeline' && <PipelineKanbanView />}
            {activeMenu === 'tuning' && <BrandSettingsView />}
            {activeMenu === 'history' && <HistoryList />}
            {activeMenu === 'billing' && <BillingManagementView />}
            {activeMenu === 'mypage' && <MyPageView />}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Sidebar Menu Button
   ═══════════════════════════════════════════════════════ */
function MenuButton({
  active,
  icon,
  label,
  onClick,
  badge,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick?: () => void;
  badge?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl transition-all duration-200 group ${
        active
          ? 'bg-card text-primary font-bold shadow-sm'
          : 'text-muted-foreground hover:bg-card/70 hover:text-foreground'
      }`}
    >
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        {badge && (
          <span className="w-4 h-4 rounded-full bg-danger text-white text-[0.5625rem] font-black flex items-center justify-center animate-pulse">
            {badge}
          </span>
        )}
        {active && !badge && <div className="w-1.5 h-1.5 bg-primary rounded-full" />}
      </div>
    </button>
  );
}

/* ═══════════════════════════════════════════════════════
   View 1: Team Management (팀 및 권역 관리)
   ═══════════════════════════════════════════════════════ */
// 구 → 동 매핑은 src/data/seoulRegions.ts 에 분리 (서울 25개 구 전체)
const REGION_DATA = SEOUL_REGIONS;

function RegionSelect({
  value,
  onChange,
  options,
  placeholder = '선택...',
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`w-full flex items-center justify-between bg-card border rounded-lg px-3.5 py-2.5 text-xs transition-colors ${
          open
            ? 'border-primary text-foreground'
            : value
              ? 'border-border text-foreground hover:border-primary/50'
              : 'border-border text-muted-foreground hover:border-primary/50'
        }`}
      >
        <span className="font-medium">{value || placeholder}</span>
        <ChevronDown
          className={`w-3.5 h-3.5 transition-transform duration-200 ${
            open ? 'rotate-180 text-primary' : 'text-muted-foreground'
          }`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15, ease: [0.19, 1, 0.22, 1] }}
            className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 origin-top bg-card border border-border rounded-lg shadow-2xl overflow-hidden"
          >
            <ul className="max-h-60 overflow-y-auto custom-scrollbar py-1">
              {options.map((opt) => {
                const selected = opt === value;
                return (
                  <li key={opt}>
                    <button
                      type="button"
                      onClick={() => {
                        onChange(opt);
                        setOpen(false);
                      }}
                      className={`w-full text-left px-3.5 py-2 text-xs transition-colors flex items-center justify-between ${
                        selected
                          ? 'bg-primary/10 text-primary font-bold'
                          : 'text-foreground hover:bg-card'
                      }`}
                    >
                      <span>{opt}</span>
                      {selected && <CheckCircle2 className="w-3.5 h-3.5" />}
                    </button>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Manager 타입 + formatRelativeTime은 ../hooks/useManagerList 에서 import 사용.
// (중복 정의 제거, 순환 import 회피 위해 hook 측에 canonical 정의를 둠)
type Manager = HookManager;

/* ─────────── ManagerActionsMenu — 활성 매니저 더보기 드롭다운 ─────────── */
function ManagerActionsMenu({
  onReassign,
  onDelete,
}: {
  onReassign: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number }>({
    top: 0,
    left: 0,
  });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // 메뉴 폭 (w-48 = 12rem = 192px)
  const MENU_WIDTH = 192;

  // open 상태 변경 시 버튼 위치로 portal 좌표 계산
  useEffect(() => {
    if (!open || !buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    setPosition({
      top: rect.bottom + 4,
      // 버튼 오른쪽 끝에 맞춰 정렬, 화면 밖으로 나가지 않도록 clamp
      left: Math.max(8, rect.right - MENU_WIDTH),
    });
  }, [open]);

  // 클릭 아웃사이드 + ESC + 스크롤/리사이즈 시 자동 닫기
  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        menuRef.current &&
        !menuRef.current.contains(target) &&
        buttonRef.current &&
        !buttonRef.current.contains(target)
      ) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    const onScrollOrResize = () => setOpen(false);

    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onScrollOrResize, true);
      window.removeEventListener('resize', onScrollOrResize);
    };
  }, [open]);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-muted-foreground hover:text-primary transition-colors p-1 rounded hover:bg-card"
      >
        <MoreVertical className="w-5 h-5 ml-auto" />
      </button>

      {/* Portal — 테이블의 overflow-hidden을 회피하고 body에 직접 렌더 */}
      {createPortal(
        <AnimatePresence>
          {open && (
            <motion.div
              ref={menuRef}
              initial={{ opacity: 0, y: -4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={{ duration: 0.15, ease: [0.19, 1, 0.22, 1] }}
              style={{
                position: 'fixed',
                top: position.top,
                left: position.left,
                width: MENU_WIDTH,
              }}
              className="z-[1000] origin-top-right bg-card border border-border rounded-lg shadow-2xl overflow-hidden"
            >
              <ul className="py-1">
                <li>
                  <button
                    type="button"
                    onClick={() => {
                      onReassign();
                      setOpen(false);
                    }}
                    className="w-full text-left px-3.5 py-2 text-xs text-foreground hover:bg-card flex items-center gap-2.5 transition-colors"
                  >
                    <Pencil className="w-3.5 h-3.5 text-primary" />
                    담당 권역 변경
                  </button>
                </li>
                <li className="border-t border-border">
                  <button
                    type="button"
                    onClick={() => {
                      onDelete();
                      setOpen(false);
                    }}
                    className="w-full text-left px-3.5 py-2 text-xs text-danger hover:bg-danger/10 flex items-center gap-2.5 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    매니저 제거 (퇴사)
                  </button>
                </li>
              </ul>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </>
  );
}

/* ─────────── ReassignRegionModal — 담당 권역 변경 모달 ─────────── */
function ReassignRegionModal({
  manager,
  onClose,
  onSave,
  isBusy,
}: {
  manager: Manager | null;
  onClose: () => void;
  onSave: (id: string, gu: string | null, dongs: string[] | null) => void;
  isBusy: boolean;
}) {
  const [gu, setGu] = useState<string>('');
  const [dongs, setDongs] = useState<string[]>([]);

  // 모달이 새 매니저로 열릴 때마다 기존 권역 값으로 초기화
  useEffect(() => {
    if (manager) {
      setGu(manager.assigned_gu ?? '');
      setDongs(manager.assigned_dongs ?? []);
    } else {
      setGu('');
      setDongs([]);
    }
  }, [manager]);

  if (!manager) return null;

  const toggleDong = (dong: string) => {
    setDongs((prev) => (prev.includes(dong) ? prev.filter((d) => d !== dong) : [...prev, dong]));
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[200] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-md bg-card border border-border rounded-2xl shadow-2xl overflow-hidden"
        >
          <div className="px-6 py-5 border-b border-border">
            <h3 className="text-sm font-black text-foreground flex items-center gap-2">
              <Pencil className="w-4 h-4 text-primary" />
              담당 권역 변경
            </h3>
            <p className="text-[0.6875rem] text-muted-foreground mt-1">
              {manager.contact_name} 매니저의 담당 구/행정동을 변경합니다.
            </p>
          </div>

          <div className="p-6 space-y-4">
            <div>
              <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider font-bold block mb-2">
                담당 구
              </label>
              <RegionSelect
                value={gu}
                onChange={(v) => {
                  setGu(v);
                  setDongs([]);
                }}
                options={Object.keys(REGION_DATA)}
                placeholder="구 선택..."
              />
            </div>

            {gu && (
              <div>
                <p className="text-[0.625rem] text-muted-foreground mb-2">
                  {gu} 행정동 선택 (복수 가능)
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {REGION_DATA[gu]?.map((dong) => {
                    const selected = dongs.includes(dong);
                    return (
                      <button
                        key={dong}
                        type="button"
                        onClick={() => toggleDong(dong)}
                        className={`px-2.5 py-1 rounded-full text-[0.625rem] font-medium border transition-all ${
                          selected
                            ? 'bg-primary/15 border-primary text-primary'
                            : 'bg-transparent border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
                        }`}
                      >
                        {dong}
                      </button>
                    );
                  })}
                </div>
                {dongs.length > 0 && (
                  <p className="text-[0.625rem] text-primary mt-2 font-mono">
                    {dongs.length}개 동 선택됨
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="px-6 py-4 border-t border-border bg-card/50 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isBusy}
              className="px-4 py-2 text-xs font-bold text-muted-foreground hover:text-foreground transition-colors"
            >
              취소
            </button>
            <button
              type="button"
              onClick={() => onSave(manager.id, gu || null, dongs.length ? dongs : null)}
              disabled={isBusy}
              className="px-4 py-2 bg-primary hover:bg-primary text-primary-foreground text-xs font-bold rounded-lg shadow-[0_0_15px_rgba(0,44,209,0.3)] hover:shadow-[0_0_20px_rgba(0,44,209,0.5)] transition-all duration-200 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isBusy ? (
                <>
                  <div className="w-3 h-3 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin" />
                  저장 중...
                </>
              ) : (
                '변경 저장'
              )}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

/* ─────────── DeleteConfirmModal — 매니저 제거(퇴사) 확인 ─────────── */
function DeleteConfirmModal({
  manager,
  onClose,
  onConfirm,
  isBusy,
}: {
  manager: Manager | null;
  onClose: () => void;
  onConfirm: (id: string) => void;
  isBusy: boolean;
}) {
  if (!manager) return null;
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[200] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-sm bg-card border border-border rounded-2xl shadow-2xl overflow-hidden"
        >
          <div className="px-6 py-5 border-b border-border">
            <h3 className="text-sm font-black text-foreground flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-danger" />
              매니저 제거 (퇴사 처리)
            </h3>
          </div>

          <div className="p-6 space-y-3 text-sm">
            <p className="text-foreground">
              <span className="font-bold text-foreground">{manager.contact_name}</span>
              <span className="text-muted-foreground text-xs"> ({manager.email})</span>
              <br />
              매니저를 워크스페이스에서 제거하시겠습니까?
            </p>
            <div className="p-3 bg-danger/5 border border-danger/20 rounded-lg">
              <p className="text-[0.6875rem] text-danger leading-relaxed">
                해당 매니저는 즉시 비활성화되며 더 이상 로그인할 수 없습니다. 담당 권역 할당 정보는
                보존되지만 복구하려면 재승인이 필요합니다.
              </p>
            </div>
          </div>

          <div className="px-6 py-4 border-t border-border bg-card/50 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isBusy}
              className="px-4 py-2 text-xs font-bold text-muted-foreground hover:text-foreground transition-colors"
            >
              취소
            </button>
            <button
              type="button"
              onClick={() => onConfirm(manager.id)}
              disabled={isBusy}
              className="px-4 py-2 bg-danger hover:bg-danger/90 text-white text-xs font-bold rounded-lg shadow-[0_0_15px_rgba(244,63,94,0.3)] hover:shadow-[0_0_20px_rgba(244,63,94,0.5)] transition-all duration-200 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isBusy ? (
                <>
                  <div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  처리 중...
                </>
              ) : (
                <>
                  <Trash2 className="w-3.5 h-3.5" />
                  제거하기
                </>
              )}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function PendingManagerCard({
  manager,
  onApprove,
  onReject,
  isBusy,
}: {
  manager: Manager;
  onApprove: (id: string, gu?: string, dongs?: string[]) => void;
  onReject: (id: string) => void;
  isBusy: boolean;
}) {
  const [pendingGu, setPendingGu] = useState('');
  const [pendingDongs, setPendingDongs] = useState<string[]>([]);

  const toggleDong = (dong: string) => {
    setPendingDongs((prev) =>
      prev.includes(dong) ? prev.filter((d) => d !== dong) : [...prev, dong],
    );
  };

  return (
    <div className="bg-card rounded-xl p-5 shadow-md hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <BrandLogo
            name={manager.contact_name}
            isUser={true}
            tone="muted"
            className="w-12 h-12 text-lg rounded-full"
          />
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-base font-bold text-foreground">{manager.contact_name}</span>
              <span className="px-1.5 py-0.5 bg-danger/10 text-danger rounded text-[0.5625rem] font-bold uppercase tracking-wider border border-danger/20">
                Pending
              </span>
              {manager.position && (
                <span className="px-1.5 py-0.5 bg-muted text-muted-foreground rounded text-[0.5625rem] font-bold uppercase tracking-wider">
                  {manager.position}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="font-mono">{manager.email}</span>
              <span className="hidden sm:inline">·</span>
              <span className="hidden sm:inline">
                초대 코드 입력 완료 ({formatRelativeTime(manager.created_at)})
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() =>
              onApprove(
                manager.id,
                pendingGu || undefined,
                pendingDongs.length ? pendingDongs : undefined,
              )
            }
            disabled={isBusy}
            className="p-2 bg-success/10 text-success hover:bg-success hover:text-white rounded-lg transition-colors border border-success/20 disabled:opacity-50 disabled:cursor-wait"
            title="승인"
          >
            <CheckCircle2 className="w-5 h-5" />
          </button>
          <button
            onClick={() => onReject(manager.id)}
            disabled={isBusy}
            className="p-2 bg-danger/10 text-danger hover:bg-danger hover:text-white rounded-lg transition-colors border border-danger/20 disabled:opacity-50 disabled:cursor-wait"
            title="거절"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* 구 → 동 선택 */}
      <div className="bg-card border border-border rounded-lg p-4">
        <p className="text-[0.625rem] text-muted-foreground uppercase tracking-wider font-bold mb-3">
          담당 권역 할당
        </p>
        <div className="mb-3">
          <RegionSelect
            value={pendingGu}
            onChange={(v) => {
              setPendingGu(v);
              setPendingDongs([]);
            }}
            options={Object.keys(REGION_DATA)}
            placeholder="구 선택..."
          />
        </div>

        {pendingGu && (
          <div>
            <p className="text-[0.625rem] text-muted-foreground mb-2">
              {pendingGu} 행정동 선택 (복수 가능)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {REGION_DATA[pendingGu]?.map((dong) => {
                const selected = pendingDongs.includes(dong);
                return (
                  <button
                    key={dong}
                    onClick={() => toggleDong(dong)}
                    className={`px-2.5 py-1 rounded-full text-[0.625rem] font-medium border transition-all ${
                      selected
                        ? 'bg-primary/15 border-primary text-primary'
                        : 'bg-transparent border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
                    }`}
                  >
                    {dong}
                  </button>
                );
              })}
            </div>
            {pendingDongs.length > 0 && (
              <p className="text-[0.625rem] text-primary mt-2 font-mono">
                {pendingDongs.length}개 동 선택됨: {pendingDongs.join(', ')}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TeamManagementView({
  managers,
  pending,
  active,
  isLoading,
  refetch,
}: {
  managers: HookManager[];
  pending: HookManager[];
  active: HookManager[];
  isLoading: boolean;
  refetch: () => Promise<void>;
}) {
  const { showToast } = useToast();
  const { user } = useAuth();
  const [busyId, setBusyId] = useState<string | null>(null);
  // 활성 매니저 관리 모달 (reassign / delete)
  const [reassignTarget, setReassignTarget] = useState<HookManager | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<HookManager | null>(null);
  // 활성 멤버 정렬
  const [sortBy, setSortBy] = useState<string>('이름순 (가나다)');
  const sortedActive = useMemo(() => {
    const arr = [...active];
    if (sortBy === '이름순 (가나다)') {
      return arr.sort((a, b) => a.contact_name.localeCompare(b.contact_name, 'ko'));
    }
    if (sortBy === '담당 권역순') {
      return arr.sort((a, b) => {
        // 미배정은 끝으로 밀기 (한글 "ㅎ" 이후로 정렬)
        const guA = a.assigned_gu || '힣';
        const guB = b.assigned_gu || '힣';
        const byGu = guA.localeCompare(guB, 'ko');
        if (byGu !== 0) return byGu;
        return a.contact_name.localeCompare(b.contact_name, 'ko');
      });
    }
    if (sortBy === '최근 가입순') {
      return arr.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
    }
    return arr;
  }, [active, sortBy]);
  // managers 사용하지 않는 경고 방지 (hook에서 pending/active로 분리됨)
  void managers;

  const handleApprove = useCallback(
    async (managerId: string, gu?: string, dongs?: string[]) => {
      if (!user?.id || busyId) return;
      setBusyId(managerId);
      try {
        const res = await fetch(`/api/auth/manager/${managerId}/approve`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            owner_id: user.id,
            assigned_gu: gu || null,
            assigned_dongs: dongs?.length ? dongs : null,
          }),
        });
        const data = await res.json();
        if (data.status === 'success') {
          showToast('success', data.message || '매니저를 승인했습니다.');
          refetch();
        } else {
          showToast('error', data.message || '승인에 실패했습니다.');
        }
      } catch {
        showToast('error', '서버 연결에 실패했습니다.');
      } finally {
        setBusyId(null);
      }
    },
    [user?.id, busyId, showToast, refetch],
  );

  const handleReject = useCallback(
    async (managerId: string) => {
      if (!user?.id || busyId) return;
      setBusyId(managerId);
      try {
        const res = await fetch(`/api/auth/manager/${managerId}/reject`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ owner_id: user.id }),
        });
        const data = await res.json();
        if (data.status === 'success') {
          showToast('success', data.message || '매니저를 거절했습니다.');
          refetch();
        } else {
          showToast('error', data.message || '거절에 실패했습니다.');
        }
      } catch {
        showToast('error', '서버 연결에 실패했습니다.');
      } finally {
        setBusyId(null);
      }
    },
    [user?.id, busyId, showToast, refetch],
  );

  // 재할당(approve와 동일 엔드포인트, 이미 승인된 매니저도 UPDATE로 동작)
  const handleReassign = useCallback(
    async (managerId: string, gu: string | null, dongs: string[] | null) => {
      if (!user?.id || busyId) return;
      setBusyId(managerId);
      try {
        const res = await fetch(`/api/auth/manager/${managerId}/approve`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            owner_id: user.id,
            assigned_gu: gu,
            assigned_dongs: dongs && dongs.length ? dongs : null,
          }),
        });
        const data = await res.json();
        if (data.status === 'success') {
          showToast('success', '담당 권역이 업데이트되었습니다.');
          refetch();
          setReassignTarget(null);
        } else {
          showToast('error', data.message || '권역 변경에 실패했습니다.');
        }
      } catch {
        showToast('error', '서버 연결에 실패했습니다.');
      } finally {
        setBusyId(null);
      }
    },
    [user?.id, busyId, showToast, refetch],
  );

  // 퇴사 처리 — reject 엔드포인트 재사용 (is_active=false)
  const handleRemove = useCallback(
    async (managerId: string) => {
      await handleReject(managerId);
      setDeleteTarget(null);
    },
    [handleReject],
  );

  // pending, active는 props로 받음 (hook에서 이미 필터링됨)

  return (
    <div className="flex flex-col gap-8">
      {/* 1. 승인 대기 (Pending Approval) */}
      <section>
        <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              pending.length > 0 ? 'bg-danger animate-pulse' : 'bg-muted'
            }`}
          />
          승인 대기 중인 매니저 ({pending.length})
        </h3>

        {isLoading && managers.length === 0 ? (
          <div className="bg-card rounded-xl p-10 shadow-md flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-border border-t-primary rounded-full animate-spin" />
          </div>
        ) : pending.length === 0 ? (
          <div className="bg-card border border-dashed border-border rounded-xl p-8 flex flex-col items-center justify-center text-center">
            <div className="w-10 h-10 rounded-full bg-card flex items-center justify-center mb-3">
              <ShieldAlert className="w-5 h-5 text-muted-foreground" />
            </div>
            <p className="text-sm font-bold text-muted-foreground mb-1">
              대기 중인 요청이 없습니다.
            </p>
            <p className="text-xs text-muted-foreground">
              우측 상단의 <span className="text-primary font-bold">초대코드 발급</span> 버튼을 눌러
              팀원을 초대하세요.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {pending.map((m) => (
              <PendingManagerCard
                key={m.id}
                manager={m}
                onApprove={handleApprove}
                onReject={handleReject}
                isBusy={busyId === m.id}
              />
            ))}
          </div>
        )}
      </section>

      {/* 2. 활성 멤버 리스트 (Card List — v12.3 + 정렬 필터) */}
      <section>
        <div className="flex items-center justify-between mb-4 gap-3">
          <h3 className="text-sm font-bold text-foreground">
            활성 워크스페이스 멤버 ({active.length})
          </h3>
          {active.length > 1 && (
            <div className="w-48 shrink-0">
              <RegionSelect
                value={sortBy}
                onChange={setSortBy}
                options={['이름순 (가나다)', '담당 권역순', '최근 가입순']}
                placeholder="정렬..."
              />
            </div>
          )}
        </div>

        {active.length === 0 ? (
          <div className="bg-card border border-dashed border-border rounded-xl p-10 flex flex-col items-center justify-center text-center">
            <Users className="w-8 h-8 text-muted-foreground/60 mb-3" />
            <p className="text-sm font-bold text-muted-foreground mb-1">활성 멤버가 없습니다.</p>
            <p className="text-xs text-muted-foreground">
              위에서 승인 대기 중인 매니저를 승인하여 팀을 구성하세요.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {sortedActive.map((m) => {
              const hasDongs = m.assigned_dongs && m.assigned_dongs.length > 0;
              const dongSummary = hasDongs
                ? m.assigned_dongs!.length > 3
                  ? `${m.assigned_dongs!.slice(0, 2).join(', ')} 외 ${m.assigned_dongs!.length - 2}곳`
                  : m.assigned_dongs!.join(', ')
                : '동 미지정';
              return (
                <div
                  key={m.id}
                  className="bg-card rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between transition-all duration-300 group shadow-md hover:shadow-lg gap-4 md:gap-0"
                >
                  {/* Left: Avatar + Info */}
                  <div className="flex items-center gap-4">
                    <BrandLogo
                      name={m.contact_name}
                      isUser={true}
                      tone="accent"
                      className="w-12 h-12 text-lg rounded-full shrink-0"
                    />
                    <div className="flex flex-col gap-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-base font-bold text-foreground truncate">
                          {m.contact_name}
                        </span>
                        <span className="px-1.5 py-0.5 bg-muted text-muted-foreground rounded text-[0.5625rem] font-bold uppercase tracking-wider shrink-0">
                          {m.position || 'Regional Mgr'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-mono truncate">{m.email}</span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Region + Status + Actions */}
                  <div className="flex items-center justify-between md:justify-end gap-6 md:gap-8 ml-16 md:ml-0">
                    {/* Assigned Region */}
                    <div className="flex flex-col items-start md:items-end gap-1.5">
                      {m.assigned_gu ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary border border-primary/20 rounded-md text-[0.625rem] font-bold">
                          <MapPin className="w-3 h-3" />
                          {m.assigned_gu}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-muted/50 text-muted-foreground border border-border rounded-md text-[0.625rem] font-bold">
                          <MapPin className="w-3 h-3" /> 미배정
                        </span>
                      )}
                      <span className="text-[0.625rem] text-muted-foreground">{dongSummary}</span>
                    </div>

                    {/* Activity Status (고정 Active) */}
                    <div className="w-20 flex justify-end shrink-0">
                      <span className="flex items-center gap-1.5 text-xs text-success font-bold">
                        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                        Active
                      </span>
                    </div>

                    {/* Actions Menu (기존 컴포넌트 재사용) */}
                    <div className="shrink-0">
                      <ManagerActionsMenu
                        onReassign={() => setReassignTarget(m)}
                        onDelete={() => setDeleteTarget(m)}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 담당 권역 변경 모달 */}
      <ReassignRegionModal
        manager={reassignTarget}
        onClose={() => setReassignTarget(null)}
        onSave={handleReassign}
        isBusy={!!busyId}
      />

      {/* 매니저 제거(퇴사) 확인 모달 */}
      <DeleteConfirmModal
        manager={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleRemove}
        isBusy={!!busyId}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   View 2: Pipeline Kanban Board (출점 파이프라인)
   ═══════════════════════════════════════════════════════ */
/* ───── 출점 파이프라인 mock 데이터 (시연용) ─────
   실 backend stage 테이블 구축 시 자동 교체. card 구조: 동·업종·점수·매출·BEP·담당자·태그. */
type PipelineStageId = 'analysis' | 'review' | 'proposal' | 'confirmed';
interface PipelineCard {
  id: string;
  district: string;
  bizType: string;
  brand: string;
  score: number; // 0~100
  monthlyRevenue: number; // 원
  bepMonths: number;
  closureRisk: 'low' | 'medium' | 'high';
  manager: string;
  updatedAgo: string;
  comments: number;
  tags: ('priority' | 'fast-track' | 'needs-review' | 'opening-soon')[];
  openingDate?: string; // confirmed only
}

const PIPELINE_CARDS: Record<PipelineStageId, PipelineCard[]> = {
  analysis: [
    {
      id: 'p1',
      district: '합정동',
      bizType: '카페·음료',
      brand: '메가엠지씨커피',
      score: 87,
      monthlyRevenue: 18_200_000,
      bepMonths: 8,
      closureRisk: 'low',
      manager: '박지윤',
      updatedAgo: '2일 전',
      comments: 3,
      tags: ['fast-track'],
    },
    {
      id: 'p2',
      district: '서교동',
      bizType: '한식음식점',
      brand: '김밥천국',
      score: 72,
      monthlyRevenue: 14_500_000,
      bepMonths: 11,
      closureRisk: 'medium',
      manager: '최강민',
      updatedAgo: '5시간 전',
      comments: 1,
      tags: [],
    },
    {
      id: 'p3',
      district: '망원1동',
      bizType: '카페·음료',
      brand: '백다방',
      score: 68,
      monthlyRevenue: 12_800_000,
      bepMonths: 13,
      closureRisk: 'medium',
      manager: '이수진',
      updatedAgo: '1일 전',
      comments: 5,
      tags: ['needs-review'],
    },
    {
      id: 'p4',
      district: '연남동',
      bizType: '제과점',
      brand: '베어카페',
      score: 81,
      monthlyRevenue: 16_400_000,
      bepMonths: 9,
      closureRisk: 'low',
      manager: '박지윤',
      updatedAgo: '3시간 전',
      comments: 2,
      tags: [],
    },
  ],
  review: [
    {
      id: 'p5',
      district: '상암동',
      bizType: '카페·음료',
      brand: '메가엠지씨커피',
      score: 92,
      monthlyRevenue: 21_500_000,
      bepMonths: 6,
      closureRisk: 'low',
      manager: '최강민',
      updatedAgo: '6시간 전',
      comments: 8,
      tags: ['priority', 'fast-track'],
    },
    {
      id: 'p6',
      district: '공덕동',
      bizType: '카페·음료',
      brand: '저가커피',
      score: 84,
      monthlyRevenue: 17_900_000,
      bepMonths: 8,
      closureRisk: 'low',
      manager: '김서준',
      updatedAgo: '12시간 전',
      comments: 4,
      tags: [],
    },
    {
      id: 'p7',
      district: '성산1동',
      bizType: '한식음식점',
      brand: '한솥',
      score: 79,
      monthlyRevenue: 15_700_000,
      bepMonths: 10,
      closureRisk: 'medium',
      manager: '이수진',
      updatedAgo: '2일 전',
      comments: 2,
      tags: ['needs-review'],
    },
  ],
  proposal: [
    {
      id: 'p8',
      district: '도화동',
      bizType: '카페·음료',
      brand: '메가엠지씨커피',
      score: 89,
      monthlyRevenue: 19_300_000,
      bepMonths: 7,
      closureRisk: 'low',
      manager: '박지윤',
      updatedAgo: '4일 전',
      comments: 11,
      tags: ['priority'],
    },
    {
      id: 'p9',
      district: '신수동',
      bizType: '분식전문점',
      brand: '스쿨푸드',
      score: 76,
      monthlyRevenue: 13_900_000,
      bepMonths: 11,
      closureRisk: 'medium',
      manager: '최강민',
      updatedAgo: '1주 전',
      comments: 6,
      tags: [],
    },
  ],
  confirmed: [
    {
      id: 'p10',
      district: '서강동',
      bizType: '카페·음료',
      brand: '메가엠지씨커피',
      score: 91,
      monthlyRevenue: 20_100_000,
      bepMonths: 7,
      closureRisk: 'low',
      manager: '박지윤',
      updatedAgo: '2주 전',
      comments: 14,
      tags: ['opening-soon'],
      openingDate: '2026-09-01',
    },
    {
      id: 'p11',
      district: '합정역 1번출구',
      bizType: '카페·음료',
      brand: '메가엠지씨커피',
      score: 95,
      monthlyRevenue: 23_400_000,
      bepMonths: 5,
      closureRisk: 'low',
      manager: '최강민',
      updatedAgo: '3주 전',
      comments: 22,
      tags: ['opening-soon'],
      openingDate: '2026-07-01',
    },
  ],
};

const TAG_LABELS: Record<
  NonNullable<PipelineCard['tags'][number]>,
  { label: string; cls: string }
> = {
  priority: {
    label: 'PRIORITY',
    cls: 'border-danger/40 bg-danger/10 text-danger',
  },
  'fast-track': {
    label: 'FAST TRACK',
    cls: 'border-primary/40 bg-primary/10 text-primary',
  },
  'needs-review': {
    label: 'NEEDS REVIEW',
    cls: 'border-warning/40 bg-warning/10 text-warning',
  },
  'opening-soon': {
    label: 'OPENING SOON',
    cls: 'border-success/40 bg-success/10 text-success',
  },
};

const RISK_LABELS: Record<PipelineCard['closureRisk'], { label: string; cls: string }> = {
  low: { label: '낮음', cls: 'text-success' },
  medium: { label: '중간', cls: 'text-warning' },
  high: { label: '높음', cls: 'text-danger' },
};

function formatRevenue(v: number): string {
  if (v >= 100_000_000) return `${(v / 100_000_000).toFixed(1)}억`;
  if (v >= 10_000) return `${Math.round(v / 10_000).toLocaleString('ko-KR')}만`;
  return `${v.toLocaleString('ko-KR')}원`;
}

function PipelineCardItem({ card, onAction }: { card: PipelineCard; onAction: () => void }) {
  const scoreColor =
    card.score >= 85
      ? 'text-success'
      : card.score >= 70
        ? 'text-primary'
        : card.score >= 60
          ? 'text-warning'
          : 'text-danger';
  const scoreBarColor =
    card.score >= 85
      ? 'bg-success'
      : card.score >= 70
        ? 'bg-primary'
        : card.score >= 60
          ? 'bg-warning'
          : 'bg-danger';
  const risk = RISK_LABELS[card.closureRisk];
  return (
    <button
      type="button"
      onClick={onAction}
      className="w-full rounded-xl border border-border bg-card p-4 text-left transition-all hover:border-primary/40 hover:shadow-md cursor-grab active:cursor-grabbing"
    >
      {/* Tags */}
      {card.tags.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {card.tags.map((t) => (
            <span
              key={t}
              className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[0.5625rem] font-black uppercase tracking-wider ${TAG_LABELS[t].cls}`}
            >
              {TAG_LABELS[t].label}
            </span>
          ))}
        </div>
      )}

      {/* Header — 동·업종 */}
      <div className="mb-1 flex items-baseline gap-2">
        <span className="text-base font-black text-foreground tracking-tight">{card.district}</span>
        <span className="text-[0.6875rem] text-muted-foreground">{card.bizType}</span>
      </div>
      <div className="mb-3 text-[0.6875rem] font-bold text-muted-foreground">{card.brand}</div>

      {/* Score */}
      <div className="mb-3 flex items-baseline justify-between">
        <span className={`text-2xl font-black tabular-nums ${scoreColor}`}>
          {card.score}
          <span className="text-xs font-normal text-muted-foreground"> /100</span>
        </span>
        <span className="text-[0.625rem] font-bold uppercase tracking-widest text-muted-foreground">
          종합 점수
        </span>
      </div>
      <div className="mb-3 h-1 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full ${scoreBarColor}`}
          style={{ width: `${card.score}%` }}
        />
      </div>

      {/* 재무 지표 */}
      <dl className="mb-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-[0.5625rem] font-black uppercase tracking-widest text-muted-foreground">
            월매출
          </dt>
          <dd className="text-sm font-black tabular-nums text-foreground">
            ₩{formatRevenue(card.monthlyRevenue)}
          </dd>
        </div>
        <div>
          <dt className="text-[0.5625rem] font-black uppercase tracking-widest text-muted-foreground">
            BEP
          </dt>
          <dd className="text-sm font-black tabular-nums text-foreground">{card.bepMonths}개월</dd>
        </div>
      </dl>

      {/* Risk + Opening date */}
      <div className="mb-3 flex items-center justify-between border-t border-border/50 pt-2">
        <span className="text-[0.625rem] text-muted-foreground">
          폐업 위험 <span className={`font-bold ${risk.cls}`}>{risk.label}</span>
        </span>
        {card.openingDate && (
          <span className="text-[0.625rem] font-bold tabular-nums text-success">
            🎉 {card.openingDate}
          </span>
        )}
      </div>

      {/* Footer — 매니저 + 갱신 + 댓글 */}
      <div className="flex items-center justify-between text-[0.625rem] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-secondary text-[0.5rem] font-black text-foreground">
            {card.manager.charAt(0)}
          </span>
          {card.manager}
        </span>
        <span className="flex items-center gap-2">
          <span>🕐 {card.updatedAgo}</span>
          <span>💬 {card.comments}</span>
        </span>
      </div>
    </button>
  );
}

function PipelineKanbanView() {
  const { showToast } = useToast();
  const { brand, user } = useAuth();
  // 사용자 브랜드(또는 회사명) 로 모든 mock 카드 brand 통일 — 김밥천국/저가커피 같은
  // 무관한 외부 브랜드가 (주)앤하우스 등 본부 영업팀 워크스페이스에 노출되는 회귀 차단.
  const brandName = user?.company_name || brand?.brand_name || '본사';
  const cardsByStage = useMemo<Record<PipelineStageId, PipelineCard[]>>(
    () =>
      Object.fromEntries(
        (Object.keys(PIPELINE_CARDS) as PipelineStageId[]).map((stageId) => [
          stageId,
          PIPELINE_CARDS[stageId].map((c) => ({ ...c, brand: brandName })),
        ]),
      ) as Record<PipelineStageId, PipelineCard[]>,
    [brandName],
  );

  const stages: {
    id: PipelineStageId;
    title: string;
    titleColor: string;
    bgColor: string;
    description: string;
  }[] = [
    {
      id: 'analysis',
      title: '상권 분석 중',
      titleColor: 'text-muted-foreground',
      bgColor: 'border-t-border',
      description: '시뮬 진행 + 후보지 검토',
    },
    {
      id: 'review',
      title: '임원 보고 대기',
      titleColor: 'text-warning',
      bgColor: 'border-t-warning',
      description: '본부장 승인 대기',
    },
    {
      id: 'proposal',
      title: '가맹점주 제안',
      titleColor: 'text-primary',
      bgColor: 'border-t-primary',
      description: '계약 협의 진행',
    },
    {
      id: 'confirmed',
      title: '출점 확정',
      titleColor: 'text-success',
      bgColor: 'border-t-success',
      description: '오픈 일정 확정',
    },
  ];

  // 전체 합계 — 헤더 통계용
  const totalCount = stages.reduce((sum, s) => sum + cardsByStage[s.id].length, 0);
  const totalRevenue = stages.reduce(
    (sum, s) => sum + cardsByStage[s.id].reduce((a, c) => a + c.monthlyRevenue, 0),
    0,
  );
  const confirmedCount = cardsByStage.confirmed.length;

  return (
    <div className="flex h-full flex-col gap-4">
      {/* summary stats */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-end">
        <div className="flex items-center gap-4 text-xs">
          <div>
            <span className="text-muted-foreground">총 후보지</span>{' '}
            <span className="font-black tabular-nums text-foreground">{totalCount}곳</span>
          </div>
          <div className="h-3 w-px bg-border" />
          <div>
            <span className="text-muted-foreground">예상 월매출 합계</span>{' '}
            <span className="font-black tabular-nums text-primary">
              ₩{formatRevenue(totalRevenue)}
            </span>
          </div>
          <div className="h-3 w-px bg-border" />
          <div>
            <span className="text-muted-foreground">출점 확정</span>{' '}
            <span className="font-black tabular-nums text-success">{confirmedCount}곳</span>
          </div>
        </div>
      </div>

      {/* Kanban columns */}
      <div className="flex gap-4 overflow-x-auto pb-4">
        {stages.map((col) => {
          const cards = cardsByStage[col.id];
          return (
            <div
              key={col.id}
              className={`flex min-w-[280px] flex-1 flex-col overflow-hidden rounded-2xl border border-border border-t-4 bg-secondary/40 ${col.bgColor}`}
            >
              {/* Column header */}
              <div className="flex items-center justify-between border-b border-border/50 bg-card/60 p-4">
                <div>
                  <h4 className={`text-xs font-black uppercase tracking-wider ${col.titleColor}`}>
                    {col.title}
                  </h4>
                  <p className="mt-0.5 text-[0.625rem] text-muted-foreground">{col.description}</p>
                </div>
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-card text-[0.6875rem] font-black tabular-nums text-foreground border border-border">
                  {cards.length}
                </span>
              </div>

              {/* Cards */}
              <div className="flex flex-1 flex-col gap-3 p-3 min-h-[200px]">
                {cards.length > 0 ? (
                  cards.map((card) => (
                    <PipelineCardItem
                      key={card.id}
                      card={card}
                      onAction={() =>
                        showToast(
                          'info',
                          `${card.district} ${card.bizType} 카드 상세는 정식 오픈 후 지원됩니다.`,
                        )
                      }
                    />
                  ))
                ) : (
                  <div className="flex flex-1 items-center justify-center text-[0.625rem] uppercase tracking-widest text-muted-foreground">
                    대기 중
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => showToast('info', '후보지 추가는 정식 오픈 후 지원됩니다.')}
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-dashed border-border bg-card/40 px-3 py-3 text-[0.6875rem] font-bold text-muted-foreground transition-colors hover:border-primary/40 hover:bg-card hover:text-foreground"
                >
                  <Plus className="h-3.5 w-3.5" />
                  후보지 추가
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   View 3: Brand Settings (브랜드 설정)
   상단 서브탭: 자사 브랜드 프로필 (작동) | AI 튜닝 (Phase 2, 로드맵)
   ═══════════════════════════════════════════════════════ */
type BrandSettingsTab = 'profile' | 'tuning';

function BrandSettingsView() {
  const [tab, setTab] = useState<BrandSettingsTab>('profile');

  return (
    <div className="max-w-4xl mx-auto w-full flex flex-col gap-6">
      <div className="flex items-center gap-1 p-1 bg-card border border-border rounded-xl self-start">
        <BrandSubTabButton
          active={tab === 'profile'}
          onClick={() => setTab('profile')}
          label="자사 브랜드 프로필"
        />
        <BrandSubTabButton
          active={tab === 'tuning'}
          onClick={() => setTab('tuning')}
          label="AI 튜닝"
          badge="Phase 2"
        />
      </div>

      {tab === 'profile' ? <BrandProfileView /> : <BrandTuningPhase2View />}
    </div>
  );
}

function BrandSubTabButton({
  active,
  onClick,
  label,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  badge?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 transition-colors ${
        active
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground'
      }`}
    >
      {label}
      {badge && (
        <span
          className={`text-[0.5625rem] font-mono px-1.5 py-0.5 rounded ${
            active ? 'bg-card/20 text-primary-foreground' : 'bg-primary/10 text-primary'
          }`}
        >
          {badge}
        </span>
      )}
    </button>
  );
}

/* ───── 자사 브랜드 프로필 (읽기 전용 + 간단 메모) ───── */
const BRAND_MEMO_KEY = 'spotter_brand_memo';

type CorpBrand = { name: string; industry: string; stores: number };

function BrandCarousel({
  brands,
  activeIdx,
  onChange,
}: {
  brands: CorpBrand[];
  activeIdx: number;
  onChange: (i: number) => void;
}) {
  const [dragX, setDragX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ startX: number; moved: boolean } | null>(null);
  const activeIdxRef = useRef(activeIdx);
  activeIdxRef.current = activeIdx;

  const onPointerDown = (e: React.PointerEvent) => {
    dragRef.current = { startX: e.clientX, moved: false };
    setDragX(0);
    setIsDragging(true);

    const onMove = (ev: PointerEvent) => {
      if (!dragRef.current) return;
      const delta = ev.clientX - dragRef.current.startX;
      if (Math.abs(delta) > 4) dragRef.current.moved = true;
      setDragX(delta);
    };
    const onUp = (ev: PointerEvent) => {
      if (!dragRef.current) return;
      const delta = ev.clientX - dragRef.current.startX;
      const wasMoved = dragRef.current.moved;
      dragRef.current = null;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      // 거리 기반 commit — 카드 spacing(170px) 의 절반 넘게 끌면 1칸 이동.
      // 오른쪽 드래그(delta>0) → idx 감소 (왼쪽 brand). 부호 반전.
      if (wasMoved) {
        const shift = -Math.round(delta / 170);
        if (shift !== 0) {
          const curIdx = activeIdxRef.current;
          const newIdx = Math.max(0, Math.min(brands.length - 1, curIdx + shift));
          if (newIdx !== curIdx) onChange(newIdx);
        }
      }
      setDragX(0);
      setIsDragging(false);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
  };

  return (
    <div
      className="relative h-[240px] w-full overflow-hidden select-none"
      style={{ cursor: isDragging ? 'grabbing' : 'grab', touchAction: 'pan-y' }}
      onPointerDown={onPointerDown}
    >
      {brands.map((b, i) => {
        const offset = i - activeIdx;
        const dragOffset = isDragging ? dragX / 200 : 0;
        const visualOffset = offset + dragOffset;
        const abs = Math.abs(visualOffset);
        if (abs > 3) return null;
        const scale = Math.max(0.55, 1 - abs * 0.18);
        const opacity = Math.max(0.18, 1 - abs * 0.32);
        const translateX = visualOffset * 170;
        const zIndex = 100 - Math.round(abs * 10);
        const isActive = Math.round(visualOffset) === 0;
        return (
          <motion.div
            key={`${b.name}-${i}`}
            onClick={() => {
              if (offset !== 0 && !isDragging) onChange(i);
            }}
            animate={{ x: translateX, scale, opacity }}
            transition={
              isDragging
                ? { duration: 0 }
                : { type: 'tween', duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }
            }
            className="absolute w-[240px] h-[180px] rounded-2xl border bg-card shadow-xl p-5 flex flex-col gap-2"
            style={{
              left: 'calc(50% - 120px)',
              top: 'calc(50% - 90px)',
              zIndex,
              cursor: isActive ? (isDragging ? 'grabbing' : 'grab') : 'pointer',
              borderColor: isActive ? 'var(--primary)' : 'var(--border)',
              boxShadow: isActive ? '0 12px 40px -12px rgba(0,0,0,0.4)' : undefined,
            }}
          >
            <div className="text-[0.625rem] font-mono uppercase tracking-widest text-muted-foreground">
              {b.industry}
            </div>
            <div className="text-xl font-black text-foreground line-clamp-2 leading-tight">
              {b.name}
            </div>
            <div className="mt-auto text-sm tabular-nums">
              <span className="text-muted-foreground">전국 가맹점 </span>
              <span className="font-bold text-primary">{b.stores.toLocaleString()}</span>
              <span className="text-muted-foreground">개</span>
            </div>
          </motion.div>
        );
      })}

      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5 pointer-events-none">
        {brands.map((_, i) => (
          <div
            key={i}
            className={`h-1.5 rounded-full transition-all ${i === activeIdx ? 'w-4 bg-primary' : 'w-1.5 bg-muted-foreground/30'}`}
          />
        ))}
      </div>
    </div>
  );
}

function BrandProfileView() {
  const { brand, user } = useAuth();
  const { showToast } = useToast();
  const [memo, setMemo] = useState<string>(() => {
    try {
      return window.localStorage.getItem(BRAND_MEMO_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [memoDirty, setMemoDirty] = useState(false);
  const [corpBrands, setCorpBrands] = useState<CorpBrand[]>([]);
  const [companyName, setCompanyName] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    let alive = true;
    getOperatedIndustries().then((res) => {
      if (!alive) return;
      const list = (res.brands ?? []).slice().sort((a, b) => b.stores - a.stores);
      setCorpBrands(list);
      setCompanyName(res.company_name ?? null);
      // auth.brand 와 매칭되는 idx 를 default active 로
      const matchIdx = list.findIndex((b) => b.name === brand?.brand_name);
      setActiveIdx(matchIdx >= 0 ? matchIdx : 0);
    });
    return () => {
      alive = false;
    };
  }, [brand?.brand_name]);

  const formatMoney = (v: number | null | undefined): string => {
    if (v == null) return '—';
    if (v >= 100_000_000) return `₩${(v / 100_000_000).toFixed(1)}억`;
    if (v >= 10_000) return `₩${Math.round(v / 10_000).toLocaleString()}만`;
    return `₩${v.toLocaleString()}`;
  };

  const activeBrand = corpBrands[activeIdx];
  const isAuthBrand = activeBrand?.name === brand?.brand_name;

  const fields: { label: string; value: string; hint?: string }[] = [
    { label: '브랜드명', value: activeBrand?.name ?? brand?.brand_name ?? '—' },
    { label: '업종', value: activeBrand?.industry ?? '—' },
    {
      label: '전체 가맹점 수',
      value: activeBrand
        ? `${activeBrand.stores.toLocaleString()}개`
        : brand?.franchise_count != null
          ? `${brand.franchise_count.toLocaleString()}개`
          : '—',
      hint: '본사 공시 기준',
    },
    {
      label: '평균 월매출',
      value: isAuthBrand ? formatMoney(brand?.avg_sales) : '—',
      hint: isAuthBrand ? '가맹점당 월 평균' : '대표 brand 만 집계',
    },
    {
      label: '마포구 내 매장',
      value: isAuthBrand
        ? brand?.mapo_store_count != null
          ? `${brand.mapo_store_count.toLocaleString()}개`
          : '—'
        : '—',
      hint: isAuthBrand ? '시뮬 지역 기준' : '대표 brand 만 집계',
    },
  ];

  const saveMemo = () => {
    try {
      window.localStorage.setItem(BRAND_MEMO_KEY, memo);
      setMemoDirty(false);
      showToast('success', '브랜드 메모가 저장되었습니다.');
    } catch {
      showToast('info', '메모 저장에 실패했습니다.');
    }
  };

  return (
    <div className="box-glass rounded-2xl p-6 relative overflow-hidden">
      <Building2 className="absolute -right-10 -top-10 w-48 h-48 text-primary opacity-5 pointer-events-none" />

      <div className="relative z-10">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-foreground flex items-center gap-2 mb-1">
              <Building2 className="w-5 h-5 text-primary" /> 자사 브랜드 프로필
            </h3>
            <p className="text-xs text-muted-foreground">
              로그인 시 회사 마스터 데이터에서 불러온 기본 정보입니다. 수정은 본사 담당자 승인이
              필요해요.
            </p>
          </div>
          {user?.role === 'master' && (
            <span className="text-[0.5625rem] font-mono text-primary bg-primary/10 border border-primary/30 px-2 py-1 rounded-md uppercase tracking-widest">
              Master
            </span>
          )}
        </div>

        {corpBrands.length > 0 && (
          <div className="mb-6">
            <div className="flex items-baseline justify-between mb-2 px-1">
              <span className="text-[0.625rem] font-bold text-muted-foreground uppercase tracking-widest">
                {companyName ?? '운영 brand'} · {corpBrands.length}개
              </span>
              <span className="text-[0.625rem] text-muted-foreground/60">
                좌우로 드래그 또는 클릭
              </span>
            </div>
            <BrandCarousel brands={corpBrands} activeIdx={activeIdx} onChange={setActiveIdx} />
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {fields.map((f) => (
            <div
              key={f.label}
              className="p-4 bg-card border border-border rounded-xl flex flex-col gap-1"
            >
              <span className="text-[0.625rem] font-bold text-muted-foreground uppercase tracking-widest">
                {f.label}
              </span>
              <span className="text-lg font-black text-foreground tabular-nums">{f.value}</span>
              {f.hint && <span className="text-[0.625rem] text-muted-foreground/60">{f.hint}</span>}
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-xs font-bold text-foreground flex items-center justify-between">
            <span>브랜드 메모</span>
            <span className="text-[0.625rem] font-normal text-muted-foreground/60">
              이 브라우저에만 저장 · 팀 공유 X
            </span>
          </label>
          <textarea
            value={memo}
            onChange={(e) => {
              setMemo(e.target.value);
              setMemoDirty(true);
            }}
            rows={4}
            placeholder="예: 2026 Q3 신규 상권 서교/합정 우선 검토. 배달 채널 비중 높은 입지 선호."
            className="w-full bg-card border border-border rounded-lg p-3 text-sm text-foreground placeholder-muted-foreground/60 focus:border-primary outline-none resize-none"
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={saveMemo}
              disabled={!memoDirty}
              className="px-4 py-2 bg-primary text-primary-foreground text-xs font-bold rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary"
            >
              메모 저장
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───── AI 튜닝 (Phase 2 로드맵 프리뷰) ───── */
function BrandTuningPhase2View() {
  return (
    <div className="box-glass rounded-2xl p-6 relative overflow-hidden">
      <Building2 className="absolute -right-10 -top-10 w-48 h-48 text-primary opacity-5 pointer-events-none" />

      <div className="relative z-10">
        <div className="flex items-start justify-between gap-4 mb-2">
          <h3 className="text-lg font-bold text-primary flex items-center gap-2">
            <Zap className="w-5 h-5" /> Brand AI Weights
          </h3>
          <span className="text-[0.625rem] font-mono text-warning bg-warning/10 border border-warning/30 px-2 py-1 rounded-md uppercase tracking-widest whitespace-nowrap">
            Phase 2 · 2026 Q3
          </span>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          우리 프랜차이즈의 특성을 입력하면 AI 예측 모델이 가중치로 반영해 맞춤형 매출/리스크를
          산출하는 기능입니다.
        </p>

        <div className="flex items-start gap-2 mb-8 p-3 bg-warning/10 border border-warning/30 rounded-xl">
          <AlertTriangle className="w-4 h-4 text-warning mt-0.5 shrink-0" />
          <p className="text-[0.6875rem] text-warning leading-relaxed">
            <strong>로드맵 프리뷰입니다.</strong> 현재 입력값은 AI 모델에 반영되지 않습니다. 2026 Q3
            백엔드 가중치 API 구축 완료 후 정식 활성화됩니다.
          </p>
        </div>

        <fieldset disabled className="grid grid-cols-1 md:grid-cols-2 gap-8 opacity-60">
          {/* 객단가 (AOV) */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-foreground">예상 평균 객단가 (AOV)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground font-bold">
                ₩
              </span>
              <input
                type="text"
                defaultValue="25,000"
                className="w-full bg-card border border-border rounded-lg pl-8 pr-4 py-2.5 text-sm font-mono text-foreground outline-none cursor-not-allowed"
              />
            </div>
            <p className="text-[0.625rem] text-muted-foreground">
              유동인구 소비력 스코어 계산에 가중치로 작용합니다.
            </p>
          </div>

          {/* 타겟 연령층 */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-foreground">
              핵심 타겟 고객층 (Primary Target)
            </label>
            <select className="w-full bg-card border border-border rounded-lg px-4 py-2.5 text-sm font-medium text-foreground outline-none appearance-none cursor-not-allowed">
              <option value="2030f">2030 여성 (트렌드/디저트)</option>
              <option value="2030m">2030 남성/여성 (가성비/식사)</option>
              <option value="3040">3040 직장인 (회식/저녁)</option>
              <option value="family">주거 배후세대 (가족/배달)</option>
            </select>
            <p className="text-[0.625rem] text-muted-foreground">
              선택한 타겟층의 해당 상권 거주/유동 비율을 우선 분석합니다.
            </p>
          </div>

          {/* 배달 vs 홀 비중 슬라이더 */}
          <div className="flex flex-col gap-4 md:col-span-2 mt-4 p-5 bg-card border border-border rounded-xl">
            <div className="flex justify-between items-center">
              <label className="text-xs font-bold text-foreground">매출 비중 (홀 vs 배달)</label>
              <span className="text-xs font-mono font-bold text-primary">홀 30% : 배달 70%</span>
            </div>

            <div className="relative w-full h-3 bg-muted rounded-full overflow-hidden flex cursor-not-allowed">
              <div className="h-full bg-muted" style={{ width: '30%' }} />
              <div className="h-full bg-primary" style={{ width: '70%' }} />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white rounded-full shadow-lg border-2 border-primary"
                style={{ left: 'calc(30% - 10px)' }}
              />
            </div>

            <div className="flex justify-between text-[0.625rem] font-bold text-muted-foreground">
              <span>Dine-in (입지/접근성 가중치 상승)</span>
              <span>Delivery (배후세대 가중치 상승)</span>
            </div>
          </div>
        </fieldset>

        <div className="mt-8 flex justify-end">
          <button
            type="button"
            disabled
            className="px-6 py-2.5 bg-primary/30 text-primary-foreground/60 text-sm font-bold rounded-lg cursor-not-allowed"
          >
            AI 모델 업데이트 적용 (Phase 2)
          </button>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   View 4: Billing & API Token Management (결제 및 토큰)
   ───────────────────────────────────────────────────────
   시연용 mock 데이터 — 실 결제/토큰 API 연동 시 교체 예정.
   "Demo" 배지로 명시. LangSmith 토큰 번레이트만 실데이터.
   ═══════════════════════════════════════════════════════ */
const MOCK_PLAN = {
  name: 'Growth',
  price: 149_000,
  currency: '₩',
  billingCycle: 'monthly',
  status: 'active' as const,
  nextBillingDate: '2026-06-15',
  paymentMethod: { brand: '신한카드', last4: '1234', expiry: '08/27' },
  members: { active: 3, total: 5 },
};

const MOCK_TOKENS = {
  used: 743,
  limit: 1000,
  resetDate: '2026-06-15',
  lastMonthUsed: 821,
  topConsumers: [
    { name: '박지윤', role: '점포개발 매니저', tokens: 158 },
    { name: '최강민', role: '본부장', tokens: 124 },
    { name: '김서준', role: '개발팀장', tokens: 98 },
  ],
};

const MOCK_INVOICES = [
  { id: 'INV-2026-0415', date: '2026-04-15', plan: 'Growth', amount: 149_000, status: 'paid' },
  { id: 'INV-2026-0315', date: '2026-03-15', plan: 'Growth', amount: 149_000, status: 'paid' },
  { id: 'INV-2026-0215', date: '2026-02-15', plan: 'Growth', amount: 149_000, status: 'paid' },
  { id: 'INV-2026-0115', date: '2026-01-15', plan: 'Starter', amount: 49_000, status: 'paid' },
];

const MOCK_API_KEYS = [
  {
    id: 'k_prod_2a9f',
    label: 'Production',
    key: 'sk_live_xR7m...3a9f',
    fullKey: 'sk_live_xR7mP9qV2tNb8wYj4kL5cZ8e3a9f',
    createdAt: '2026-04-10',
    lastUsed: '5분 전',
    scope: 'read+write',
  },
  {
    id: 'k_dev_8b2c',
    label: 'Development',
    key: 'sk_test_dQ4n...8b2c',
    fullKey: 'sk_test_dQ4nF1pH7sLm2vXk6jY9wU8b2c',
    createdAt: '2026-04-10',
    lastUsed: '1시간 전',
    scope: 'read+write',
  },
  {
    id: 'k_legacy_e1d',
    label: 'Legacy CI',
    key: 'sk_live_aB3c...e1d4',
    fullKey: 'sk_live_aB3cF8gH2jK9lM5nO7pQ1rSe1d4',
    createdAt: '2025-11-22',
    lastUsed: '12일 전',
    scope: 'read-only',
  },
];

function formatKrwShort(v: number): string {
  if (v >= 10_000) return `${Math.round(v / 1000) / 10}만원`;
  return `${v.toLocaleString('ko-KR')}원`;
}

function BillingManagementView() {
  const { showToast } = useToast();
  const [revealedKey, setRevealedKey] = useState<string | null>(null);

  const usagePct = Math.round((MOCK_TOKENS.used / MOCK_TOKENS.limit) * 100);
  const usageColor =
    usagePct >= 90 ? 'text-danger' : usagePct >= 70 ? 'text-warning' : 'text-success';
  const usageBarColor = usagePct >= 90 ? 'bg-danger' : usagePct >= 70 ? 'bg-warning' : 'bg-success';

  const handleCopyKey = (label: string) => {
    showToast('success', `${label} API Key 가 클립보드에 복사되었습니다.`);
  };

  return (
    <div className="flex flex-col gap-8 max-w-6xl">
      {/* 1. 현재 구독 & API 토큰 사용량 */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Current Plan */}
        <div className="rounded-2xl border border-border bg-card p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-primary" />
              <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground">
                Current Plan
              </h3>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success/10 px-2 py-0.5 text-[0.625rem] font-bold uppercase tracking-wider text-success">
              <span className="h-1.5 w-1.5 rounded-full bg-success" />
              Active
            </span>
          </div>
          <div className="mb-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-foreground tracking-tight">
              {MOCK_PLAN.name}
            </span>
            <span className="text-xs text-muted-foreground">/ month</span>
          </div>
          <div className="mb-5 text-sm font-bold tabular-nums text-foreground">
            {MOCK_PLAN.currency}
            {MOCK_PLAN.price.toLocaleString('ko-KR')}
          </div>
          <dl className="space-y-2 text-xs border-t border-border pt-4">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">다음 결제일</dt>
              <dd className="font-bold text-foreground tabular-nums">
                {MOCK_PLAN.nextBillingDate}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">결제 수단</dt>
              <dd className="font-bold text-foreground">
                {MOCK_PLAN.paymentMethod.brand} ****{MOCK_PLAN.paymentMethod.last4}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">활성 멤버</dt>
              <dd className="font-bold text-foreground tabular-nums">
                {MOCK_PLAN.members.active} / {MOCK_PLAN.members.total} 명
              </dd>
            </div>
          </dl>
          <button
            type="button"
            onClick={() => showToast('info', '결제 수단 변경은 정식 오픈 후 지원됩니다.')}
            className="mt-4 w-full rounded-lg border border-border bg-card py-2 text-xs font-bold text-foreground transition-colors hover:bg-secondary hover:border-primary/40"
          >
            결제 수단 관리
          </button>
        </div>

        {/* API Tokens Usage */}
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground">
                API Tokens Usage
              </h3>
            </div>
            <span className="text-[0.625rem] text-muted-foreground">
              초기화: {MOCK_TOKENS.resetDate}
            </span>
          </div>
          <div className="mb-3 flex items-baseline gap-2">
            <span className={`text-3xl font-black tabular-nums ${usageColor}`}>
              {MOCK_TOKENS.used.toLocaleString('ko-KR')}
            </span>
            <span className="text-sm text-muted-foreground tabular-nums">
              / {MOCK_TOKENS.limit.toLocaleString('ko-KR')} tokens
            </span>
            <span className={`ml-auto text-sm font-black tabular-nums ${usageColor}`}>
              {usagePct}%
            </span>
          </div>
          <div className="mb-5 h-2 overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full transition-all duration-500 ${usageBarColor}`}
              style={{ width: `${usagePct}%` }}
            />
          </div>
          <div className="mb-4 flex justify-between text-[0.6875rem] text-muted-foreground">
            <span>
              지난달 {MOCK_TOKENS.lastMonthUsed.toLocaleString('ko-KR')} 사용 →{' '}
              <span
                className={
                  MOCK_TOKENS.used < MOCK_TOKENS.lastMonthUsed ? 'text-success' : 'text-warning'
                }
              >
                {MOCK_TOKENS.used < MOCK_TOKENS.lastMonthUsed ? '↓' : '↑'}{' '}
                {Math.abs(MOCK_TOKENS.used - MOCK_TOKENS.lastMonthUsed)}
              </span>
            </span>
            <span>일 평균 약 26 tokens</span>
          </div>
          <div className="border-t border-border pt-4">
            <h4 className="mb-3 text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
              상위 사용자 (Top 3)
            </h4>
            <ul className="space-y-2">
              {MOCK_TOKENS.topConsumers.map((c, i) => (
                <li key={c.name} className="flex items-center gap-3">
                  <span className="text-[0.625rem] font-mono font-black text-muted-foreground tabular-nums w-4">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-bold text-foreground truncate">{c.name}</div>
                    <div className="text-[0.625rem] text-muted-foreground truncate">{c.role}</div>
                  </div>
                  <span className="text-xs font-black tabular-nums text-foreground shrink-0">
                    {c.tokens}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* 2. LangSmith 실데이터 — 유지 */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground">LLM 토큰 번레이트 (최근 30일)</h3>
          <span className="text-[0.625rem] text-muted-foreground">LangSmith 실데이터 기반</span>
        </div>
        <TokenBurnrateSection />
      </section>

      {/* 3. 결제 내역 (mock) */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <Receipt className="h-4 w-4 text-primary" />
            결제 내역
          </h3>
          <span className="text-[0.625rem] text-muted-foreground">최근 4건</span>
        </div>
        <div className="rounded-2xl border border-border bg-card overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-secondary border-b border-border">
              <tr className="text-left">
                <th className="px-4 py-3 font-bold text-muted-foreground uppercase tracking-widest text-[0.625rem]">
                  Invoice
                </th>
                <th className="px-4 py-3 font-bold text-muted-foreground uppercase tracking-widest text-[0.625rem]">
                  결제일
                </th>
                <th className="px-4 py-3 font-bold text-muted-foreground uppercase tracking-widest text-[0.625rem]">
                  Plan
                </th>
                <th className="px-4 py-3 text-right font-bold text-muted-foreground uppercase tracking-widest text-[0.625rem]">
                  금액
                </th>
                <th className="px-4 py-3 text-center font-bold text-muted-foreground uppercase tracking-widest text-[0.625rem]">
                  Status
                </th>
                <th className="px-4 py-3 text-right font-bold text-muted-foreground uppercase tracking-widest text-[0.625rem]">
                  영수증
                </th>
              </tr>
            </thead>
            <tbody>
              {MOCK_INVOICES.map((inv, i) => (
                <tr
                  key={inv.id}
                  className={`${i < MOCK_INVOICES.length - 1 ? 'border-b border-border' : ''} hover:bg-secondary/50`}
                >
                  <td className="px-4 py-3 font-mono text-[0.6875rem] text-foreground tabular-nums">
                    {inv.id}
                  </td>
                  <td className="px-4 py-3 text-foreground tabular-nums">{inv.date}</td>
                  <td className="px-4 py-3 font-bold text-foreground">{inv.plan}</td>
                  <td className="px-4 py-3 text-right font-bold tabular-nums text-foreground">
                    {formatKrwShort(inv.amount)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success/10 px-2 py-0.5 text-[0.625rem] font-bold uppercase tracking-wider text-success">
                      paid
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        showToast('info', '영수증 다운로드는 정식 오픈 후 지원됩니다.')
                      }
                      className="inline-flex items-center gap-1 text-[0.6875rem] font-bold text-primary hover:text-primary/80"
                    >
                      <Download className="h-3 w-3" />
                      다운로드
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 4. API Key 관리 (mock) */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <Key className="h-4 w-4 text-primary" />
            API Key 관리
          </h3>
          <button
            type="button"
            onClick={() => showToast('info', 'API Key 발급은 정식 오픈 후 지원됩니다.')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-primary bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Plus className="h-3.5 w-3.5" />새 API Key 발급
          </button>
        </div>
        <div className="space-y-3">
          {MOCK_API_KEYS.map((k) => {
            const isRevealed = revealedKey === k.id;
            return (
              <div
                key={k.id}
                className="rounded-2xl border border-border bg-card p-4 flex items-center gap-4"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-secondary border border-border">
                  <Key className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-bold text-foreground">{k.label}</span>
                    <span className="rounded border border-border bg-secondary px-1.5 py-0.5 text-[0.5625rem] font-mono uppercase tracking-wider text-muted-foreground">
                      {k.scope}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mb-1">
                    <code className="font-mono text-[0.6875rem] text-foreground bg-secondary px-2 py-0.5 rounded">
                      {isRevealed ? k.fullKey : k.key}
                    </code>
                    <button
                      type="button"
                      onClick={() => setRevealedKey(isRevealed ? null : k.id)}
                      aria-label={isRevealed ? 'Key 가리기' : 'Key 보기'}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {isRevealed ? (
                        <EyeOff className="h-3.5 w-3.5" />
                      ) : (
                        <Eye className="h-3.5 w-3.5" />
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCopyKey(k.label)}
                      aria-label="Key 복사"
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="text-[0.625rem] text-muted-foreground">
                    생성: {k.createdAt} · 최근 사용: {k.lastUsed}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => showToast('info', 'API Key 폐기는 정식 오픈 후 지원됩니다.')}
                  className="shrink-0 rounded-lg border border-danger/30 bg-card px-3 py-1.5 text-[0.6875rem] font-bold text-danger transition-colors hover:bg-danger/10"
                >
                  폐기
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* 5. Plan Upgrade (Pricing Cards) — 현재 플랜 = Growth, 표시 강조 */}
      <section className="mt-4">
        <h3 className="text-sm font-bold text-foreground mb-4">플랜 변경</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              id: 'Starter',
              price: '₩49,000',
              tokens: '100 Tokens/mo',
              target: '소규모 점포개발팀',
            },
            {
              id: 'Growth',
              price: '₩149,000',
              tokens: '1,000 Tokens/mo',
              target: '중견 프랜차이즈 본사',
              isPopular: true,
            },
            {
              id: 'Enterprise',
              price: 'Custom',
              tokens: 'Unlimited Tokens',
              target: '대형 프랜차이즈 및 컨설팅사',
            },
          ].map((plan) => {
            const isCurrent = plan.id === MOCK_PLAN.name;
            return (
              <div
                key={plan.id}
                className={`group relative w-full rounded-2xl overflow-hidden p-[2px] transition-transform duration-500 ease-out hover:-translate-y-2 ${
                  isCurrent ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : ''
                }`}
              >
                <div
                  className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                  style={{
                    background:
                      'conic-gradient(from 0deg, transparent 0%, transparent 40%, var(--primary) 50%, var(--primary) 60%, transparent 100%)',
                  }}
                />
                <div className="relative z-10 h-full w-full bg-card rounded-[14px] flex flex-col p-6 transition-colors duration-500 border border-border group-hover:border-transparent">
                  {isCurrent ? (
                    <div className="absolute top-4 right-4 inline-flex items-center justify-center h-5 px-2.5 bg-primary rounded-full">
                      <span className="text-[0.5625rem] font-bold text-primary-foreground tracking-wider leading-none">
                        CURRENT PLAN
                      </span>
                    </div>
                  ) : plan.isPopular ? (
                    <div className="absolute top-4 right-4 inline-flex items-center justify-center h-5 px-2.5 bg-muted border border-primary/30 rounded-full">
                      <span className="text-[0.5625rem] font-bold text-primary tracking-wider leading-none">
                        MOST POPULAR
                      </span>
                    </div>
                  ) : null}
                  <h4 className="text-lg font-bold text-foreground mb-1">{plan.id}</h4>
                  <p className="text-[0.625rem] text-muted-foreground mb-4">{plan.target}</p>
                  <div className="flex items-end gap-1 mb-6 pb-6 border-b border-border">
                    <span className="text-2xl font-black text-foreground">{plan.price}</span>
                    <span className="text-[0.625rem] text-muted-foreground mb-1">/ month</span>
                  </div>
                  <ul className="text-[0.6875rem] text-muted-foreground space-y-3 mb-8">
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-primary" /> {plan.tokens}
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-primary" /> 모든 상권 분석 지표 제공
                    </li>
                  </ul>
                  <div className="mt-auto">
                    <button
                      onClick={() =>
                        showToast(
                          'info',
                          isCurrent
                            ? '이미 사용 중인 플랜입니다.'
                            : '결제 및 플랜 변경은 정식 오픈 후 지원됩니다.',
                        )
                      }
                      disabled={isCurrent}
                      className={
                        isCurrent
                          ? 'w-full py-3 bg-secondary text-muted-foreground border border-border text-xs font-bold rounded-xl cursor-not-allowed'
                          : 'w-full py-3 bg-card text-muted-foreground border border-border text-xs font-bold rounded-xl group-hover:bg-primary group-hover:text-primary-foreground group-hover:border-transparent transition-all duration-300 shadow-[0_0_20px_rgba(0,44,209,0)] group-hover:shadow-[0_0_20px_rgba(0,44,209,0.4)]'
                      }
                    >
                      {isCurrent ? '현재 플랜' : '플랜 문의하기'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   View 5: My Page (내 정보 관리 + Danger Zone)
   ═══════════════════════════════════════════════════════ */
function MyPageView() {
  const { user, logout } = useAuth();
  const { showToast } = useToast();
  const nav = useTransition();

  const isManager = user?.role === 'manager';

  const [contactName, setContactName] = useState(user?.contact_name || '');
  const [position, setPosition] = useState(user?.position || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [storeCount, setStoreCount] = useState<string>(user?.store_count || '');

  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showDeleteAlert, setShowDeleteAlert] = useState(false);
  const [actionType, setActionType] = useState<'update' | 'delete'>('update');
  const [passwordInput, setPasswordInput] = useState('');
  const [passwordError, setPasswordError] = useState('');

  // 최초 mount 시 백엔드 최신 프로필 반영
  useEffect(() => {
    if (!user?.id) return;
    setIsLoadingProfile(true);
    const endpoint = isManager
      ? `/api/auth/manager/${user.id}/profile`
      : `/api/auth/user/${user.id}`;
    fetch(endpoint)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === 'success' && data.profile) {
          const p = data.profile;
          setContactName(p.contact_name || '');
          setPosition(p.position || '');
          setPhone(p.phone || '');
          if (p.store_count !== undefined && p.store_count !== null) {
            setStoreCount(String(p.store_count));
          }
        }
      })
      .catch(() => {
        /* 네트워크 오류는 조용히 — 이미 localStorage로 기본값 세팅됨 */
      })
      .finally(() => setIsLoadingProfile(false));
  }, [user?.id, isManager]);

  const handleActionRequest = (type: 'update' | 'delete') => {
    setActionType(type);
    setPasswordInput('');
    setPasswordError('');
    if (type === 'delete') {
      setShowDeleteAlert(true);
    } else {
      setShowPasswordModal(true);
    }
  };

  const handlePasswordConfirm = async () => {
    if (passwordInput.length < 8) {
      setPasswordError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    if (!user?.id) return;
    setIsSaving(true);
    setPasswordError('');

    try {
      if (actionType === 'update') {
        // 프로필 수정 API 호출 (백엔드가 내부에서 비밀번호 검증은 별도 로직 필요 —
        // 현재 스펙상 비밀번호는 UX 확인용으로만 사용하고 PUT /auth/user/{id}로 전송)
        const endpoint = isManager
          ? `/api/auth/manager/${user.id}/profile`
          : `/api/auth/user/${user.id}`;
        const body: Record<string, unknown> = {
          contact_name: contactName,
          position,
          phone,
        };
        if (!isManager && storeCount.trim() !== '') {
          const parsed = Number(storeCount);
          if (!Number.isNaN(parsed)) body.store_count = parsed;
        }
        const res = await fetch(endpoint, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.status === 'success') {
          showToast('success', '정보가 성공적으로 변경되었습니다.');
          setShowPasswordModal(false);
        } else {
          setPasswordError(data.message || '변경 실패. 다시 시도해주세요.');
        }
      } else {
        // 탈퇴 — 소프트 삭제 (is_active=false, 소속 매니저·초대코드 일괄 비활성화)
        const res = await fetch(`/api/auth/user/${user.id}/deactivate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: passwordInput }),
        });
        const data = await res.json();
        if (data.status === 'success') {
          showToast('success', data.message || '탈퇴가 완료되었습니다.');
          setShowPasswordModal(false);
          setTimeout(() => {
            logout();
            nav('/');
          }, 1200);
        } else {
          setPasswordError(data.message || '탈퇴 처리에 실패했습니다.');
        }
      }
    } catch {
      setPasswordError('서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-4xl flex flex-col gap-6">
      {/* 내 정보 수정 (Profile Settings) */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.19, 1, 0.22, 1] }}
        className="box-glass rounded-2xl p-8"
      >
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-foreground mb-2">내 정보 관리</h3>
            <p className="text-xs text-muted-foreground">
              {isManager
                ? '매니저 프로필 정보를 수정할 수 있습니다.'
                : '팀장(마스터) 권한 이양 및 담당자 변경을 위해 가입 정보를 수정할 수 있습니다.'}
            </p>
          </div>
          {isLoadingProfile && <Loader2 className="w-4 h-4 text-primary animate-spin shrink-0" />}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="text-xs font-bold text-foreground block mb-1.5">이름</label>
            <input
              type="text"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              placeholder="홍길동"
              className="w-full bg-card border border-border rounded-lg px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-foreground block mb-1.5">
              이메일 (ID)
              <span className="ml-2 text-[0.5625rem] font-mono text-muted-foreground uppercase">
                Read-only
              </span>
            </label>
            <input
              type="email"
              value={user?.email || ''}
              readOnly
              disabled
              className="w-full bg-card/50 border border-border rounded-lg px-4 py-2.5 text-sm text-muted-foreground font-mono cursor-not-allowed"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-foreground block mb-1.5">직책</label>
            <input
              type="text"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              placeholder="팀장 / 과장 / 매니저"
              className="w-full bg-card border border-border rounded-lg px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-foreground block mb-1.5">연락처</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="010-0000-0000"
              className="w-full bg-card border border-border rounded-lg px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-primary transition-colors"
            />
          </div>
          {!isManager && (
            <div className="md:col-span-2">
              <label className="text-xs font-bold text-foreground block mb-1.5">가맹점 수</label>
              <input
                type="number"
                min={0}
                value={storeCount}
                onChange={(e) => setStoreCount(e.target.value)}
                placeholder="0"
                className="w-full bg-card border border-border rounded-lg px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-primary transition-colors"
              />
            </div>
          )}
        </div>

        <div className="mt-8 flex justify-end">
          <button
            onClick={() => handleActionRequest('update')}
            disabled={!contactName.trim()}
            className="px-6 py-2.5 bg-primary text-primary-foreground text-sm font-bold rounded-lg shadow-[0_0_20px_rgba(0,44,209,0.4)] hover:bg-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            변경사항 저장
          </button>
        </div>
      </motion.div>

      {/* Danger Zone — 회원 탈퇴 (팀장 전용) */}
      {!isManager ? (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.08, ease: [0.19, 1, 0.22, 1] }}
          className="box-glass rounded-2xl p-8 ring-1 ring-danger/20"
        >
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-danger" />
            <h3 className="text-lg font-bold text-danger">Danger Zone</h3>
          </div>
          <p className="text-xs text-muted-foreground mb-6">
            워크스페이스를 탈퇴하고 모든 데이터를 DB에서 영구적으로 파기합니다. 이 작업은 되돌릴 수
            없습니다.
          </p>
          <button
            onClick={() => handleActionRequest('delete')}
            className="px-6 py-2.5 bg-danger/10 text-danger border border-danger/30 hover:bg-danger hover:text-white text-sm font-bold rounded-lg transition-colors"
          >
            회원 탈퇴 및 워크스페이스 삭제
          </button>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.08, ease: [0.19, 1, 0.22, 1] }}
          className="bg-card border border-border rounded-2xl p-6 flex items-start gap-4"
        >
          <div className="w-9 h-9 rounded-full bg-card flex items-center justify-center shrink-0 mt-0.5">
            <Shield className="w-4 h-4 text-primary" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold text-foreground mb-1">
              계정 해지는 팀장을 통해 진행됩니다
            </p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              매니저 계정은 개별 탈퇴가 불가합니다. 퇴사 등으로 계정 해지가 필요하면 소속 팀장에게
              '팀 및 권역 관리 → 매니저 제거'를 요청해주세요.
            </p>
          </div>
        </motion.div>
      )}

      {/* 회원 탈퇴 경고 Alert 모달 */}
      <AnimatePresence>
        {showDeleteAlert && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          >
            <div
              className="absolute inset-0 bg-black/80 backdrop-blur-sm"
              onClick={() => setShowDeleteAlert(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
              className="relative bg-card border border-danger/50 rounded-2xl p-8 shadow-[0_0_50px_rgba(244,63,94,0.15)] max-w-md w-full"
            >
              <div className="w-12 h-12 rounded-full bg-danger/10 flex items-center justify-center mb-4 border border-danger/20">
                <AlertTriangle className="w-6 h-6 text-danger" />
              </div>
              <h3 className="text-xl font-black text-foreground mb-2">정말로 탈퇴하시겠습니까?</h3>
              <div className="bg-danger/10 border border-danger/20 p-4 rounded-lg mb-6">
                <p className="text-sm text-danger font-bold leading-relaxed">
                  구독 후 1회 이상 시뮬레이션을 실행한 경우, 중간에 탈퇴하더라도 남은 기간에 대한
                  환불이 불가합니다.
                </p>
              </div>
              <p className="text-xs text-muted-foreground mb-8">
                탈퇴 시 귀하의 계정과 시뮬레이션 히스토리 등 모든 데이터가 영구적으로 삭제됩니다.
              </p>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowDeleteAlert(false)}
                  className="px-4 py-2 bg-card hover:bg-muted text-foreground text-sm font-bold rounded-lg transition-colors border border-border"
                >
                  취소
                </button>
                <button
                  onClick={() => {
                    setShowDeleteAlert(false);
                    setShowPasswordModal(true);
                  }}
                  className="px-4 py-2 bg-danger hover:bg-danger/90 text-white text-sm font-bold rounded-lg transition-colors shadow-[0_0_15px_rgba(244,63,94,0.4)]"
                >
                  탈퇴합니다
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 비밀번호 재확인 모달 */}
      <AnimatePresence>
        {showPasswordModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          >
            <div
              className="absolute inset-0 bg-black/80 backdrop-blur-sm"
              onClick={() => !isSaving && setShowPasswordModal(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
              className="relative bg-card border border-border rounded-2xl p-8 shadow-2xl max-w-sm w-full"
            >
              <h3 className="text-lg font-bold text-foreground mb-2">본인 인증</h3>
              <p className="text-xs text-muted-foreground mb-6">
                {actionType === 'delete' ? '안전한 탈퇴 처리를 위해' : '정보 수정을 위해'} 현재
                비밀번호를 입력해주세요.
              </p>
              <input
                type="password"
                autoFocus
                value={passwordInput}
                onChange={(e) => {
                  setPasswordInput(e.target.value);
                  setPasswordError('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handlePasswordConfirm();
                }}
                placeholder="비밀번호 입력"
                className="w-full bg-card border border-border rounded-lg px-4 py-3 text-sm text-foreground focus:outline-none focus:border-primary mb-2 transition-colors"
              />
              {passwordError && (
                <p className="text-[0.6875rem] text-danger mb-4">{passwordError}</p>
              )}
              {!passwordError && <div className="mb-4" />}
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowPasswordModal(false)}
                  disabled={isSaving}
                  className="px-4 py-2 text-muted-foreground hover:text-foreground text-sm font-bold transition-colors disabled:opacity-50"
                >
                  취소
                </button>
                <button
                  onClick={handlePasswordConfirm}
                  disabled={isSaving || passwordInput.length < 8}
                  className={`px-4 py-2 text-white text-sm font-bold rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                    actionType === 'delete'
                      ? 'bg-danger hover:bg-danger/90'
                      : 'bg-primary hover:bg-primary'
                  }`}
                >
                  {isSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  확인
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Manager Workspace — 매니저 전용 HQ
   ═══════════════════════════════════════════════════════
   마스터의 Command Center와 달리 매니저는 아래 2개만 필요:
   1. 내 워크스페이스 — 내가 실행한 시뮬레이션 기록 + 나에게 들어온 의뢰
   2. 내 정보 관리 — MyPageView 재사용
   TODO(backend): GET /simulations?manager_id=... + 의뢰 관계 테이블 (IM3 Jira 전달 예정)
   ═══════════════════════════════════════════════════════ */
type ManagerMenuId = 'workspace' | 'history' | 'mypage';

function ManagerWorkspace() {
  const [searchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab') as ManagerMenuId | null;
  const [activeMenu, setActiveMenu] = useState<ManagerMenuId>(
    tabFromUrl && ['workspace', 'history', 'mypage'].includes(tabFromUrl)
      ? tabFromUrl
      : 'workspace',
  );
  const { user } = useAuth();

  useEffect(() => {
    if (tabFromUrl && ['workspace', 'history', 'mypage'].includes(tabFromUrl)) {
      setActiveMenu(tabFromUrl);
    }
  }, [tabFromUrl]);

  return (
    <div className="absolute inset-0 z-20 flex bg-card text-foreground font-sans overflow-hidden select-none">
      {/* 좌측 사이드바 */}
      <div className="w-64 bg-card border-r border-border flex flex-col z-20 shrink-0">
        <div className="h-20 flex items-center px-6 border-b border-border gap-3 mt-24">
          <BrandLogo
            name={user?.contact_name || 'Manager'}
            isUser={true}
            tone="accent"
            className="w-8 h-8 text-xs rounded-full shrink-0"
          />
          <div className="flex flex-col min-w-0">
            <span className="font-black text-sm text-foreground truncate">
              {user?.contact_name || 'Manager'}
            </span>
            <span className="text-[0.5625rem] text-primary font-mono tracking-widest uppercase">
              Regional Manager
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-6 px-4 flex flex-col gap-2">
          <p className="px-2 text-[0.625rem] font-bold text-muted-foreground mb-2 tracking-widest">
            WORKSPACE
          </p>
          <MenuButton
            active={activeMenu === 'workspace'}
            onClick={() => setActiveMenu('workspace')}
            icon={<LayoutTemplate className="w-4 h-4" />}
            label="내 워크스페이스"
          />
          <MenuButton
            active={activeMenu === 'history'}
            onClick={() => setActiveMenu('history')}
            icon={<History className="w-4 h-4" />}
            label="내 시뮬 이력"
          />

          <p className="px-2 text-[0.625rem] font-bold text-muted-foreground mt-6 mb-2 tracking-widest">
            SETTINGS
          </p>
          <MenuButton
            active={activeMenu === 'mypage'}
            onClick={() => setActiveMenu('mypage')}
            icon={<UserCog className="w-4 h-4" />}
            label="내 정보 관리"
          />
        </div>

        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-3 p-2 rounded-lg">
            <BrandLogo
              name={user?.contact_name || '매니저'}
              isUser={true}
              tone="accent"
              className="w-8 h-8 text-xs rounded-full shrink-0"
            />
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-xs font-bold text-foreground truncate">
                {user?.contact_name || '매니저'}
              </span>
              <span className="text-[0.625rem] text-primary truncate">Regional Access</span>
            </div>
          </div>
        </div>
      </div>

      {/* 우측 메인 영역 */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-card">
        <header className="h-20 border-b border-border flex items-center justify-between px-8 bg-card/80 backdrop-blur-md z-10 shrink-0 mt-24">
          <h2 className="text-lg font-bold flex items-center gap-2">
            {activeMenu === 'workspace' && '내 워크스페이스'}
            {activeMenu === 'history' && '내 시뮬 이력'}
            {activeMenu === 'mypage' && '내 정보 관리'}
          </h2>
        </header>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-8">
          <div className="max-w-[1920px] w-full mx-auto xl:px-10 2xl:px-16">
            {activeMenu === 'workspace' && <ManagerWorkspaceView />}
            {activeMenu === 'history' && <HistoryList />}
            {activeMenu === 'mypage' && <MyPageView />}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───── Manager Workspace View ─────
   내 시뮬레이션 기록 (HistoryList 실연동) + 의뢰 목록 (백엔드 API 대기) */
function ManagerWorkspaceView() {
  return (
    <div className="flex flex-col gap-8">
      {/* 내 시뮬레이션 기록 — simulation_history 실데이터 연동 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-primary" />내 시뮬레이션 기록
          </h3>
          <span className="text-[0.625rem] font-mono text-muted-foreground uppercase tracking-widest">
            Recent Runs
          </span>
        </div>
        <HistoryList />
      </section>

      {/* 시뮬레이션 의뢰 목록 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <Users className="w-4 h-4 text-primary" />
            시뮬레이션 의뢰 목록
          </h3>
          <span className="text-[0.625rem] font-mono text-muted-foreground uppercase tracking-widest">
            Client Requests
          </span>
        </div>
        <div className="bg-card border border-dashed border-border rounded-xl p-10 flex flex-col items-center justify-center text-center">
          <div className="w-10 h-10 rounded-full bg-card flex items-center justify-center mb-3">
            <Users className="w-5 h-5 text-muted-foreground" />
          </div>
          <p className="text-sm font-bold text-muted-foreground mb-1">들어온 의뢰가 없습니다.</p>
          <p className="text-xs text-muted-foreground mb-4">
            팀장이 의뢰 요청을 배정하면 이 목록에 표시됩니다.
          </p>
          <p className="text-[0.625rem] font-mono text-primary/60 uppercase tracking-wider">
            [Backend 연동 대기 중 — IM3 Jira]
          </p>
        </div>
      </section>
    </div>
  );
}
