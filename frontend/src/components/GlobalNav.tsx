/**
 * GlobalNav — 글로벌 헤더 우측 영역 (LogoutButton + GlobalLimelightNav)
 * App.tsx Phase C Round 3 코드 스플릿으로 추출 — 기능 변경 없음.
 */
import React, { useState, useEffect, useRef } from 'react';
import {
  User,
  Bell,
  Settings,
  Folder,
  LogOut,
  ShieldAlert,
  CheckCircle2,
  Scale,
  AlertTriangle,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useToast } from './Toast';
import { useManagerList, formatRelativeTime } from '../hooks/useManagerList';
import { useTransition } from '../contexts/TransitionContext';

export function LogoutButton() {
  const { isLoggedIn, logout } = useAuth();
  const nav = useTransition();

  if (!isLoggedIn) return null;

  return (
    <button
      onClick={() => {
        logout();
        nav('/login');
      }}
      className="hidden md:flex items-center gap-1.5 px-3 py-1.5 text-[#9ca3af] hover:text-rose-400 hover:bg-rose-500/10 rounded-full text-xs font-medium transition-colors border border-transparent hover:border-rose-500/30"
      title="로그아웃"
    >
      <LogOut className="w-3.5 h-3.5" />
      <span>로그아웃</span>
    </button>
  );
}

/**
 * Notification Mock Items — 도메인 특화 샘플 3종
 * (실제 API 연동 전 demo 용도. 승인 대기는 실 데이터로 별도 렌더)
 */
const NOTIFICATION_MOCK_ITEMS = [
  {
    id: 'mock-legal',
    type: 'critical' as const,
    iconType: 'legal' as const,
    title: '[권리금 경고] 연남동 B권역, 최근 3년 상가임대차 갱신 거절 분쟁 급증 (Legal Agent)',
    time: '1시간 전',
    action: '법률 리스크 상세 리포트는 준비 중입니다.',
  },
  {
    id: 'mock-cannibal',
    type: 'warning' as const,
    iconType: 'cannibal' as const,
    title: '[간섭도 주의] 서교동 신규 출점 시 기존 3호점(홍대점) 예상 매출 -18% 타격 감지',
    time: '2시간 전',
    action: '카니발리제이션 분석 대시보드는 준비 중입니다.',
  },
  {
    id: 'mock-sim',
    type: 'success' as const,
    iconType: 'sim' as const,
    title: '[분석 완료] 마포구 망원동 112-4 일대 시뮬레이션 완료 및 보관함 저장됨',
    time: '5시간 전',
    action: '보관함 파이프라인은 준비 중입니다.',
  },
];

