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

import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useToast } from "../components/Toast";
import {
  Building2,
  Users,
  LayoutTemplate,
  SlidersHorizontal,
  CreditCard,
  Search,
  Plus,
  MapPin,
  MoreVertical,
  CheckCircle2,
  XCircle,
  BarChart3,
  Crosshair,
  Shield,
  Zap,
  TrendingUp,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════ */
type MenuId = "team" | "pipeline" | "tuning" | "billing";

/* ═══════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════ */
export default function HQCommandCenter() {
  const [searchParams] = useSearchParams();
  const tabFromUrl = searchParams.get("tab") as MenuId | null;
  const [activeMenu, setActiveMenu] = useState<MenuId>(tabFromUrl || "team");
  const { showToast } = useToast();

  // URL ?tab= 파라미터 변경 시 탭 동기화
  useEffect(() => {
    if (tabFromUrl && ["team", "pipeline", "tuning", "billing"].includes(tabFromUrl)) {
      setActiveMenu(tabFromUrl);
    }
  }, [tabFromUrl]);

  return (
    <div className="absolute inset-0 z-20 flex bg-[#1e1b18] text-[#e2e8f0] font-sans overflow-hidden select-none">
      {/* ==========================================
          좌측 사이드바 (LNB)
          ========================================== */}
      <div className="w-64 bg-[#2c2825] border-r border-[#3a3633] flex flex-col z-20 shrink-0">
        {/* 워크스페이스 로고 영역 */}
        <div className="h-20 flex items-center px-6 border-b border-[#3a3633] gap-3 cursor-pointer group mt-24">
          <div className="w-8 h-8 rounded-lg bg-[#818cf8]/20 border border-[#818cf8]/50 flex items-center justify-center">
            <Building2 className="w-4 h-4 text-[#818cf8]" />
          </div>
          <div className="flex flex-col">
            <span className="font-black text-sm tracking-widest text-[#e2e8f0] group-hover:text-[#818cf8] transition-colors">
              SPOTTER-HQ
            </span>
            <span className="text-[10px] text-[#9ca3af]">
              (주) 제네시스 BBQ 본사
            </span>
          </div>
        </div>

        {/* 메뉴 리스트 */}
        <div className="flex-1 overflow-y-auto py-6 px-4 flex flex-col gap-2">
          <p className="px-2 text-[10px] font-bold text-[#9ca3af] mb-2 tracking-widest">
            COMMAND CENTER
          </p>

          <MenuButton
            active={activeMenu === "team"}
            onClick={() => setActiveMenu("team")}
            icon={<Users className="w-4 h-4" />}
            label="팀 및 권역 관리"
            badge="1"
          />
          <MenuButton
            active={activeMenu === "pipeline"}
            onClick={() => setActiveMenu("pipeline")}
            icon={<LayoutTemplate className="w-4 h-4" />}
            label="출점 파이프라인"
          />
          <MenuButton
            active={activeMenu === "tuning"}
            onClick={() => setActiveMenu("tuning")}
            icon={<SlidersHorizontal className="w-4 h-4" />}
            label="브랜드 AI 튜닝"
          />

          <p className="px-2 text-[10px] font-bold text-[#9ca3af] mt-6 mb-2 tracking-widest">
            SETTINGS
          </p>
          <MenuButton
            active={activeMenu === "billing"}
            onClick={() => setActiveMenu("billing")}
            icon={<CreditCard className="w-4 h-4" />}
            label="결제 및 API 토큰"
          />
        </div>

        {/* 하단 유저 프로필 */}
        <div className="p-4 border-t border-[#3a3633]">
          <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-[#1e1b18] cursor-pointer transition-colors">
            <div className="w-8 h-8 rounded-full bg-[#3a3633] flex items-center justify-center">
              <Shield className="w-4 h-4 text-[#9ca3af]" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold">마스터 계정 (팀장)</span>
              <span className="text-[10px] text-[#818cf8]">
                Pro Plan · 340 Tokens
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
            {activeMenu === "team" && "팀 및 권역 관리"}
            {activeMenu === "pipeline" && "출점 파이프라인 보드"}
            {activeMenu === "tuning" && "자사 브랜드 AI 튜닝 (Master Data)"}
            {activeMenu === "billing" && "결제 및 API 토큰 관리"}
          </h2>

          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca3af]" />
              <input
                type="text"
                placeholder="검색..."
                className="w-64 h-9 bg-[#2c2825] border border-[#3a3633] rounded-full pl-9 pr-4 text-xs focus:outline-none focus:border-[#818cf8] transition-colors text-[#e2e8f0] placeholder-[#9ca3af]"
              />
            </div>
            <button
              onClick={() => {
                if (activeMenu === "team") {
                  navigator.clipboard.writeText("SPOTTER-HQ-2026");
                  showToast("success", "초대 코드가 복사되었습니다: SPOTTER-HQ-2026");
                } else {
                  showToast("info", "해당 기능은 정식 서비스에서 제공됩니다.");
                }
              }}
              className="h-9 px-4 bg-[#818cf8] hover:bg-[#6366f1] text-[#1e1b18] text-xs font-bold rounded-full transition-colors flex items-center gap-2 shadow-[0_0_15px_rgba(129,140,248,0.3)]"
            >
              <Plus className="w-4 h-4" />
              {activeMenu === "team"
                ? "매니저 초대"
                : activeMenu === "pipeline"
                ? "새 시뮬레이션"
                : "저장"}
            </button>
          </div>
        </header>

        {/* 렌더링 영역 */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-8">
          <div className="max-w-[1920px] w-full mx-auto xl:px-10 2xl:px-16">
            {activeMenu === "team" && <TeamManagementView />}
            {activeMenu === "pipeline" && <PipelineKanbanView />}
            {activeMenu === "tuning" && <BrandTuningView />}
            {activeMenu === "billing" && <BillingManagementView />}
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
          ? "bg-[#818cf8]/10 text-[#818cf8]"
          : "text-[#9ca3af] hover:bg-[#3a3633]/30 hover:text-[#e2e8f0]"
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
// 구 → 동 매핑 (mock, 주요 동만)
const REGION_DATA: Record<string, string[]> = {
  "마포구": ["연남동", "서교동", "합정동", "망원동", "상암동", "성산동", "연희동"],
  "서초구": ["서초동", "반포동", "잠원동", "방배동", "양재동", "내곡동"],
  "강남구": ["역삼동", "삼성동", "청담동", "신사동", "논현동", "대치동", "개포동"],
  "서대문구": ["신촌동", "창천동", "연희동", "홍제동", "남가좌동", "북가좌동"],
  "영등포구": ["여의도동", "당산동", "영등포동", "문래동", "양평동", "신길동"],
  "송파구": ["잠실동", "석촌동", "송파동", "방이동", "가락동", "문정동"],
};

function TeamManagementView() {
  const { showToast } = useToast();
  const [pendingGu, setPendingGu] = useState("");
  const [pendingDongs, setPendingDongs] = useState<string[]>([]);

  const toggleDong = (dong: string) => {
    setPendingDongs((prev) =>
      prev.includes(dong) ? prev.filter((d) => d !== dong) : [...prev, dong]
    );
  };

  return (
    <div className="flex flex-col gap-8">
      {/* 1. 승인 대기 (Pending Approval) */}
      <section>
        <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          승인 대기 중인 매니저 (1)
        </h3>
        <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl p-5 shadow-lg shadow-rose-500/5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-[#1e1b18] border border-[#3a3633] flex items-center justify-center font-bold text-[#9ca3af]">
                최
              </div>
              <div>
                <p className="text-sm font-bold text-[#e2e8f0]">최점포 매니저</p>
                <p className="text-xs text-[#9ca3af]">초대 코드 입력 완료 (10분 전)</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => showToast("success", "매니저 승인 기능은 정식 서비스에서 제공됩니다.")} className="p-2 bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500 hover:text-white rounded-lg transition-colors border border-emerald-500/20">
                <CheckCircle2 className="w-5 h-5" />
              </button>
              <button onClick={() => showToast("info", "매니저 거절 기능은 정식 서비스에서 제공됩니다.")} className="p-2 bg-rose-500/10 text-rose-500 hover:bg-rose-500 hover:text-white rounded-lg transition-colors border border-rose-500/20">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* 구 → 동 선택 */}
          <div className="bg-[#1e1b18] border border-[#3a3633] rounded-lg p-4">
            <p className="text-[10px] text-[#9ca3af] uppercase tracking-wider font-bold mb-3">담당 권역 할당</p>
            <select
              value={pendingGu}
              onChange={(e) => { setPendingGu(e.target.value); setPendingDongs([]); }}
              className="w-full bg-[#2c2825] border border-[#3a3633] rounded-lg text-xs px-3 py-2.5 text-[#e2e8f0] outline-none focus:border-[#818cf8] transition-colors mb-3"
            >
              <option value="">구 선택...</option>
              {Object.keys(REGION_DATA).map((gu) => (
                <option key={gu} value={gu}>{gu}</option>
              ))}
            </select>

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
                            ? "bg-[#818cf8]/15 border-[#818cf8] text-[#818cf8]"
                            : "bg-transparent border-[#3a3633] text-[#9ca3af] hover:border-[#818cf8]/50 hover:text-[#e2e8f0]"
                        }`}
                      >
                        {dong}
                      </button>
                    );
                  })}
                </div>
                {pendingDongs.length > 0 && (
                  <p className="text-[10px] text-[#818cf8] mt-2 font-mono">
                    {pendingDongs.length}개 동 선택됨: {pendingDongs.join(", ")}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 2. 활성 멤버 리스트 */}
      <section>
        <h3 className="text-sm font-bold mb-4 text-[#9ca3af]">
          활성 워크스페이스 멤버
        </h3>
        <div className="bg-[#2c2825] border border-[#3a3633] rounded-xl overflow-hidden shadow-lg">
          <table className="w-full text-left border-collapse">
            <thead className="bg-[#1e1b18]/50 border-b border-[#3a3633] text-xs font-mono text-[#9ca3af] uppercase tracking-wider">
              <tr>
                <th className="p-4 font-medium">이름 / 직급</th>
                <th className="p-4 font-medium">담당 권역</th>
                <th className="p-4 font-medium">최근 활동</th>
                <th className="p-4 font-medium">상태</th>
                <th className="p-4 font-medium text-right">관리</th>
              </tr>
            </thead>
            <tbody className="text-sm divide-y divide-[#3a3633]">
              <tr className="hover:bg-[#1e1b18]/50 transition-colors">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#818cf8]/20 flex items-center justify-center text-[#818cf8] font-bold text-xs">
                      김
                    </div>
                    <div>
                      <p className="font-bold text-[#e2e8f0]">
                        김마포 매니저
                      </p>
                      <p className="text-[10px] text-[#9ca3af]">
                        Regional Manager
                      </p>
                    </div>
                  </div>
                </td>
                <td className="p-4">
                  <div className="flex flex-wrap gap-1">
                    <span className="px-2 py-0.5 bg-[#818cf8]/10 text-[#818cf8] border border-[#818cf8]/20 rounded-md text-[10px] font-bold inline-flex items-center gap-1">
                      <MapPin className="w-3 h-3" /> 연남동
                    </span>
                    <span className="px-2 py-0.5 bg-[#818cf8]/10 text-[#818cf8] border border-[#818cf8]/20 rounded-md text-[10px] font-bold">
                      서교동
                    </span>
                    <span className="px-2 py-0.5 bg-[#818cf8]/10 text-[#818cf8] border border-[#818cf8]/20 rounded-md text-[10px] font-bold">
                      합정동
                    </span>
                  </div>
                </td>
                <td className="p-4 text-xs text-[#9ca3af]">
                  연남동 시뮬레이션 저장 (2시간 전)
                </td>
                <td className="p-4">
                  <span className="flex items-center gap-1.5 text-xs text-emerald-500 font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />{" "}
                    Online
                  </span>
                </td>
                <td className="p-4 text-right">
                  <button onClick={() => showToast("info", "멤버 관리 기능은 정식 서비스에서 제공됩니다.")} className="text-[#9ca3af] hover:text-[#818cf8] transition-colors">
                    <MoreVertical className="w-5 h-5 ml-auto" />
                  </button>
                </td>
              </tr>
              <tr className="hover:bg-[#1e1b18]/50 transition-colors">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#3a3633] flex items-center justify-center text-[#9ca3af] font-bold text-xs">
                      이
                    </div>
                    <div>
                      <p className="font-bold text-[#e2e8f0]">
                        이서초 매니저
                      </p>
                      <p className="text-[10px] text-[#9ca3af]">
                        Regional Manager
                      </p>
                    </div>
                  </div>
                </td>
                <td className="p-4">
                  <div className="flex flex-wrap gap-1">
                    <span className="px-2 py-0.5 bg-[#3a3633]/50 text-[#9ca3af] border border-[#3a3633] rounded-md text-[10px] font-bold inline-flex items-center gap-1">
                      <MapPin className="w-3 h-3" /> 서초동
                    </span>
                    <span className="px-2 py-0.5 bg-[#3a3633]/50 text-[#9ca3af] border border-[#3a3633] rounded-md text-[10px] font-bold">
                      반포동
                    </span>
                  </div>
                </td>
                <td className="p-4 text-xs text-[#9ca3af]">
                  서초4동 리포트 공유 (어제)
                </td>
                <td className="p-4">
                  <span className="flex items-center gap-1.5 text-xs text-[#9ca3af]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#404040]" />{" "}
                    Offline
                  </span>
                </td>
                <td className="p-4 text-right">
                  <button onClick={() => showToast("info", "멤버 관리 기능은 정식 서비스에서 제공됩니다.")} className="text-[#9ca3af] hover:text-[#818cf8] transition-colors">
                    <MoreVertical className="w-5 h-5 ml-auto" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   View 2: Pipeline Kanban Board (출점 파이프라인)
   ═══════════════════════════════════════════════════════ */
function PipelineKanbanView() {
  const columns = [
    {
      title: "상권 분석 중",
      count: 2,
      borderColor: "border-[#3a3633]",
      titleColor: "text-[#9ca3af]",
    },
    {
      title: "임원 보고 대기",
      count: 1,
      borderColor: "border-amber-500/50",
      titleColor: "text-amber-500",
    },
    {
      title: "가맹점주 제안",
      count: 1,
      borderColor: "border-[#818cf8]/50",
      titleColor: "text-[#818cf8]",
    },
    {
      title: "출점 확정",
      count: 0,
      borderColor: "border-emerald-500/50",
      titleColor: "text-emerald-500",
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
            <h4
              className={`text-xs font-bold uppercase tracking-wider ${col.titleColor}`}
            >
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
                <span className="text-xs font-mono text-[#9ca3af]">
                  Drag & Drop
                </span>
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
    <div onClick={() => showToast("info", "칸반 상태 변경은 정식 버전에서 지원됩니다.")} className="bg-[#1e1b18] border border-[#3a3633] rounded-xl p-4 cursor-grab hover:border-[#818cf8]/50 transition-colors shadow-md group">
      <div className="flex justify-between items-start mb-3">
        <div>
          <span className="text-[10px] font-mono text-[#9ca3af]">{date}</span>
          <h5 className="font-bold text-sm text-[#e2e8f0] group-hover:text-[#818cf8] transition-colors">
            {district} 후보지
          </h5>
        </div>
        <div
          className="w-6 h-6 rounded-full bg-[#2c2825] flex items-center justify-center text-[8px] font-bold text-[#9ca3af] border border-[#3a3633]"
          title={manager}
        >
          {manager[0]}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="bg-[#2c2825] rounded-lg p-2 border border-[#3a3633] flex flex-col items-center justify-center text-center">
          <span className="text-[9px] text-[#9ca3af] block mb-0.5">
            예상 매출
          </span>
          <span className="text-xs font-black text-white flex items-center gap-1">
            <BarChart3 className="w-3 h-3 text-emerald-500" /> {revenue}
          </span>
        </div>
        <div className="bg-[#2c2825] rounded-lg p-2 border border-[#3a3633] flex flex-col items-center justify-center text-center">
          <span className="text-[9px] text-[#9ca3af] block mb-0.5">
            AI 매력도
          </span>
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
            우리 프랜차이즈의 특성을 입력하면, AI 예측 모델이 이를 반영하여
            맞춤형 예상 매출과 리스크를 산출합니다.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* 객단가 (AOV) 설정 */}
            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-[#e2e8f0]">
                예상 평균 객단가 (AOV)
              </label>
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
                <option value="2030f">
                  2030 여성 (트렌드/디저트)
                </option>
                <option value="2030m">
                  2030 남성/여성 (가성비/식사)
                </option>
                <option value="3040">3040 직장인 (회식/저녁)</option>
                <option value="family">
                  주거 배후세대 (가족/배달)
                </option>
              </select>
              <p className="text-[10px] text-[#9ca3af]">
                선택한 타겟층의 해당 상권 거주/유동 비율을 우선 분석합니다.
              </p>
            </div>

            {/* 배달 vs 홀 비중 슬라이더 */}
            <div className="flex flex-col gap-4 md:col-span-2 mt-4 p-5 bg-[#1e1b18] border border-[#3a3633] rounded-xl">
              <div className="flex justify-between items-center">
                <label className="text-xs font-bold text-[#e2e8f0]">
                  매출 비중 (홀 vs 배달)
                </label>
                <span className="text-xs font-mono font-bold text-[#818cf8]">
                  홀 30% : 배달 70%
                </span>
              </div>

              <div className="relative w-full h-3 bg-[#3a3633] rounded-full overflow-hidden flex cursor-pointer">
                <div
                  className="h-full bg-[#3a3633]"
                  style={{ width: "30%" }}
                />
                <div
                  className="h-full bg-[#818cf8]"
                  style={{ width: "70%" }}
                />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white rounded-full shadow-lg border-2 border-[#818cf8] transition-transform hover:scale-110"
                  style={{ left: "calc(30% - 10px)" }}
                />
              </div>

              <div className="flex justify-between text-[10px] font-bold text-[#9ca3af]">
                <span>Dine-in (입지/접근성 가중치 상승)</span>
                <span>Delivery (배후세대 가중치 상승)</span>
              </div>
            </div>
          </div>

          <div className="mt-8 flex justify-end">
            <button onClick={() => showToast("info", "AI 모델 가중치 업데이트 기능은 준비 중입니다.")} className="px-6 py-2.5 bg-[#818cf8] text-[#1e1b18] text-sm font-bold rounded-lg shadow-[0_0_20px_rgba(129,140,248,0.4)] hover:bg-[#6366f1] transition-colors">
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
  const currentPlan = "Growth";
  const billingCycle = "2026. 04. 10 ~ 2026. 05. 09";
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
        <div className="bg-[#2c2825] border border-[#3a3633] rounded-2xl p-6 shadow-lg flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-[#818cf8]/10 blur-[40px] rounded-full pointer-events-none" />
          <div>
            <h3 className="text-[#9ca3af] text-xs font-bold uppercase tracking-widest mb-1">Current Plan</h3>
            <div className="flex items-end gap-3 mb-4">
              <h2 className="text-3xl font-black text-white">{currentPlan}</h2>
              <span className="px-2 py-1 bg-[#818cf8]/20 text-[#818cf8] border border-[#818cf8]/30 rounded-md text-[10px] font-bold mb-1">Active</span>
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
          <button onClick={() => showToast("info", "결제 및 플랜 변경은 정식 오픈 후 지원됩니다.")} className="w-full mt-6 py-2.5 bg-[#1e1b18] hover:bg-[#3a3633] border border-[#3a3633] text-[#e2e8f0] text-xs font-bold rounded-lg transition-colors">
            결제 수단 관리 / 영수증
          </button>
        </div>

        {/* API 토큰 사용량 */}
        <div className="lg:col-span-2 bg-[#2c2825] border border-[#3a3633] rounded-2xl p-6 shadow-lg flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-start mb-6">
              <div>
                <h3 className="text-[#9ca3af] text-xs font-bold uppercase tracking-widest mb-1">API Tokens Usage</h3>
                <h2 className="text-2xl font-black text-white">
                  {usedTokens.toLocaleString()}{" "}
                  <span className="text-lg text-[#9ca3af] font-medium">/ {totalTokens.toLocaleString()}</span>
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
              <span className="text-[10px] text-[#818cf8] font-bold">{progressPercent.toFixed(1)}% Used</span>
              <span className="text-[10px] text-[#9ca3af]">{remainTokens.toLocaleString()} Tokens Left</span>
            </div>
          </div>

          <div className="mt-8 p-4 bg-[#1e1b18] border border-[#3a3633] rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#818cf8]/10 flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-[#818cf8]" />
              </div>
              <div>
                <p className="text-xs font-bold text-white">토큰이 부족하신가요?</p>
                <p className="text-[10px] text-[#9ca3af]">플랜을 업그레이드하거나 일회성 토큰을 충전하세요.</p>
              </div>
            </div>
            <button onClick={() => showToast("info", "토큰 충전은 정식 오픈 후 지원됩니다.")} className="px-4 py-2 bg-[#818cf8] hover:bg-[#6366f1] text-[#1e1b18] text-xs font-bold rounded-lg shadow-[0_0_15px_rgba(129,140,248,0.3)] transition-colors">
              즉시 충전하기
            </button>
          </div>
        </div>
      </section>

      {/* 2. Plan Upgrade (Pricing Cards) */}
      <section className="mt-4">
        <h3 className="text-sm font-bold text-[#e2e8f0] mb-4">플랜 업그레이드</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { id: "Starter", price: "₩49,000", tokens: "100 Tokens/mo", target: "소규모 점포개발팀" },
            { id: "Growth", price: "₩149,000", tokens: "1,000 Tokens/mo", target: "중견 프랜차이즈 본사", isPopular: true },
            { id: "Enterprise", price: "Custom", tokens: "Unlimited Tokens", target: "대형 프랜차이즈 및 컨설팅사" },
          ].map((plan) => (
            <div
              key={plan.id}
              className="group relative w-full rounded-2xl overflow-hidden p-[2px] transition-transform duration-500 ease-out hover:-translate-y-2"
            >
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                style={{
                  background:
                    "conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)",
                }}
              />
              <div className="relative z-10 h-full w-full bg-[#2c2825] rounded-[14px] flex flex-col p-6 transition-colors duration-500 border border-[#3a3633] group-hover:border-transparent">
                {plan.isPopular && (
                  <div className="absolute top-4 right-4 px-2.5 py-0.5 bg-[#3a3633] border border-[#818cf8]/30 rounded-full">
                    <span className="text-[9px] font-bold text-[#818cf8] tracking-wider">MOST POPULAR</span>
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
                    <button onClick={() => showToast("info", "결제 및 플랜 변경은 정식 오픈 후 지원됩니다.")} className="w-full py-3 bg-[#1e1b18] text-[#9ca3af] border border-[#3a3633] text-xs font-bold rounded-xl group-hover:bg-[#818cf8] group-hover:text-[#1e1b18] group-hover:border-transparent transition-all duration-300 shadow-[0_0_20px_rgba(129,140,248,0)] group-hover:shadow-[0_0_20px_rgba(129,140,248,0.4)]">
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
