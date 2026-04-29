/**
 * TokenBurnrateSection — LLM 토큰 번레이트 대시보드 (리서치 #7)
 *
 * LangSmith 실데이터 기반 (backend /api/ops/token-usage endpoint 대기).
 * 백엔드 미구현(404) 시 empty state + B1 예진 연동 대기 안내.
 *
 * 표시:
 * - 총 소진 / 비용 / run 수 (KPI 3카드)
 * - 일별 토큰 번다운 바 (최근 기간)
 * - 매니저별 소진 랭킹
 * - 모델별 breakdown (Opus / Sonnet / Haiku 등)
 */

import { useMemo } from 'react';
import { AlertCircle, Activity, DollarSign, Zap, Users, Cpu } from 'lucide-react';
import { useTokenUsage } from '../../hooks/useTokenUsage';

function defaultRange30d(): { from: string; to: string } {
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const today = new Date();
  const start = new Date(today);
  start.setDate(start.getDate() - 29);
  return { from: iso(start), to: iso(today) };
}

function formatInt(n: number): string {
  return n.toLocaleString('en-US');
}

function formatUsd(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}k`;
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(4)}`;
}

export function TokenBurnrateSection() {
  const range = useMemo(() => defaultRange30d(), []);
  const { data, isLoading, notImplemented, error } = useTokenUsage(range);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-stone-800 bg-[#2c2825] p-6">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="h-4 w-4 text-[#818cf8]" />
          <h3 className="text-sm font-bold text-[#e2e8f0]">LLM 토큰 번레이트</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-stone-900/40" />
          ))}
        </div>
      </div>
    );
  }

  if (notImplemented) {
    return (
      <div className="rounded-2xl border border-dashed border-amber-500/30 bg-amber-500/5 p-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-amber-400 mt-0.5" />
          <div className="flex-1">
            <h3 className="text-sm font-bold text-amber-300 mb-1">
              LLM 토큰 번레이트 — 백엔드 연동 대기
            </h3>
            <p className="text-xs text-amber-200/80 leading-relaxed mb-3">
              LangSmith API 키는 백엔드 <code className="font-mono">.env</code>에 있고, 프론트는
              <code className="font-mono"> /api/ops/token-usage</code> 엔드포인트를 호출하도록 이미
              준비되어 있습니다. B1(예진)이 엔드포인트를 추가하면 이 섹션은 자동으로 활성화됩니다.
            </p>
            <details className="mt-2">
              <summary className="cursor-pointer text-[0.6875rem] font-bold text-amber-300 hover:text-amber-200">
                응답 스키마 (B1 참고)
              </summary>
              <pre className="mt-2 rounded-md bg-[#1e1b18] p-3 text-[0.625rem] leading-relaxed text-stone-400 overflow-x-auto">{`GET /api/ops/token-usage?from=YYYY-MM-DD&to=YYYY-MM-DD
Authorization: Bearer <JWT>

{
  "period": { "from": "...", "to": "..." },
  "total_tokens": 0,
  "total_cost_usd": 0,
  "total_runs": 0,
  "daily": [{ "date": "...", "tokens": 0, "cost_usd": 0, "run_count": 0 }],
  "by_manager": [{ "manager_id": "uuid", "manager_name": "...", "tokens": 0, "cost_usd": 0, "run_count": 0 }],
  "by_model": [{ "model": "claude-opus-4-7", "tokens": 0, "cost_usd": 0, "run_count": 0 }],
  "langsmith_project": "mapo-franchise-simulator",
  "fetched_at": "ISO datetime"
}

# 구현 힌트: LangSmith SDK의 Client.list_runs(project_name=..., start_time=...) 사용.
# metadata.manager_id 필터링은 synthesis/agents에서 with_config(metadata={"manager_id": ...}) 주입 필요.`}</pre>
            </details>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-6 text-xs text-rose-300">
        <div className="flex items-center gap-2 mb-1">
          <AlertCircle className="h-4 w-4" />
          <span className="font-bold">토큰 사용량 조회 실패</span>
        </div>
        <p className="text-rose-300/80">{error ?? '알 수 없는 오류'}</p>
      </div>
    );
  }

  const maxDaily = Math.max(1, ...data.daily.map((d) => d.tokens));
  const topManagers = [...data.by_manager].sort((a, b) => b.tokens - a.tokens).slice(0, 5);
  const totalManagerTokens = topManagers.reduce((s, m) => s + m.tokens, 0) || 1;

  return (
    <div className="flex flex-col gap-6">
      {/* KPI 3카드 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <KpiCard
          label="총 토큰 소진"
          value={formatInt(data.total_tokens)}
          sub={`${data.total_runs.toLocaleString()} runs`}
          icon={<Activity className="h-4 w-4 text-[#818cf8]" />}
        />
        <KpiCard
          label="총 비용"
          value={formatUsd(data.total_cost_usd)}
          sub={`${data.period.from} ~ ${data.period.to}`}
          icon={<DollarSign className="h-4 w-4 text-emerald-400" />}
        />
        <KpiCard
          label="LangSmith Project"
          value={data.langsmith_project ?? '—'}
          sub={`fetched ${new Date(data.fetched_at).toLocaleTimeString('ko-KR')}`}
          icon={<Zap className="h-4 w-4 text-amber-400" />}
          mono
        />
      </div>

      {/* 일별 번레이트 바 */}
      <div className="rounded-2xl border border-stone-800 bg-[#2c2825] p-5">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
            일별 토큰 소진
          </span>
          <span className="text-[0.625rem] text-stone-600">peak {formatInt(maxDaily)} tokens/day</span>
        </div>
        {data.daily.length === 0 ? (
          <div className="py-8 text-center text-xs text-stone-500">해당 기간 기록 없음</div>
        ) : (
          <div className="flex h-24 items-end gap-0.5">
            {data.daily.map((d) => {
              const pct = (d.tokens / maxDaily) * 100;
              return (
                <div
                  key={d.date}
                  className="flex flex-1 flex-col justify-end"
                  title={`${d.date}: ${formatInt(d.tokens)} tokens · ${formatUsd(d.cost_usd)}`}
                >
                  <div
                    className="w-full rounded-t bg-gradient-to-t from-[#6366f1] to-[#818cf8] transition-all"
                    style={{ height: `${pct}%`, minHeight: d.tokens > 0 ? '2px' : '0' }}
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 매니저별 Top 5 */}
        <div className="rounded-2xl border border-stone-800 bg-[#2c2825] p-5">
          <div className="mb-3 flex items-center gap-2">
            <Users className="h-4 w-4 text-[#818cf8]" />
            <span className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
              매니저별 Top 5
            </span>
          </div>
          {topManagers.length === 0 ? (
            <span className="text-xs text-stone-500">데이터 없음</span>
          ) : (
            <div className="space-y-2">
              {topManagers.map((m, i) => {
                const pct = (m.tokens / totalManagerTokens) * 100;
                return (
                  <div key={m.manager_id} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between text-[0.6875rem]">
                      <span className="flex items-center gap-2 text-stone-300">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-stone-800 text-[0.5625rem] font-mono text-stone-400">
                          {i + 1}
                        </span>
                        <span className="truncate">
                          {m.manager_name ?? m.manager_id.slice(0, 8)}
                        </span>
                      </span>
                      <span className="font-mono tabular-nums text-indigo-400">
                        {formatInt(m.tokens)}
                      </span>
                    </div>
                    <div className="h-1 w-full rounded bg-stone-900 overflow-hidden">
                      <div
                        className="h-full bg-[#818cf8] transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 모델별 */}
        <div className="rounded-2xl border border-stone-800 bg-[#2c2825] p-5">
          <div className="mb-3 flex items-center gap-2">
            <Cpu className="h-4 w-4 text-[#818cf8]" />
            <span className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
              모델별 소진
            </span>
          </div>
          {data.by_model.length === 0 ? (
            <span className="text-xs text-stone-500">데이터 없음</span>
          ) : (
            <div className="space-y-2">
              {data.by_model.map((m) => (
                <div
                  key={m.model}
                  className="flex items-center justify-between border-b border-stone-800/60 pb-2 last:border-0"
                >
                  <div className="flex flex-col">
                    <span className="font-mono text-[0.6875rem] text-stone-300">{m.model}</span>
                    <span className="text-[0.5625rem] text-stone-500">
                      {m.run_count.toLocaleString()} runs
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-[0.6875rem] tabular-nums text-indigo-400">
                      {formatInt(m.tokens)}
                    </div>
                    <div className="text-[0.5625rem] text-emerald-400">{formatUsd(m.cost_usd)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  icon,
  mono = false,
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-stone-800 bg-[#2c2825] p-5">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
          {label}
        </span>
        {icon}
      </div>
      <div
        className={`text-2xl font-black tabular-nums text-stone-100 ${mono ? 'font-mono text-lg' : ''}`}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-[0.625rem] text-stone-500">{sub}</div>}
    </div>
  );
}
