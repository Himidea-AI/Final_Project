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
import { useTransition } from '../App';
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
  Crosshair,
  Zap,
  TrendingUp,
  ChevronDown,
  Trash2,
  Pencil,
  AlertTriangle,
  ShieldAlert,
  UserCog,
  Shield,
  Loader2,
} from 'lucide-react';

/* ═══════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════ */
type MenuId = 'team' | 'pipeline' | 'tuning' | 'billing' | 'mypage';

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
    if (tabFromUrl && ['team', 'pipeline', 'tuning', 'billing', 'mypage'].includes(tabFromUrl)) {
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
    <div className="absolute inset-0 z-20 flex bg-[#1e1b18] text-[#e2e8f0] font-sans overflow-hidden select-none">
      {/* ==========================================
          좌측 사이드바 (LNB)
          ========================================== */}
      <div className="w-64 bg-[#2c2825] border-r border-[#3a3633] flex flex-col z-20 shrink-0">
        {/* 워크스페이스 로고 영역 — auth.user 기반 동적 */}
        <div className="h-20 flex items-center px-6 border-b border-[#3a3633] gap-3 cursor-pointer group mt-24">
          <BrandLogo
            name={user?.company_name || "SPOTTER"}
            isUser={false}
            className="w-8 h-8 text-xs rounded-lg shrink-0"
          />
          <div className="flex flex-col min-w-0">
            <span
              className="font-black text-sm text-[#e2e8f0] group-hover:text-[#818cf8] transition-colors truncate"
              title={user?.company_name || "SPOTTER Workspace"}
            >
              {user?.company_name || "SPOTTER Workspace"}
            </span>
            <span className="text-[9px] text-[#9ca3af] font-mono tracking-widest uppercase">
              SPOTTER-HQ
            </span>
          </div>
        </div>

        {/* 메뉴 리스트 */}
        <div className="flex-1 overflow-y-auto py-6 px-4 flex flex-col gap-2">
          <p className="px-2 text-[10px] font-bold text-[#9ca3af] mb-2 tracking-widest">
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
            label="브랜드 AI 튜닝"
          />

          <p className="px-2 text-[10px] font-bold text-[#9ca3af] mt-6 mb-2 tracking-widest">
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

        {/* 하단 유저 프로필 — auth.user 기반 동적 (master / manager 분기) */}
        <div className="p-4 border-t border-[#3a3633]">
          <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-[#1e1b18] cursor-pointer transition-colors">
            <BrandLogo
              name={user?.contact_name || "사용자"}
              isUser={true}
              tone="accent"
              className="w-8 h-8 text-xs rounded-full shrink-0"
            />
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-xs font-bold text-[#e2e8f0] flex items-center gap-1.5">
                <span className="truncate">{user?.contact_name || "사용자"}</span>
                <span className="text-[9px] font-mono text-[#9ca3af] uppercase shrink-0">
                  · {user?.role === "manager" ? "매니저" : "팀장"}
                </span>
              </span>
              <span className="text-[10px] text-[#818cf8] truncate">
                {user?.role === "manager"
                  ? "Regional Access"
                  : `${user?.plan || "Pro"} Plan`}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ==========================================
          우측 메인 콘텐츠 영역
          ========================================== */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#1e1b18]">
        {/* 상단 툴바 */}
        <header className="h-20 border-b border-[#3a3633] flex items-center justify-between px-8 bg-[#1e1b18]/80 backdrop-blur-md z-10 shrink-0 mt-24">
          <h2 className="text-lg font-bold flex items-center gap-2">
            {activeMenu === 'team' && '팀 및 권역 관리'}
            {activeMenu === 'pipeline' && '출점 파이프라인 보드'}
            {activeMenu === 'tuning' && '자사 브랜드 AI 튜닝 (Master Data)'}
            {activeMenu === 'billing' && '결제 및 API 토큰 관리'}
            {activeMenu === 'mypage' && '내 정보 관리'}
          </h2>

          <div className="flex items-center gap-4">
            {activeMenu !== 'mypage' && (
              <button
                onClick={() => {
                  if (activeMenu === 'team') {
                    void handleIssueInviteCode();
                  } else {
                    showToast('info', '해당 기능은 정식 서비스에서 제공됩니다.');
                  }
                }}
                disabled={activeMenu === 'team' && isIssuing}
                className="h-9 px-4 bg-[#818cf8] hover:bg-[#6366f1] text-[#1e1b18] text-xs font-bold rounded-full flex items-center gap-2 shadow-[0_0_15px_rgba(129,140,248,0.3)] hover:shadow-[0_0_20px_rgba(129,140,248,0.5)] transition-all duration-200 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {activeMenu === 'team' && isIssuing ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-[#1e1b18]/40 border-t-[#1e1b18] rounded-full animate-spin" />
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
            {activeMenu === 'tuning' && <BrandTuningView />}
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
      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg transition-all duration-200 group ${
        active
          ? 'bg-[#818cf8]/10 text-[#818cf8]'
          : 'text-[#9ca3af] hover:bg-[#3a3633]/30 hover:text-[#e2e8f0]'
      }`}
    >
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      {badge && (
        <span className="w-4 h-4 rounded-full bg-rose-500 text-white text-[9px] font-black flex items-center justify-center animate-pulse">
          {badge}
        </span>
      )}
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
        className={`w-full flex items-center justify-between bg-[#2c2825] border rounded-lg px-3.5 py-2.5 text-xs transition-colors ${
          open
            ? 'border-[#818cf8] text-[#e2e8f0]'
            : value
              ? 'border-[#3a3633] text-[#e2e8f0] hover:border-[#818cf8]/50'
              : 'border-[#3a3633] text-[#9ca3af] hover:border-[#818cf8]/50'
        }`}
      >
        <span className="font-medium">{value || placeholder}</span>
        <ChevronDown
          className={`w-3.5 h-3.5 transition-transform duration-200 ${
            open ? 'rotate-180 text-[#818cf8]' : 'text-[#9ca3af]'
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
            className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 origin-top bg-[#1e1b18] border border-[#3a3633] rounded-lg shadow-2xl overflow-hidden"
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
                          ? 'bg-[#818cf8]/10 text-[#818cf8] font-bold'
                          : 'text-[#e2e8f0] hover:bg-[#2c2825]'
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
      if (e.key === "Escape") setOpen(false);
    };
    const onScrollOrResize = () => setOpen(false);

    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open]);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-[#9ca3af] hover:text-[#818cf8] transition-colors p-1 rounded hover:bg-[#1e1b18]"
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
                position: "fixed",
                top: position.top,
                left: position.left,
                width: MENU_WIDTH,
              }}
              className="z-[1000] origin-top-right bg-[#1e1b18] border border-[#3a3633] rounded-lg shadow-2xl overflow-hidden"
            >
              <ul className="py-1">
                <li>
                  <button
                    type="button"
                    onClick={() => {
                      onReassign();
                      setOpen(false);
                    }}
                    className="w-full text-left px-3.5 py-2 text-xs text-[#e2e8f0] hover:bg-[#2c2825] flex items-center gap-2.5 transition-colors"
                  >
                    <Pencil className="w-3.5 h-3.5 text-[#818cf8]" />
                    담당 권역 변경
                  </button>
                </li>
                <li className="border-t border-[#3a3633]">
                  <button
                    type="button"
                    onClick={() => {
                      onDelete();
                      setOpen(false);
                    }}
                    className="w-full text-left px-3.5 py-2 text-xs text-rose-400 hover:bg-rose-500/10 flex items-center gap-2.5 transition-colors"
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
  const [gu, setGu] = useState<string>("");
  const [dongs, setDongs] = useState<string[]>([]);

  // 모달이 새 매니저로 열릴 때마다 기존 권역 값으로 초기화
  useEffect(() => {
    if (manager) {
      setGu(manager.assigned_gu ?? "");
      setDongs(manager.assigned_dongs ?? []);
    } else {
      setGu("");
      setDongs([]);
    }
  }, [manager]);

  if (!manager) return null;

  const toggleDong = (dong: string) => {
    setDongs((prev) =>
      prev.includes(dong) ? prev.filter((d) => d !== dong) : [...prev, dong],
    );
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
          className="w-full max-w-md bg-[#2c2825] border border-[#3a3633] rounded-2xl shadow-2xl overflow-hidden"
        >
          <div className="px-6 py-5 border-b border-[#3a3633]">
            <h3 className="text-sm font-black text-white flex items-center gap-2">
              <Pencil className="w-4 h-4 text-[#818cf8]" />
              담당 권역 변경
            </h3>
            <p className="text-[11px] text-[#9ca3af] mt-1">
              {manager.contact_name} 매니저의 담당 구/행정동을 변경합니다.
            </p>
          </div>

          <div className="p-6 space-y-4">
            <div>
              <label className="text-[10px] text-[#9ca3af] uppercase tracking-wider font-bold block mb-2">
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
                <p className="text-[10px] text-[#9ca3af] mb-2">
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
                        className={`px-2.5 py-1 rounded-full text-[10px] font-medium border transition-all ${
                          selected
                            ? "bg-[#818cf8]/15 border-[#818cf8] text-[#818cf8]"
                            : "bg-transparent border-[#3a3633] text-[#9ca3af] hover:border-[#818cf8]/50 hover:text-[#e2e8f0]"
                        }`}
                      >
                        {dong}
                      </button>
                    );
                  })}
                </div>
                {dongs.length > 0 && (
                  <p className="text-[10px] text-[#818cf8] mt-2 font-mono">
                    {dongs.length}개 동 선택됨
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="px-6 py-4 border-t border-[#3a3633] bg-[#1e1b18]/50 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isBusy}
              className="px-4 py-2 text-xs font-bold text-[#9ca3af] hover:text-white transition-colors"
            >
              취소
            </button>
            <button
              type="button"
              onClick={() =>
                onSave(manager.id, gu || null, dongs.length ? dongs : null)
              }
              disabled={isBusy}
              className="px-4 py-2 bg-[#818cf8] hover:bg-[#6366f1] text-[#1e1b18] text-xs font-bold rounded-lg shadow-[0_0_15px_rgba(129,140,248,0.3)] hover:shadow-[0_0_20px_rgba(129,140,248,0.5)] transition-all duration-200 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isBusy ? (
                <>
                  <div className="w-3 h-3 border-2 border-[#1e1b18]/40 border-t-[#1e1b18] rounded-full animate-spin" />
                  저장 중...
                </>
              ) : (
                "변경 저장"
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
          className="w-full max-w-sm bg-[#2c2825] border border-[#3a3633] rounded-2xl shadow-2xl overflow-hidden"
        >
          <div className="px-6 py-5 border-b border-[#3a3633]">
            <h3 className="text-sm font-black text-white flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-500" />
              매니저 제거 (퇴사 처리)
            </h3>
          </div>

          <div className="p-6 space-y-3 text-sm">
            <p className="text-[#e2e8f0]">
              <span className="font-bold text-white">{manager.contact_name}</span>
              <span className="text-[#9ca3af] text-xs"> ({manager.email})</span>
              <br />
              매니저를 워크스페이스에서 제거하시겠습니까?
            </p>
            <div className="p-3 bg-rose-500/5 border border-rose-500/20 rounded-lg">
              <p className="text-[11px] text-rose-400 leading-relaxed">
                해당 매니저는 즉시 비활성화되며 더 이상 로그인할 수 없습니다.
                담당 권역 할당 정보는 보존되지만 복구하려면 재승인이 필요합니다.
              </p>
            </div>
          </div>

          <div className="px-6 py-4 border-t border-[#3a3633] bg-[#1e1b18]/50 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isBusy}
              className="px-4 py-2 text-xs font-bold text-[#9ca3af] hover:text-white transition-colors"
            >
              취소
            </button>
            <button
              type="button"
              onClick={() => onConfirm(manager.id)}
              disabled={isBusy}
              className="px-4 py-2 bg-rose-500 hover:bg-rose-600 text-white text-xs font-bold rounded-lg shadow-[0_0_15px_rgba(244,63,94,0.3)] hover:shadow-[0_0_20px_rgba(244,63,94,0.5)] transition-all duration-200 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
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
    <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-lg shadow-rose-500/5">
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
              <span className="text-base font-bold text-[#e2e8f0]">
                {manager.contact_name}
              </span>
              <span className="px-1.5 py-0.5 bg-rose-500/10 text-rose-400 rounded text-[9px] font-bold uppercase tracking-wider border border-rose-500/20">
                Pending
              </span>
              {manager.position && (
                <span className="px-1.5 py-0.5 bg-[#3a3633] text-[#a3a3a3] rounded text-[9px] font-bold uppercase tracking-wider">
                  {manager.position}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-[#6b7280]">
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
            className="p-2 bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500 hover:text-white rounded-lg transition-colors border border-emerald-500/20 disabled:opacity-50 disabled:cursor-wait"
            title="승인"
          >
            <CheckCircle2 className="w-5 h-5" />
          </button>
          <button
            onClick={() => onReject(manager.id)}
            disabled={isBusy}
            className="p-2 bg-rose-500/10 text-rose-500 hover:bg-rose-500 hover:text-white rounded-lg transition-colors border border-rose-500/20 disabled:opacity-50 disabled:cursor-wait"
            title="거절"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* 구 → 동 선택 */}
      <div className="bg-[#1e1b18] border border-[#3a3633] rounded-lg p-4">
        <p className="text-[10px] text-[#9ca3af] uppercase tracking-wider font-bold mb-3">
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
            <p className="text-[10px] text-[#9ca3af] mb-2">{pendingGu} 행정동 선택 (복수 가능)</p>
            <div className="flex flex-wrap gap-1.5">
              {REGION_DATA[pendingGu]?.map((dong) => {
                const selected = pendingDongs.includes(dong);
                return (
                  <button
                    key={dong}
                    onClick={() => toggleDong(dong)}
                    className={`px-2.5 py-1 rounded-full text-[10px] font-medium border transition-all ${
                      selected
                        ? 'bg-[#818cf8]/15 border-[#818cf8] text-[#818cf8]'
                        : 'bg-transparent border-[#3a3633] text-[#9ca3af] hover:border-[#818cf8]/50 hover:text-[#e2e8f0]'
                    }`}
                  >
                    {dong}
                  </button>
                );
              })}
            </div>
            {pendingDongs.length > 0 && (
              <p className="text-[10px] text-[#818cf8] mt-2 font-mono">
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
  const [sortBy, setSortBy] = useState<string>("이름순 (가나다)");
  const sortedActive = useMemo(() => {
    const arr = [...active];
    if (sortBy === "이름순 (가나다)") {
      return arr.sort((a, b) =>
        a.contact_name.localeCompare(b.contact_name, "ko"),
      );
    }
    if (sortBy === "담당 권역순") {
      return arr.sort((a, b) => {
        // 미배정은 끝으로 밀기 (한글 "ㅎ" 이후로 정렬)
        const guA = a.assigned_gu || "힣";
        const guB = b.assigned_gu || "힣";
        const byGu = guA.localeCompare(guB, "ko");
        if (byGu !== 0) return byGu;
        return a.contact_name.localeCompare(b.contact_name, "ko");
      });
    }
    if (sortBy === "최근 가입순") {
      return arr.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
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
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            owner_id: user.id,
            assigned_gu: gu,
            assigned_dongs: dongs && dongs.length ? dongs : null,
          }),
        });
        const data = await res.json();
        if (data.status === "success") {
          showToast("success", "담당 권역이 업데이트되었습니다.");
          refetch();
          setReassignTarget(null);
        } else {
          showToast("error", data.message || "권역 변경에 실패했습니다.");
        }
      } catch {
        showToast("error", "서버 연결에 실패했습니다.");
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
              pending.length > 0 ? 'bg-rose-500 animate-pulse' : 'bg-[#404040]'
            }`}
          />
          승인 대기 중인 매니저 ({pending.length})
        </h3>

        {isLoading && managers.length === 0 ? (
          <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-10 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-[#3a3633] border-t-[#818cf8] rounded-full animate-spin" />
          </div>
        ) : pending.length === 0 ? (
          <div className="bg-[#1e1b18] border border-dashed border-[#3a3633] rounded-xl p-8 flex flex-col items-center justify-center text-center">
            <div className="w-10 h-10 rounded-full bg-[#2c2825] flex items-center justify-center mb-3">
              <ShieldAlert className="w-5 h-5 text-[#6b7280]" />
            </div>
            <p className="text-sm font-bold text-[#a3a3a3] mb-1">
              대기 중인 요청이 없습니다.
            </p>
            <p className="text-xs text-[#6b7280]">
              우측 상단의 <span className="text-[#818cf8] font-bold">초대코드 발급</span> 버튼을 눌러 팀원을 초대하세요.
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
          <h3 className="text-sm font-bold text-[#e2e8f0]">
            활성 워크스페이스 멤버 ({active.length})
          </h3>
          {active.length > 1 && (
            <div className="w-48 shrink-0">
              <RegionSelect
                value={sortBy}
                onChange={setSortBy}
                options={["이름순 (가나다)", "담당 권역순", "최근 가입순"]}
                placeholder="정렬..."
              />
            </div>
          )}
        </div>

        {active.length === 0 ? (
          <div className="bg-[#1e1b18] border border-dashed border-[#3a3633] rounded-xl p-10 flex flex-col items-center justify-center text-center">
            <Users className="w-8 h-8 text-[#404040] mb-3" />
            <p className="text-sm font-bold text-[#a3a3a3] mb-1">
              활성 멤버가 없습니다.
            </p>
            <p className="text-xs text-[#6b7280]">
              위에서 승인 대기 중인 매니저를 승인하여 팀을 구성하세요.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {sortedActive.map((m) => {
              const hasDongs = m.assigned_dongs && m.assigned_dongs.length > 0;
              const dongSummary = hasDongs
                ? (m.assigned_dongs!.length > 3
                    ? `${m.assigned_dongs!.slice(0, 2).join(", ")} 외 ${m.assigned_dongs!.length - 2}곳`
                    : m.assigned_dongs!.join(", "))
                : "동 미지정";
              return (
                <div
                  key={m.id}
                  className="bg-[#1e1b18] border border-[#3a3633] rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between hover:border-[#818cf8]/50 hover:bg-[#2c2825]/30 transition-all duration-300 group shadow-sm gap-4 md:gap-0"
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
                        <span className="text-base font-bold text-white truncate">
                          {m.contact_name}
                        </span>
                        <span className="px-1.5 py-0.5 bg-[#3a3633] text-[#a3a3a3] rounded text-[9px] font-bold uppercase tracking-wider shrink-0">
                          {m.position || "Regional Mgr"}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-[#6b7280]">
                        <span className="font-mono truncate">{m.email}</span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Region + Status + Actions */}
                  <div className="flex items-center justify-between md:justify-end gap-6 md:gap-8 ml-16 md:ml-0">
                    {/* Assigned Region */}
                    <div className="flex flex-col items-start md:items-end gap-1.5">
                      {m.assigned_gu ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-[#818cf8]/10 text-[#818cf8] border border-[#818cf8]/20 rounded-md text-[10px] font-bold">
                          <MapPin className="w-3 h-3" />
                          {m.assigned_gu}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-[#3a3633]/50 text-[#a3a3a3] border border-[#3a3633] rounded-md text-[10px] font-bold">
                          <MapPin className="w-3 h-3" /> 미배정
                        </span>
                      )}
                      <span className="text-[10px] text-[#6b7280]">
                        {dongSummary}
                      </span>
                    </div>

                    {/* Activity Status (고정 Active) */}
                    <div className="w-20 flex justify-end shrink-0">
                      <span className="flex items-center gap-1.5 text-xs text-emerald-500 font-bold">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
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
function PipelineKanbanView() {
  const columns = [
    {
      title: '상권 분석 중',
      count: 2,
      borderColor: 'border-[#3a3633]',
      titleColor: 'text-[#9ca3af]',
    },
    {
      title: '임원 보고 대기',
      count: 1,
      borderColor: 'border-amber-500/50',
      titleColor: 'text-amber-500',
    },
    {
      title: '가맹점주 제안',
      count: 1,
      borderColor: 'border-[#818cf8]/50',
      titleColor: 'text-[#818cf8]',
    },
    {
      title: '출점 확정',
      count: 0,
      borderColor: 'border-emerald-500/50',
      titleColor: 'text-emerald-500',
    },
  ];

  return (
    <div className="flex gap-4 h-full overflow-x-auto pb-4">
      {columns.map((col, idx) => (
        <div
          key={idx}
          className={`flex-1 min-w-[280px] bg-[#2c2825] border border-[#3a3633] rounded-2xl flex flex-col overflow-hidden shadow-lg border-t-2 ${col.borderColor}`}
        >
          <div className="p-4 border-b border-[#3a3633] flex justify-between items-center bg-[#1e1b18]/30">
            <h4 className={`text-xs font-bold uppercase tracking-wider ${col.titleColor}`}>
              {col.title}
            </h4>
            <span className="w-5 h-5 rounded-full bg-[#1e1b18] flex items-center justify-center text-[10px] font-bold text-[#9ca3af] border border-[#3a3633]">
              {col.count}
            </span>
          </div>

          <div className="flex-1 p-3 flex flex-col gap-3 overflow-y-auto custom-scrollbar">
            {idx === 0 && (
              <>
                <KanbanCard
                  district="마포구 연남동"
                  date="2026.04.08"
                  revenue="32.4M"
                  score="87"
                  manager="김마포"
                />
                <KanbanCard
                  district="마포구 망원동"
                  date="2026.04.07"
                  revenue="28.1M"
                  score="76"
                  manager="김마포"
                />
              </>
            )}
            {idx === 1 && (
              <KanbanCard
                district="서초구 반포동"
                date="2026.04.05"
                revenue="45.0M"
                score="91"
                manager="이서초"
              />
            )}
            {idx === 2 && (
              <KanbanCard
                district="서대문구 창천동"
                date="2026.04.01"
                revenue="30.2M"
                score="82"
                manager="김마포"
              />
            )}
            {col.count === 0 && (
              <div className="flex-1 flex items-center justify-center border-2 border-dashed border-[#3a3633] rounded-xl m-2 opacity-50 min-h-[120px]">
                <span className="text-xs font-mono text-[#9ca3af]">Drag & Drop</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function KanbanCard({
  district,
  date,
  revenue,
  score,
  manager,
}: {
  district: string;
  date: string;
  revenue: string;
  score: string;
  manager: string;
}) {
  const { showToast } = useToast();
  return (
    <div
      onClick={() => showToast('info', '칸반 상태 변경은 정식 버전에서 지원됩니다.')}
      className="bg-[#1e1b18] border border-[#3a3633] rounded-xl p-4 cursor-grab hover:border-[#818cf8]/50 transition-colors shadow-md group"
    >
      <div className="flex justify-between items-start mb-3">
        <div>
          <span className="text-[10px] font-mono text-[#9ca3af]">{date}</span>
          <h5 className="font-bold text-sm text-[#e2e8f0] group-hover:text-[#818cf8] transition-colors">
            {district} 후보지
          </h5>
        </div>
        <BrandLogo
          name={manager}
          isUser={true}
          tone="muted"
          className="w-6 h-6 text-[9px] rounded-full"
          title={manager}
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="bg-[#2c2825] rounded-lg p-2 border border-[#3a3633] flex flex-col items-center justify-center text-center">
          <span className="text-[9px] text-[#9ca3af] block mb-0.5">예상 매출</span>
          <span className="text-xs font-black text-white flex items-center gap-1">
            <BarChart3 className="w-3 h-3 text-emerald-500" /> {revenue}
          </span>
        </div>
        <div className="bg-[#2c2825] rounded-lg p-2 border border-[#3a3633] flex flex-col items-center justify-center text-center">
          <span className="text-[9px] text-[#9ca3af] block mb-0.5">AI 매력도</span>
          <span className="text-xs font-black text-white flex items-center gap-1">
            <Crosshair className="w-3 h-3 text-amber-500" /> {score} Pts
          </span>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   View 3: Brand AI Tuning (브랜드 AI 튜닝)
   ═══════════════════════════════════════════════════════ */
function BrandTuningView() {
  const { showToast } = useToast();
  return (
    <div className="max-w-4xl mx-auto w-full flex flex-col gap-6">
      <div className="bg-[#2c2825] border border-[#818cf8]/30 rounded-2xl p-6 shadow-[0_0_30px_rgba(129,140,248,0.05)] relative overflow-hidden">
        {/* 장식용 배경 */}
        <Building2 className="absolute -right-10 -top-10 w-48 h-48 text-[#818cf8] opacity-5 pointer-events-none" />

        <div className="relative z-10">
          <h3 className="text-lg font-bold text-[#818cf8] flex items-center gap-2 mb-2">
            <Zap className="w-5 h-5" /> Brand AI Weights
          </h3>
          <p className="text-sm text-[#9ca3af] mb-8">
            우리 프랜차이즈의 특성을 입력하면, AI 예측 모델이 이를 반영하여 맞춤형 예상 매출과
            리스크를 산출합니다.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* 객단가 (AOV) 설정 */}
            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-[#e2e8f0]">예상 평균 객단가 (AOV)</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca3af] font-bold">
                  ₩
                </span>
                <input
                  type="text"
                  defaultValue="25,000"
                  className="w-full bg-[#1e1b18] border border-[#3a3633] rounded-lg pl-8 pr-4 py-2.5 text-sm font-mono text-[#e2e8f0] focus:border-[#818cf8] outline-none"
                />
              </div>
              <p className="text-[10px] text-[#9ca3af]">
                유동인구 소비력 스코어 계산에 가중치로 작용합니다.
              </p>
            </div>

            {/* 타겟 연령층 */}
            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-[#e2e8f0]">
                핵심 타겟 고객층 (Primary Target)
              </label>
              <select className="w-full bg-[#1e1b18] border border-[#3a3633] rounded-lg px-4 py-2.5 text-sm font-medium text-[#e2e8f0] focus:border-[#818cf8] outline-none appearance-none">
                <option value="2030f">2030 여성 (트렌드/디저트)</option>
                <option value="2030m">2030 남성/여성 (가성비/식사)</option>
                <option value="3040">3040 직장인 (회식/저녁)</option>
                <option value="family">주거 배후세대 (가족/배달)</option>
              </select>
              <p className="text-[10px] text-[#9ca3af]">
                선택한 타겟층의 해당 상권 거주/유동 비율을 우선 분석합니다.
              </p>
            </div>

            {/* 배달 vs 홀 비중 슬라이더 */}
            <div className="flex flex-col gap-4 md:col-span-2 mt-4 p-5 bg-[#1e1b18] border border-[#3a3633] rounded-xl">
              <div className="flex justify-between items-center">
                <label className="text-xs font-bold text-[#e2e8f0]">매출 비중 (홀 vs 배달)</label>
                <span className="text-xs font-mono font-bold text-[#818cf8]">
                  홀 30% : 배달 70%
                </span>
              </div>

              <div className="relative w-full h-3 bg-[#3a3633] rounded-full overflow-hidden flex cursor-pointer">
                <div className="h-full bg-[#3a3633]" style={{ width: '30%' }} />
                <div className="h-full bg-[#818cf8]" style={{ width: '70%' }} />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white rounded-full shadow-lg border-2 border-[#818cf8] transition-transform hover:scale-110"
                  style={{ left: 'calc(30% - 10px)' }}
                />
              </div>

              <div className="flex justify-between text-[10px] font-bold text-[#9ca3af]">
                <span>Dine-in (입지/접근성 가중치 상승)</span>
                <span>Delivery (배후세대 가중치 상승)</span>
              </div>
            </div>
          </div>

          <div className="mt-8 flex justify-end">
            <button
              onClick={() => showToast('info', 'AI 모델 가중치 업데이트 기능은 준비 중입니다.')}
              className="px-6 py-2.5 bg-[#818cf8] text-[#1e1b18] text-sm font-bold rounded-lg shadow-[0_0_20px_rgba(129,140,248,0.4)] hover:bg-[#6366f1] transition-colors"
            >
              AI 모델 업데이트 적용
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   View 4: Billing & API Token Management (결제 및 토큰)
   ═══════════════════════════════════════════════════════ */
function BillingManagementView() {
  const { showToast } = useToast();
  const currentPlan = 'Growth';
  const billingCycle = '2026. 04. 10 ~ 2026. 05. 09';
  const totalTokens = 1000;
  const usedTokens = 660;
  const remainTokens = totalTokens - usedTokens;
  const progressPercent = (usedTokens / totalTokens) * 100;
  const tokensPerSim = 15;
  const estimatedSims = Math.floor(remainTokens / tokensPerSim);

  return (
    <div className="flex flex-col gap-8 max-w-6xl">
      {/* 1. Current Subscription & Usage (Bento Box) */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 현재 요금제 */}
        <div className="group relative rounded-2xl overflow-hidden p-[2px] transition-transform duration-500 ease-out hover:-translate-y-2">
          <div
            className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500"
            style={{
              background:
                'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
            }}
          />
          <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-6 shadow-lg flex flex-col justify-between overflow-hidden border border-[#3a3633] group-hover:border-transparent transition-colors duration-500">
          <div className="absolute top-0 right-0 w-32 h-32 bg-[#818cf8]/10 blur-[40px] rounded-full pointer-events-none" />
          <div>
            <h3 className="text-[#9ca3af] text-xs font-bold uppercase tracking-widest mb-1">
              Current Plan
            </h3>
            <div className="flex items-end gap-3 mb-4">
              <h2 className="text-3xl font-black text-white">{currentPlan}</h2>
              <span className="px-2 py-1 bg-[#818cf8]/20 text-[#818cf8] border border-[#818cf8]/30 rounded-md text-[10px] font-bold mb-1">
                Active
              </span>
            </div>
            <div className="flex flex-col gap-2 mt-6">
              <div className="flex justify-between items-center border-b border-[#3a3633] pb-2">
                <span className="text-xs text-[#9ca3af]">결제 주기 (1개월)</span>
                <span className="text-xs font-mono text-[#e2e8f0]">{billingCycle}</span>
              </div>
              <div className="flex justify-between items-center border-b border-[#3a3633] pb-2">
                <span className="text-xs text-[#9ca3af]">다음 결제 예정일</span>
                <span className="text-xs font-mono text-[#e2e8f0]">2026. 05. 10</span>
              </div>
              <div className="flex justify-between items-center pb-1">
                <span className="text-xs text-[#9ca3af]">결제 수단</span>
                <span className="text-xs font-mono text-[#e2e8f0] flex items-center gap-2">
                  <CreditCard className="w-3 h-3 text-[#818cf8]" /> 비자카드 **** 1234
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={() => showToast('info', '결제 및 플랜 변경은 정식 오픈 후 지원됩니다.')}
            className="w-full mt-6 py-2.5 bg-[#1e1b18] text-[#e2e8f0] border border-[#3a3633] text-xs font-bold rounded-lg transition-all duration-300 hover:bg-[#818cf8] hover:text-[#1e1b18] hover:border-transparent hover:shadow-[0_0_20px_rgba(129,140,248,0.4)] active:scale-[0.98]"
          >
            결제 수단 관리 / 영수증
          </button>
          </div>
        </div>

        {/* API 토큰 사용량 */}
        <div className="group lg:col-span-2 relative rounded-2xl overflow-hidden p-[2px] transition-transform duration-500 ease-out hover:-translate-y-2">
          <div
            className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500"
            style={{
              background:
                'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
            }}
          />
          <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] p-6 shadow-lg flex flex-col justify-between border border-[#3a3633] group-hover:border-transparent transition-colors duration-500">
          <div>
            <div className="flex justify-between items-start mb-6">
              <div>
                <h3 className="text-[#9ca3af] text-xs font-bold uppercase tracking-widest mb-1">
                  API Tokens Usage
                </h3>
                <h2 className="text-2xl font-black text-white">
                  {usedTokens.toLocaleString()}{' '}
                  <span className="text-lg text-[#9ca3af] font-medium">
                    / {totalTokens.toLocaleString()}
                  </span>
                </h2>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-[#9ca3af] mb-1">잔여 예상 시뮬레이션</p>
                <div className="flex items-center gap-2 text-emerald-400 font-bold">
                  <Zap className="w-4 h-4" /> 약 {estimatedSims}회 가능
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="relative w-full h-4 bg-[#1e1b18] rounded-full overflow-hidden border border-[#3a3633]">
              <div
                className="absolute top-0 left-0 h-full bg-gradient-to-r from-[#6366f1] to-[#818cf8] rounded-full transition-all duration-1000 ease-out"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="flex justify-between items-center mt-2 px-1">
              <span className="text-[10px] text-[#818cf8] font-bold">
                {progressPercent.toFixed(1)}% Used
              </span>
              <span className="text-[10px] text-[#9ca3af]">
                {remainTokens.toLocaleString()} Tokens Left
              </span>
            </div>
          </div>

          <div className="mt-8 p-4 bg-[#1e1b18] border border-[#3a3633] rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#818cf8]/10 flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-[#818cf8]" />
              </div>
              <div>
                <p className="text-xs font-bold text-white">토큰이 부족하신가요?</p>
                <p className="text-[10px] text-[#9ca3af]">
                  플랜을 업그레이드하거나 일회성 토큰을 충전하세요.
                </p>
              </div>
            </div>
            <button
              onClick={() => showToast('info', '토큰 충전은 정식 오픈 후 지원됩니다.')}
              className="px-4 py-2 bg-[#818cf8] hover:bg-[#6366f1] text-[#1e1b18] text-xs font-bold rounded-lg shadow-[0_0_15px_rgba(129,140,248,0.3)] hover:shadow-[0_0_20px_rgba(129,140,248,0.5)] transition-all duration-200 active:scale-[0.98]"
            >
              즉시 충전하기
            </button>
          </div>
          </div>
        </div>
      </section>

      {/* 2. Plan Upgrade (Pricing Cards) */}
      <section className="mt-4">
        <h3 className="text-sm font-bold text-[#e2e8f0] mb-4">플랜 업그레이드</h3>
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
          ].map((plan) => (
            <div
              key={plan.id}
              className="group relative w-full rounded-2xl overflow-hidden p-[2px] transition-transform duration-500 ease-out hover:-translate-y-2"
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] flex flex-col p-6 transition-colors duration-500 border border-[#3a3633] group-hover:border-transparent">
                {plan.isPopular && (
                  <div className="absolute top-4 right-4 inline-flex items-center justify-center h-5 px-2.5 bg-[#3a3633] border border-[#818cf8]/30 rounded-full">
                    <span className="text-[9px] font-bold text-[#818cf8] tracking-wider leading-none">
                      MOST POPULAR
                    </span>
                  </div>
                )}
                <h4 className="text-lg font-bold text-white mb-1">{plan.id}</h4>
                <p className="text-[10px] text-[#9ca3af] mb-4">{plan.target}</p>
                <div className="flex items-end gap-1 mb-6 pb-6 border-b border-[#3a3633]">
                  <span className="text-2xl font-black text-white">{plan.price}</span>
                  <span className="text-[10px] text-[#9ca3af] mb-1">/ month</span>
                </div>
                <ul className="text-[11px] text-[#9ca3af] space-y-3 mb-8">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#818cf8]" /> {plan.tokens}
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#818cf8]" /> 모든 상권 분석 지표 제공
                  </li>
                </ul>
                <div className="mt-auto">
                  {currentPlan === plan.id ? (
                    <button
                      disabled
                      className="w-full py-3 bg-[#1e1b18] text-[#6b7280] text-xs font-bold rounded-xl cursor-not-allowed border border-[#3a3633]"
                    >
                      현재 사용 중인 플랜
                    </button>
                  ) : (
                    <button
                      onClick={() =>
                        showToast('info', '결제 및 플랜 변경은 정식 오픈 후 지원됩니다.')
                      }
                      className="w-full py-3 bg-[#1e1b18] text-[#9ca3af] border border-[#3a3633] text-xs font-bold rounded-xl group-hover:bg-[#818cf8] group-hover:text-[#1e1b18] group-hover:border-transparent transition-all duration-300 shadow-[0_0_20px_rgba(129,140,248,0)] group-hover:shadow-[0_0_20px_rgba(129,140,248,0.4)]"
                    >
                      이 플랜으로 변경
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
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
        // 탈퇴 — 백엔드 DELETE 엔드포인트 미구현. 현재는 placeholder
        showToast(
          'info',
          '탈퇴 요청이 접수되었습니다. (백엔드 구현 대기 중 — IM3 Jira로 전달 예정)',
        );
        setShowPasswordModal(false);
        setTimeout(() => {
          logout();
          nav('/');
        }, 1200);
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
        className="bg-[#2c2825] border border-[#3a3633] rounded-2xl p-8 shadow-lg"
      >
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-white mb-2">내 정보 관리</h3>
            <p className="text-xs text-[#9ca3af]">
              {isManager
                ? '매니저 프로필 정보를 수정할 수 있습니다.'
                : '팀장(마스터) 권한 이양 및 담당자 변경을 위해 가입 정보를 수정할 수 있습니다.'}
            </p>
          </div>
          {isLoadingProfile && (
            <Loader2 className="w-4 h-4 text-[#818cf8] animate-spin shrink-0" />
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="text-xs font-bold text-[#e2e8f0] block mb-1.5">
              이름
            </label>
            <input
              type="text"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              placeholder="홍길동"
              className="w-full bg-[#1e1b18] border border-[#3a3633] rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#818cf8] transition-colors"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-[#e2e8f0] block mb-1.5">
              이메일 (ID)
              <span className="ml-2 text-[9px] font-mono text-[#6b7280] uppercase">
                Read-only
              </span>
            </label>
            <input
              type="email"
              value={user?.email || ''}
              readOnly
              disabled
              className="w-full bg-[#1e1b18]/50 border border-[#3a3633] rounded-lg px-4 py-2.5 text-sm text-[#9ca3af] font-mono cursor-not-allowed"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-[#e2e8f0] block mb-1.5">
              직책
            </label>
            <input
              type="text"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              placeholder="팀장 / 과장 / 매니저"
              className="w-full bg-[#1e1b18] border border-[#3a3633] rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#818cf8] transition-colors"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-[#e2e8f0] block mb-1.5">
              연락처
            </label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="010-0000-0000"
              className="w-full bg-[#1e1b18] border border-[#3a3633] rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#818cf8] transition-colors"
            />
          </div>
          {!isManager && (
            <div className="md:col-span-2">
              <label className="text-xs font-bold text-[#e2e8f0] block mb-1.5">
                가맹점 수
              </label>
              <input
                type="number"
                min={0}
                value={storeCount}
                onChange={(e) => setStoreCount(e.target.value)}
                placeholder="0"
                className="w-full bg-[#1e1b18] border border-[#3a3633] rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#818cf8] transition-colors"
              />
            </div>
          )}
        </div>

        <div className="mt-8 flex justify-end">
          <button
            onClick={() => handleActionRequest('update')}
            disabled={!contactName.trim()}
            className="px-6 py-2.5 bg-[#818cf8] text-[#1e1b18] text-sm font-bold rounded-lg shadow-[0_0_20px_rgba(129,140,248,0.4)] hover:bg-[#6366f1] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
          className="bg-[#1e1b18] border border-rose-500/30 rounded-2xl p-8 shadow-lg"
        >
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-rose-500" />
            <h3 className="text-lg font-bold text-rose-500">Danger Zone</h3>
          </div>
          <p className="text-xs text-[#9ca3af] mb-6">
            워크스페이스를 탈퇴하고 모든 데이터를 DB에서 영구적으로 파기합니다. 이
            작업은 되돌릴 수 없습니다.
          </p>
          <button
            onClick={() => handleActionRequest('delete')}
            className="px-6 py-2.5 bg-rose-500/10 text-rose-500 border border-rose-500/30 hover:bg-rose-500 hover:text-white text-sm font-bold rounded-lg transition-colors"
          >
            회원 탈퇴 및 워크스페이스 삭제
          </button>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.08, ease: [0.19, 1, 0.22, 1] }}
          className="bg-[#1e1b18] border border-[#3a3633] rounded-2xl p-6 flex items-start gap-4"
        >
          <div className="w-9 h-9 rounded-full bg-[#2c2825] flex items-center justify-center shrink-0 mt-0.5">
            <Shield className="w-4 h-4 text-[#818cf8]" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold text-[#e2e8f0] mb-1">
              계정 해지는 팀장을 통해 진행됩니다
            </p>
            <p className="text-xs text-[#9ca3af] leading-relaxed">
              매니저 계정은 개별 탈퇴가 불가합니다. 퇴사 등으로 계정 해지가 필요하면
              소속 팀장에게 '팀 및 권역 관리 → 매니저 제거'를 요청해주세요.
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
              className="absolute inset-0 bg-[#050505]/80 backdrop-blur-sm"
              onClick={() => setShowDeleteAlert(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
              className="relative bg-[#1e1b18] border border-rose-500/50 rounded-2xl p-8 shadow-[0_0_50px_rgba(244,63,94,0.15)] max-w-md w-full"
            >
              <div className="w-12 h-12 rounded-full bg-rose-500/10 flex items-center justify-center mb-4 border border-rose-500/20">
                <AlertTriangle className="w-6 h-6 text-rose-500" />
              </div>
              <h3 className="text-xl font-black text-white mb-2">
                정말로 탈퇴하시겠습니까?
              </h3>
              <div className="bg-rose-500/10 border border-rose-500/20 p-4 rounded-lg mb-6">
                <p className="text-sm text-rose-400 font-bold leading-relaxed">
                  구독 후 1회 이상 시뮬레이션을 실행한 경우, 중간에 탈퇴하더라도 남은
                  기간에 대한 환불이 불가합니다.
                </p>
              </div>
              <p className="text-xs text-[#9ca3af] mb-8">
                탈퇴 시 귀하의 계정과 시뮬레이션 히스토리 등 모든 데이터가 영구적으로
                삭제됩니다.
              </p>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowDeleteAlert(false)}
                  className="px-4 py-2 bg-[#2c2825] hover:bg-[#3a3633] text-[#e2e8f0] text-sm font-bold rounded-lg transition-colors border border-[#3a3633]"
                >
                  취소
                </button>
                <button
                  onClick={() => {
                    setShowDeleteAlert(false);
                    setShowPasswordModal(true);
                  }}
                  className="px-4 py-2 bg-rose-500 hover:bg-rose-600 text-white text-sm font-bold rounded-lg transition-colors shadow-[0_0_15px_rgba(244,63,94,0.4)]"
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
              className="absolute inset-0 bg-[#050505]/80 backdrop-blur-sm"
              onClick={() => !isSaving && setShowPasswordModal(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
              className="relative bg-[#2c2825] border border-[#3a3633] rounded-2xl p-8 shadow-2xl max-w-sm w-full"
            >
              <h3 className="text-lg font-bold text-white mb-2">본인 인증</h3>
              <p className="text-xs text-[#9ca3af] mb-6">
                {actionType === 'delete'
                  ? '안전한 탈퇴 처리를 위해'
                  : '정보 수정을 위해'}{' '}
                현재 비밀번호를 입력해주세요.
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
                className="w-full bg-[#1e1b18] border border-[#3a3633] rounded-lg px-4 py-3 text-sm text-white focus:outline-none focus:border-[#818cf8] mb-2 transition-colors"
              />
              {passwordError && (
                <p className="text-[11px] text-rose-400 mb-4">{passwordError}</p>
              )}
              {!passwordError && <div className="mb-4" />}
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowPasswordModal(false)}
                  disabled={isSaving}
                  className="px-4 py-2 text-[#9ca3af] hover:text-white text-sm font-bold transition-colors disabled:opacity-50"
                >
                  취소
                </button>
                <button
                  onClick={handlePasswordConfirm}
                  disabled={isSaving || passwordInput.length < 8}
                  className={`px-4 py-2 text-white text-sm font-bold rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                    actionType === 'delete'
                      ? 'bg-rose-500 hover:bg-rose-600'
                      : 'bg-[#818cf8] hover:bg-[#6366f1]'
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
type ManagerMenuId = 'workspace' | 'mypage';

function ManagerWorkspace() {
  const [searchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab') as ManagerMenuId | null;
  const [activeMenu, setActiveMenu] = useState<ManagerMenuId>(
    tabFromUrl === 'mypage' ? 'mypage' : 'workspace',
  );
  const { user } = useAuth();

  useEffect(() => {
    if (tabFromUrl && ['workspace', 'mypage'].includes(tabFromUrl)) {
      setActiveMenu(tabFromUrl);
    }
  }, [tabFromUrl]);

  return (
    <div className="absolute inset-0 z-20 flex bg-[#1e1b18] text-[#e2e8f0] font-sans overflow-hidden select-none">
      {/* 좌측 사이드바 */}
      <div className="w-64 bg-[#2c2825] border-r border-[#3a3633] flex flex-col z-20 shrink-0">
        <div className="h-20 flex items-center px-6 border-b border-[#3a3633] gap-3 mt-24">
          <BrandLogo
            name={user?.contact_name || 'Manager'}
            isUser={true}
            tone="accent"
            className="w-8 h-8 text-xs rounded-full shrink-0"
          />
          <div className="flex flex-col min-w-0">
            <span className="font-black text-sm text-[#e2e8f0] truncate">
              {user?.contact_name || 'Manager'}
            </span>
            <span className="text-[9px] text-[#818cf8] font-mono tracking-widest uppercase">
              Regional Manager
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-6 px-4 flex flex-col gap-2">
          <p className="px-2 text-[10px] font-bold text-[#9ca3af] mb-2 tracking-widest">
            WORKSPACE
          </p>
          <MenuButton
            active={activeMenu === 'workspace'}
            onClick={() => setActiveMenu('workspace')}
            icon={<LayoutTemplate className="w-4 h-4" />}
            label="내 워크스페이스"
          />

          <p className="px-2 text-[10px] font-bold text-[#9ca3af] mt-6 mb-2 tracking-widest">
            SETTINGS
          </p>
          <MenuButton
            active={activeMenu === 'mypage'}
            onClick={() => setActiveMenu('mypage')}
            icon={<UserCog className="w-4 h-4" />}
            label="내 정보 관리"
          />
        </div>

        <div className="p-4 border-t border-[#3a3633]">
          <div className="flex items-center gap-3 p-2 rounded-lg">
            <BrandLogo
              name={user?.contact_name || '매니저'}
              isUser={true}
              tone="accent"
              className="w-8 h-8 text-xs rounded-full shrink-0"
            />
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-xs font-bold text-[#e2e8f0] truncate">
                {user?.contact_name || '매니저'}
              </span>
              <span className="text-[10px] text-[#818cf8] truncate">
                Regional Access
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 우측 메인 영역 */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#1e1b18]">
        <header className="h-20 border-b border-[#3a3633] flex items-center justify-between px-8 bg-[#1e1b18]/80 backdrop-blur-md z-10 shrink-0 mt-24">
          <h2 className="text-lg font-bold flex items-center gap-2">
            {activeMenu === 'workspace' && '내 워크스페이스'}
            {activeMenu === 'mypage' && '내 정보 관리'}
          </h2>
        </header>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-8">
          <div className="max-w-[1920px] w-full mx-auto xl:px-10 2xl:px-16">
            {activeMenu === 'workspace' && <ManagerWorkspaceView />}
            {activeMenu === 'mypage' && <MyPageView />}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───── Manager Workspace View ─────
   내 시뮬레이션 기록 + 의뢰 목록 (백엔드 API 대기 중 — 빈 상태 + placeholder) */
function ManagerWorkspaceView() {
  return (
    <div className="flex flex-col gap-8">
      {/* 내 시뮬레이션 기록 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-[#e2e8f0] flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[#818cf8]" />
            내 시뮬레이션 기록
          </h3>
          <span className="text-[10px] font-mono text-[#6b7280] uppercase tracking-widest">
            Recent Runs
          </span>
        </div>
        <div className="bg-[#1e1b18] border border-dashed border-[#3a3633] rounded-xl p-10 flex flex-col items-center justify-center text-center">
          <div className="w-10 h-10 rounded-full bg-[#2c2825] flex items-center justify-center mb-3">
            <BarChart3 className="w-5 h-5 text-[#6b7280]" />
          </div>
          <p className="text-sm font-bold text-[#a3a3a3] mb-1">
            아직 실행한 시뮬레이션이 없습니다.
          </p>
          <p className="text-xs text-[#6b7280] mb-4">
            상단 메뉴의 SIMULATOR에서 첫 시뮬레이션을 실행해보세요.
          </p>
          <p className="text-[10px] font-mono text-[#818cf8]/60 uppercase tracking-wider">
            [Backend 연동 대기 중 — IM3 Jira]
          </p>
        </div>
      </section>

      {/* 시뮬레이션 의뢰 목록 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-[#e2e8f0] flex items-center gap-2">
            <Users className="w-4 h-4 text-[#818cf8]" />
            시뮬레이션 의뢰 목록
          </h3>
          <span className="text-[10px] font-mono text-[#6b7280] uppercase tracking-widest">
            Client Requests
          </span>
        </div>
        <div className="bg-[#1e1b18] border border-dashed border-[#3a3633] rounded-xl p-10 flex flex-col items-center justify-center text-center">
          <div className="w-10 h-10 rounded-full bg-[#2c2825] flex items-center justify-center mb-3">
            <Users className="w-5 h-5 text-[#6b7280]" />
          </div>
          <p className="text-sm font-bold text-[#a3a3a3] mb-1">
            들어온 의뢰가 없습니다.
          </p>
          <p className="text-xs text-[#6b7280] mb-4">
            팀장이 의뢰 요청을 배정하면 이 목록에 표시됩니다.
          </p>
          <p className="text-[10px] font-mono text-[#818cf8]/60 uppercase tracking-wider">
            [Backend 연동 대기 중 — IM3 Jira]
          </p>
        </div>
      </section>
    </div>
  );
}