function GlobalLimelightNav() {
  const nav = useTransition();
  const { isLoggedIn, user } = useAuth();
  const { showToast } = useToast();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, opacity: 0 });
  const [openDropdown, setOpenDropdown] = useState<'bell' | null>(null);
  const navRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // 매니저 목록 — Bell 빨간 점 + 드롭다운 알림 소스
  const { pending: pendingManagers } = useManagerList();
  const isMaster = isLoggedIn && user?.role !== 'manager';
  // 마스터만 mock 알림 노출 (매니저는 승인 대기 없음 + 도메인 알림 관련 없음)
  const mockItems = isMaster ? NOTIFICATION_MOCK_ITEMS : [];
  const totalUnread = pendingManagers.length + mockItems.length;

  type NavItemType = 'folder' | 'bell' | 'settings' | 'user';
  const navItems: {
    type: NavItemType;
    icon: React.ReactElement;
    label: string;
    hasNoti?: boolean;
  }[] = [
    { type: 'folder', icon: <Folder />, label: '출점 파이프라인' },
    { type: 'user', icon: <User />, label: '내 시뮬 이력' },
    { type: 'settings', icon: <Settings />, label: '내 정보 관리' },
    { type: 'bell', icon: <Bell />, label: '알림', hasNoti: totalUnread > 0 },
  ];

  const targetIndex = hoverIndex !== null ? hoverIndex : activeIndex;

  useEffect(() => {
    if (targetIndex !== null) {
      const el = navRefs.current[targetIndex];
      if (el) setIndicatorStyle({ left: el.offsetLeft + el.offsetWidth / 2, opacity: 1 });
    } else {
      setIndicatorStyle((prev) => ({ ...prev, opacity: 0 }));
    }
  }, [targetIndex]);

  const handleItemClick = (index: number, type: NavItemType) => {
    // 비로그인 시 로그인 페이지로
    if (!isLoggedIn) {
      nav('/login');
      return;
    }

    setActiveIndex(index);

    if (type === 'folder') {
      setOpenDropdown(null);
      nav('/hq?tab=pipeline');
    } else if (type === 'settings') {
      setOpenDropdown(null);
      nav('/hq?tab=mypage');
    } else if (type === 'bell') {
      setOpenDropdown(openDropdown === 'bell' ? null : 'bell');
    } else if (type === 'user') {
      // [UX] 드롭다운 대신 /hq 내 이력 탭으로 직행 — /simulator 헤더 "내 이력" 버튼 대체
      setOpenDropdown(null);
      nav('/hq?tab=history');
    }
  };

  return (
    <div className="relative hidden md:flex">
      {/* 아이콘 바 — overflow-hidden으로 빔 클리핑 */}
      <div
        className="relative flex items-center bg-[#2c2825] border border-[#3a3633] rounded-full h-10 px-2 shadow-sm overflow-hidden"
        onMouseLeave={() => setHoverIndex(null)}
      >
        {/* 호버 조명 효과 */}
        <div
          className="absolute top-0 z-10 pointer-events-none flex flex-col items-center transition-all duration-300 ease-[cubic-bezier(0.25,1,0.5,1)]"
          style={{
            left: `${indicatorStyle.left}px`,
            transform: 'translateX(-50%)',
            opacity: indicatorStyle.opacity,
          }}
        >
          <div className="w-6 h-[2px] bg-[#818cf8] rounded-b-full shadow-[0_0_8px_#818cf8]" />
          <div
            className="w-12 h-10 bg-[#818cf8]/20"
            style={{ clipPath: 'polygon(25% 0%, 75% 0%, 100% 100%, 0% 100%)' }}
          />
        </div>

        {/* 아이콘 리스트 */}
        {navItems.map((item, index) => (
          <button
            key={index}
            ref={(el) => {
              navRefs.current[index] = el;
            }}
            onClick={() => handleItemClick(index, item.type)}
            onMouseEnter={() => setHoverIndex(index)}
            className="relative z-20 flex items-center justify-center h-full px-3 text-[#9ca3af] hover:text-[#e2e8f0] transition-colors group"
            title={item.label}
          >
            {React.cloneElement(item.icon, {
              className: `w-4 h-4 transition-all duration-300 ${
                targetIndex === index
                  ? 'text-[#818cf8] scale-110 drop-shadow-[0_0_5px_rgba(129,140,248,0.5)]'
                  : 'scale-100 group-hover:scale-110'
              }`,
            } as React.HTMLAttributes<HTMLElement>)}

            {item.hasNoti && (
              <span className="absolute top-2 right-2 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
              </span>
            )}
          </button>
        ))}
      </div>

      {/* 드롭다운 — overflow-hidden 바깥에서 렌더링 */}

      {/* 🔔 알림 드롭다운 (Bell) — 실 승인 대기 + 도메인 특화 mock 혼합 (v11.3) */}
      {openDropdown === 'bell' && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpenDropdown(null)} />
          <div className="absolute top-12 right-0 w-80 bg-[#1e1b18] border border-[#3a3633] rounded-xl shadow-2xl py-2 z-40 animate-in fade-in slide-in-from-top-2 duration-200">
            {/* Header */}
            <div className="px-4 py-3 border-b border-[#3a3633] flex justify-between items-center bg-[#2c2825]/50">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-[#e2e8f0]">최근 알림</span>
                {totalUnread > 0 && (
                  <span className="px-1.5 py-0.5 bg-rose-500/20 text-rose-500 text-[9px] font-black rounded-full">
                    {totalUnread}
                  </span>
                )}
              </div>
              <button
                onClick={() => {
                  showToast('info', '모든 알림을 읽음 처리했습니다.');
                  setOpenDropdown(null);
                }}
                className="text-[10px] text-[#818cf8] font-bold hover:text-[#6366f1] transition-colors"
              >
                모두 읽음
              </button>
            </div>

            {/* Notification List */}
            <div className="max-h-[320px] overflow-y-auto custom-scrollbar">
              {totalUnread === 0 ? (
                <div className="px-4 py-10 text-center">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto mb-2 opacity-60" />
                  <p className="text-[11px] text-[#9ca3af]">새 알림이 없습니다</p>
                </div>
              ) : (
                <>
                  {/* 실 데이터 — 매니저 승인 대기 */}
                  {pendingManagers.map((m) => (
                    <div
                      key={m.id}
                      onClick={() => {
                        setOpenDropdown(null);
                        nav('/hq?tab=team');
                      }}
                      className="px-4 py-3 hover:bg-[#2c2825] cursor-pointer transition-colors border-b border-[#3a3633] flex gap-3 group"
                    >
                      <div className="shrink-0 mt-0.5 p-1.5 rounded-lg border bg-rose-500/10 border-rose-500/20 group-hover:border-rose-500/40 transition-colors">
                        <ShieldAlert className="w-4 h-4 text-rose-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-[#e2e8f0] leading-snug group-hover:text-white transition-colors">
                          <strong className="font-bold text-white mr-1">[권한 승인]</strong>
                          새로운 매니저 워크스페이스 승인 대기 ({m.contact_name} 님)
                        </p>
                        <p className="text-[10px] text-[#9ca3af] mt-1.5 font-mono">
                          {formatRelativeTime(m.created_at)} · {m.email}
                        </p>
                      </div>
                      <div className="shrink-0 flex items-center justify-center w-2">
                        <div className="w-1.5 h-1.5 bg-[#818cf8] rounded-full" />
                      </div>
                    </div>
                  ))}

                  {/* Mock 3종 — 법률/카니발/완료 */}
                  {mockItems.map((item) => {
                    const tag = item.title.split(']')[0] + ']';
                    const body = item.title.split(']').slice(1).join(']').trim();
                    const bgCls =
                      item.type === 'critical'
                        ? 'bg-rose-500/10 border-rose-500/20 group-hover:border-rose-500/40'
                        : item.type === 'warning'
                          ? 'bg-amber-500/10 border-amber-500/20 group-hover:border-amber-500/40'
                          : 'bg-emerald-500/10 border-emerald-500/20 group-hover:border-emerald-500/40';
                    const Icon =
                      item.iconType === 'legal'
                        ? Scale
                        : item.iconType === 'cannibal'
                          ? AlertTriangle
                          : CheckCircle2;
                    const iconColor =
                      item.type === 'critical'
                        ? 'text-rose-500'
                        : item.type === 'warning'
                          ? 'text-amber-500'
                          : 'text-emerald-500';
                    return (
                      <div
                        key={item.id}
                        onClick={() => {
                          showToast('info', item.action);
                          setOpenDropdown(null);
                        }}
                        className="px-4 py-3 hover:bg-[#2c2825] cursor-pointer transition-colors border-b border-[#3a3633] last:border-b-0 flex gap-3 group"
                      >
                        <div
                          className={`shrink-0 mt-0.5 p-1.5 rounded-lg border transition-colors ${bgCls}`}
                        >
                          <Icon className={`w-4 h-4 ${iconColor}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-[#e2e8f0] leading-snug group-hover:text-white transition-colors">
                            <strong className="font-bold text-white mr-1">{tag}</strong>
                            {body}
                          </p>
                          <p className="text-[10px] text-[#9ca3af] mt-1.5 font-mono">{item.time}</p>
                        </div>
                        <div className="shrink-0 flex items-center justify-center w-2">
                          <div className="w-1.5 h-1.5 bg-[#818cf8] rounded-full" />
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </div>

            {/* Footer */}
            <div className="p-2 border-t border-[#3a3633]">
              <button
                onClick={() => {
                  showToast('info', '전체 알림 센터는 준비 중입니다.');
                  setOpenDropdown(null);
                }}
                className="w-full py-2 text-[10px] font-bold text-[#9ca3af] hover:text-white hover:bg-[#2c2825] rounded-lg transition-colors"
              >
                알림 센터 전체 보기
              </button>
            </div>
          </div>
        </>
      )}

      {/*
        User 드롭다운 제거됨 — User 아이콘이 `/hq?tab=history` 로 직행으로 바뀌면서
        openDropdown==='user' 조건이 트리거되지 않음.
        팀/결제 관리는 /hq 사이드바 메뉴에서, 로그아웃은 글로벌 헤더 LogoutButton 에서 접근.
      */}
    </div>
  );
}

export default GlobalLimelightNav;
