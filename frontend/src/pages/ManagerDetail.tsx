import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Mail, Phone, MapPin, User as UserIcon } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { HistoryList } from '../components/SimulationHistory/HistoryList';

type TabKey = 'info' | 'districts' | 'history' | 'activity';

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'info', label: '기본 정보' },
  { key: 'districts', label: '담당 권역' },
  { key: 'history', label: '시뮬 이력' },
  { key: 'activity', label: '활동 로그' },
];

export default function ManagerDetail() {
  const { id: routeId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, isLoggedIn } = useAuth();
  const [tab, setTab] = useState<TabKey>('history');

  // 접근 제어:
  // 1) 비로그인 → /login으로 돌림 (ProtectedRoute 이미 돌리지만 안전망)
  // 2) 매니저가 자기 ID가 아닌 경로 접근 → 403
  // 3) master(팀장/HQ)가 하위 매니저 열람 → Phase 2 (현재는 기본 정보만, history 탭은 Phase 2 안내)
  const isSelf = !!user && user.id === routeId;
  const isMaster = user?.role === 'master';

  if (!isLoggedIn) {
    return <div className="p-10 text-center text-sm text-stone-400">로그인이 필요합니다.</div>;
  }

  if (!routeId) {
    return <div className="p-10 text-center text-sm text-rose-400">잘못된 경로입니다.</div>;
  }

  if (!isSelf && !isMaster) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 p-10 text-center">
        <div className="text-lg font-semibold text-rose-400">접근 권한이 없습니다</div>
        <div className="text-sm text-stone-400">본인 프로필만 조회할 수 있습니다.</div>
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mt-2 rounded-md border border-stone-700 bg-stone-800 px-4 py-2 text-sm text-stone-200 hover:bg-stone-700"
        >
          돌아가기
        </button>
      </div>
    );
  }

  // Phase 1: master가 다른 매니저 페이지 보면 history 탭 비활성
  const historyAvailable = isSelf;

  return (
    <div className="min-h-screen bg-card pb-16 text-stone-100">
      <div className="mx-auto max-w-5xl px-6 pt-20">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-4 inline-flex items-center gap-1 text-xs text-stone-400 hover:text-stone-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          돌아가기
        </button>

        <Header routeId={routeId} isSelf={isSelf} />

        <div className="mt-6 flex gap-1 border-b border-stone-700">
          {TABS.map((t) => {
            const disabled = t.key === 'history' && !historyAvailable;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                type="button"
                disabled={disabled}
                onClick={() => setTab(t.key)}
                className={`border-b-2 px-4 py-2 text-sm font-semibold transition-colors ${
                  active
                    ? 'border-warning text-warning'
                    : 'border-transparent text-stone-400 hover:text-stone-100'
                } ${disabled ? 'cursor-not-allowed opacity-40 hover:text-stone-400' : ''}`}
                title={disabled ? '하위 매니저 이력 조회는 Phase 2에서 제공됩니다' : undefined}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        <div className="mt-6">
          {tab === 'info' && <BasicInfo isSelf={isSelf} />}
          {tab === 'districts' && <AssignedDistricts isSelf={isSelf} />}
          {tab === 'history' && historyAvailable && <HistoryList />}
          {tab === 'history' && !historyAvailable && <Phase2Notice label="시뮬 이력" />}
          {tab === 'activity' && <Phase2Notice label="활동 로그" />}
        </div>
      </div>
    </div>
  );
}

function Header({ routeId, isSelf }: { routeId: string; isSelf: boolean }) {
  const { user } = useAuth();
  const viewing = isSelf ? user : null;
  const displayName = viewing?.contact_name ?? (isSelf ? '나' : `매니저 ${routeId.slice(0, 8)}`);

  return (
    <div className="flex items-center gap-4 rounded-lg border border-stone-700 bg-stone-800 p-5">
      <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-warning/20 text-2xl">
        <UserIcon className="h-7 w-7 text-warning" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold text-stone-100">{displayName}</h1>
          {isSelf && (
            <span className="rounded bg-warning/15 px-2 py-0.5 text-[0.625rem] font-bold text-warning">
              본인
            </span>
          )}
          {!isSelf && (
            <span className="rounded bg-stone-700 px-2 py-0.5 text-[0.625rem] font-mono text-stone-300">
              {routeId.slice(0, 8)}
            </span>
          )}
        </div>
        {viewing && (
          <div className="mt-1 flex items-center gap-3 text-xs text-stone-400">
            <span className="flex items-center gap-1">
              <Mail className="h-3 w-3" />
              {viewing.email}
            </span>
            {viewing.phone && (
              <span className="flex items-center gap-1">
                <Phone className="h-3 w-3" />
                {viewing.phone}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function BasicInfo({ isSelf }: { isSelf: boolean }) {
  const { user } = useAuth();
  if (!isSelf || !user) {
    return <Phase2Notice label="매니저 기본 정보" />;
  }
  return (
    <div className="rounded-lg border border-stone-700 bg-stone-800 p-6">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <Field label="이름" value={user.contact_name ?? '—'} />
        <Field label="이메일" value={user.email ?? '—'} />
        <Field label="연락처" value={user.phone ?? '—'} />
        <Field label="직책" value={user.position ?? '—'} />
        <Field label="역할" value={user.role === 'master' ? '팀장/HQ' : '매니저'} />
        <Field label="소속 기업" value={user.company_name ?? '—'} />
      </div>
    </div>
  );
}

function AssignedDistricts({ isSelf }: { isSelf: boolean }) {
  const { user } = useAuth();
  // assigned_gu/assigned_dongs는 manager_users 테이블에 저장되지만
  // AuthContext User 타입엔 노출돼있지 않음. Phase 2에서 확장 예정.
  const rawUser = (user ?? {}) as Record<string, unknown>;
  const assignedGu = typeof rawUser.assigned_gu === 'string' ? rawUser.assigned_gu : null;
  const assignedDongs = Array.isArray(rawUser.assigned_dongs)
    ? (rawUser.assigned_dongs as string[])
    : [];

  if (!isSelf) return <Phase2Notice label="담당 권역" />;

  return (
    <div className="rounded-lg border border-stone-700 bg-stone-800 p-6">
      <Field label="담당 구" value={assignedGu ?? '미배정'} />
      <div className="mt-4">
        <div className="text-xs uppercase tracking-widest text-stone-400">담당 행정동</div>
        {assignedDongs.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {assignedDongs.map((d) => (
              <span
                key={d}
                className="inline-flex items-center gap-1 rounded-md border border-warning/40 bg-warning/10 px-2 py-1 text-xs text-warning"
              >
                <MapPin className="h-3 w-3" />
                {d}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-stone-500">
            배정된 동이 없습니다. 팀장에게 권역 할당을 요청하세요.
          </p>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[0.625rem] uppercase tracking-widest text-stone-500">{label}</div>
      <div className="mt-0.5 text-stone-100">{value}</div>
    </div>
  );
}

function Phase2Notice({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-dashed border-stone-700 bg-stone-900/40 p-10 text-center">
      <div className="text-sm font-semibold text-stone-300">{label}</div>
      <div className="mt-1 text-xs text-stone-500">Phase 2 제공 예정</div>
    </div>
  );
}
