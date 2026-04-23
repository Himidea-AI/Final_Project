"""시뮬레이션 통합 runner."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .agents import spawn_agents
from .brain import LLMBrain
from .config import (
    MAPO_DONGS,
    ModelConfig,
    PopulationMix,
    Scenario,
    TierDistribution,
    TimeConfig,
    estimate_cost,
)
from .conversation import ConversationEngine, build_friends
from .memory import MemoryStore
from .memory_index import PgVectorMemory
from .personas import assign_personas
from .scheduler import Scheduler
from .policy_generator import generate_policies
from .world import World, seed_synthetic_world
from .world_loader import StoreHoursMap, load_subway_inflow_csv, load_world_from_rds


def _load_dong_coords() -> dict[str, tuple[float, float]]:
    """dong_subway_access에서 동 중심 좌표 + 외부 가상 좌표."""
    import os

    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text

    load_dotenv()
    out: dict[str, tuple[float, float]] = {}
    try:
        e = create_engine(os.environ["POSTGRES_URL"], isolation_level="AUTOCOMMIT")
        with e.connect() as c:
            rows = c.execute(text("SELECT dong_name, center_lat, center_lon FROM dong_subway_access")).fetchall()
        out = {r[0]: (float(r[1]), float(r[2])) for r in rows if r[1] and r[2]}
    except Exception as ex:
        print(f"[trajectory] 동 좌표 로드 실패: {ex}")
    # External 에이전트는 마포 외곽(지도 경계 밖)으로 표시
    out["외부"] = (37.530, 126.860)  # 마포 남서쪽
    return out


def _load_weather_recent() -> dict:
    """weather_daily 최신 일자 1건 → World 날씨 상태."""
    import os

    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text

    load_dotenv()
    try:
        e = create_engine(os.environ["POSTGRES_URL"], isolation_level="AUTOCOMMIT")
        with e.connect() as c:
            row = (
                c.execute(
                    text(
                        "SELECT date, temp_avg, rain_day, snow_new "
                        "FROM weather_daily WHERE stn_name='서울' "
                        "ORDER BY date DESC LIMIT 1"
                    )
                )
                .mappings()
                .fetchone()
            )
        if not row:
            return {}
        rain = row.get("rain_day") or 0
        snow = row.get("snow_new") or 0
        if snow > 0:
            desc = "눈"
        elif rain > 5:
            desc = "비"
        elif rain > 0:
            desc = "약한비"
        else:
            desc = "맑음"
        return {
            "weather": desc,
            "temperature": float(row.get("temp_avg") or 18),
            "rain_mm": float(rain),
        }
    except Exception as ex:
        print(f"[weather] 로드 실패: {ex}")
        return {}


def _load_holidays() -> dict[str, dict]:
    """holiday_calendar → {YYYY-MM-DD: {is_holiday, holiday_name, is_weekend}}."""
    import os

    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text

    load_dotenv()
    out: dict[str, dict] = {}
    try:
        e = create_engine(os.environ["POSTGRES_URL"], isolation_level="AUTOCOMMIT")
        with e.connect() as c:
            rows = c.execute(
                text("SELECT date, is_weekend, is_holiday, holiday_name FROM holiday_calendar WHERE year >= 2025")
            ).fetchall()
        for r in rows:
            out[r[0].isoformat()] = {
                "is_weekend": bool(r[1]),
                "is_holiday": bool(r[2]),
                "holiday_name": r[3],
            }
    except Exception as ex:
        print(f"[holiday] 로드 실패: {ex}")
    return out


def _dump_trajectory(path: str | Path, rows: list[dict]) -> None:
    import json as _json

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        _json.dump(rows, f, ensure_ascii=False)


def _dump_sidecar(base_path: str | Path, suffix: str, rows: list[dict]) -> None:
    """trajectory 파일과 같은 디렉토리에 _<suffix>.json 저장."""
    import json as _json

    p = Path(base_path)
    out = p.with_name(p.stem.replace("_trajectory", "") + f"_{suffix}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        _json.dump(rows, f, ensure_ascii=False)


def _dump_partial(
    save_path: str | Path,
    *,
    days: int,
    day: int,
    hour: int,
    total_steps_per_day: int,
    total_decisions: int,
    brain_stats,
    cost_usd: float,
    world,
    sample_stories: list[str],
    in_progress: bool,
) -> None:
    """진행 중 결과를 같은 경로에 덮어써서 dashboard가 라이브 표시."""
    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    top = sorted(world.stores.values(), key=lambda s: s.revenue_today, reverse=True)[:30]
    progress_pct = ((day - 1) * total_steps_per_day + (hour - 6 + 1)) / max(1, days * total_steps_per_day)
    payload = {
        "days": days,
        "total_decisions": total_decisions,
        "tier_s_calls": brain_stats.tier_s_calls,
        "tier_a_calls": brain_stats.tier_a_calls,
        "estimated_cost_usd": round(cost_usd, 4),
        "top_stores": [
            {
                "store_id": s.store_id,
                "name": s.name,
                "dong": s.dong,
                "category": s.category,
                "visits": s.visits_today,
                "revenue": s.revenue_today,
            }
            for s in top
        ],
        "sample_stories": sample_stories[:20],
        "in_progress": in_progress,
        "current_day": day,
        "current_hour": hour,
        "progress_pct": round(min(1.0, max(0.0, progress_pct)), 4),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


@dataclass
class SimulationResult:
    days: int
    total_decisions: int
    tier_s_calls: int
    tier_a_calls: int
    estimated_cost_usd: float
    top_stores: list[dict]
    sample_stories: list[str]
    in_progress: bool = False
    current_day: int = 0
    current_hour: int = 0
    progress_pct: float = 0.0
    # 전체 매장 통계 (검증용) - 카테고리별 총 방문/매출 집계
    category_totals: dict | None = None
    dong_totals: dict | None = None
    # B1 /api/simulate-abm 호환 필드 (일일 집계)
    daily_visits: int = 0
    daily_visits_std: float = 0.0
    daily_revenue: float = 0.0
    daily_revenue_std: float = 0.0
    peak_hours: list = field(default_factory=list)
    customer_profile_dist: dict = field(default_factory=dict)
    cannibalization: dict = field(default_factory=dict)
    narrator_summary: str = ""
    trajectory: list | None = None
    # 신규 매장(공실 스팟 클릭) 의 시뮬 결과 — 프론트 결과 카드용
    new_store_visits: int = 0
    new_store_revenue: float = 0.0
    new_store_visit_share_pct: float = 0.0  # 전체 방문 중 점유율 (%)

    def get(self, key: str, default=None):
        """dict-like access — B1 엔드포인트 result.get() 호환."""
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        return getattr(self, key)


def run_simulation(
    days: int = 1,
    pop: PopulationMix | None = None,
    tier: TierDistribution | None = None,
    cfg: ModelConfig | None = None,
    time_cfg: TimeConfig | None = None,
    world: World | None = None,
    seed: int = 42,
    verbose: bool = True,
    use_rds: bool = False,
    hours_map: StoreHoursMap | None = None,
    use_pgvector: bool = False,
    pgvector_clear: bool = False,
    scenario: Scenario | None = None,
    save_path: str | Path | None = None,
    llm_concurrency: int = 4,
    use_profiles: bool = False,
    enable_chat: bool = False,
    chat_per_step: int = 2,
    trajectory_path: str | Path | None = None,
    use_dsl: bool = False,
    use_policy: bool = False,
    collect_trajectory: bool = False,
    trajectory_sample_size: int = 300,
    seed_memory: bool = True,
    memory_seed_days: int = 14,
    warmup_days: int = 0,
    llm_base_cache: str | Path | None = None,
) -> SimulationResult:
    pop = pop or PopulationMix()
    tier = tier or TierDistribution()
    cfg = cfg or ModelConfig()
    time_cfg = time_cfg or TimeConfig()

    # B1 n_personas 지원 — PopulationMix 총합을 n_personas로 비례 축소/확대
    if cfg.n_personas and cfg.n_personas > 0:
        current_total = pop.residents + pop.commuters + pop.visitors + pop.owners + pop.ext_commuters + pop.ext_visitors
        if current_total > 0 and current_total != cfg.n_personas:
            scale = cfg.n_personas / current_total
            pop = PopulationMix(
                residents=max(1, int(pop.residents * scale)),
                commuters=max(0, int(pop.commuters * scale)),
                visitors=max(0, int(pop.visitors * scale)),
                owners=max(0, int(pop.owners * scale)),
                ext_commuters=max(0, int(pop.ext_commuters * scale)),
                ext_visitors=max(0, int(pop.ext_visitors * scale)),
            )
            # Policy 모드가 기본 ON (B1 호환)
            use_policy = True

    if world is None:
        if use_rds:
            world, hours_map = load_world_from_rds()
        else:
            world = seed_synthetic_world(seed=seed)

    # 시나리오 충격 적용
    scenario = scenario or Scenario()
    world.price_multiplier = scenario.price_multiplier
    world.use_dsl = use_dsl
    world.use_policy = use_policy

    # 신규 매장 주입 (공실 스팟 클릭 시뮬용) — 편의점 제외
    new_store_sim_id: str | None = None
    if scenario.new_store:
        from .world import Store as _Store

        ns_cat_raw = (scenario.new_store.get("category") or "음식점").strip()
        # 음식점/카페/주점만 허용, 외이면 음식점으로 기본
        ns_cat = ns_cat_raw if ns_cat_raw in ("음식점", "카페", "주점") else "음식점"
        ns_dong = scenario.new_store.get("district") or scenario.new_store.get("dong")
        if ns_dong and ns_dong in world.dongs:
            new_store_sim_id = f"new_spot_{scenario.new_store.get('brand') or 'candidate'}"
            new_store = _Store(
                store_id=new_store_sim_id,
                name=str(scenario.new_store.get("brand") or "신규 스팟"),
                dong=ns_dong,
                category=ns_cat,
                seats=30,
                rating=4.0,
                price_level=int(scenario.new_store.get("price_level") or 2),
                lat=scenario.new_store.get("lat"),
                lon=scenario.new_store.get("lon"),
                popularity_boost=float(scenario.new_store.get("popularity_boost") or 1.0),
            )
            world.add_store(new_store)
            if verbose:
                print(f"  [NEW] 신규 매장 주입: {new_store_sim_id} ({ns_cat} @ {ns_dong})", flush=True)
    if verbose and use_dsl:
        print("  [CFG] DSL 의사결정 모드 ON (전 Tier brain.dsl_decide)", flush=True)
    if verbose and use_policy:
        print("  [CFG] Policy Generator 모드 ON (LLM 호출 11회만, 군중은 Python)", flush=True)

    # 시나리오 — 날씨 오버라이드
    if scenario.weather_override:
        world.weather = scenario.weather_override
        if verbose:
            print(f"  시나리오 날씨 override: {world.weather}", flush=True)

    # 지하철 외부유입 calibration 데이터 로드 (External 에이전트 시간/동 분포에 사용)
    world.subway_inflow = load_subway_inflow_csv()
    if verbose and world.subway_inflow:
        n_keys = len(world.subway_inflow)
        n_dongs = len({d for d, _ in world.subway_inflow})
        print(f"  지하철 inflow: {n_keys}건 ({n_dongs}개 동) 로드", flush=True)

    # Policy Generator — use_policy=True면 11개 정책 로드 (캐시 있으면 재사용)
    if use_policy:
        world.policy_cache = generate_policies(llm_base_cache=llm_base_cache) if llm_base_cache else generate_policies()
        if verbose:
            print(f"  정책 캐시: {len(world.policy_cache)}개 (LLM 호출 0회 모드)", flush=True)

    # 날씨 + 휴일 RDS 주입 — weather_override 있으면 날씨는 건드리지 않음
    weather_info = _load_weather_recent()
    if weather_info:
        if not scenario.weather_override:
            world.weather = weather_info.get("weather", world.weather)
        world.temperature = weather_info.get("temperature", world.temperature)
        world.rain_mm = weather_info.get("rain_mm", 0.0)
        if verbose:
            print(f"  날씨: {world.weather} {world.temperature:.1f}도 (강수 {world.rain_mm:.1f}mm)", flush=True)

    holiday_map = _load_holidays()

    if verbose:
        print("\n=== Simulation 시작 ===", flush=True)
        ext_c = getattr(pop, "ext_commuters", 0)
        ext_v = getattr(pop, "ext_visitors", 0)
        print(
            f"  인구: 거주{pop.residents} / 통근{pop.commuters} / 방문{pop.visitors} / 점주{pop.owners}"
            f" / 외부통근{ext_c} / 외부방문{ext_v} (총{pop.residents + pop.commuters + pop.visitors + pop.owners + ext_c + ext_v})",
            flush=True,
        )
        print(f"  Tier: S={tier.tier_s} / A={tier.tier_a} / B={tier.tier_b}", flush=True)
        print(f"  모드: {'MOCK' if cfg.mock_mode else 'API'}", flush=True)
        print(f"  Days: {days}, Hours/day: {time_cfg.total_steps}", flush=True)

    # 1. 에이전트 생성 (use_profiles=True면 RDS 기반 개인화)
    agents = spawn_agents(
        n_residents=pop.residents,
        n_commuters=pop.commuters,
        n_visitors=pop.visitors,
        n_owners=pop.owners,
        n_ext_commuters=getattr(pop, "ext_commuters", 0),
        n_ext_visitors=getattr(pop, "ext_visitors", 0),
        tier_s=tier.tier_s,
        tier_a=tier.tier_a,
        dongs=MAPO_DONGS,
        seed=seed,
        use_profiles=use_profiles,
        subway_inflow=world.subway_inflow,
    )

    # 2. 페르소나 부여 (Tier S만)
    personas = assign_personas(agents, seed=seed)
    if verbose:
        print(f"  페르소나: {len(personas)}개 생성 (Tier S)")

    # 2.5 실데이터 기반 시간×동×연령×요일 가중치 로드
    try:
        from .profile_builder import ProfileBuilder

        _pb = ProfileBuilder(seed=seed)
        world.time_age_boost = _pb.load_time_age_boost()
    except Exception as e:
        print(f"  [warn] time_age_boost 로드 실패: {e}")

    # 2.6 [v12] Memory Seeding — 격자 데이터 기반 가상 visit_history 주입 (Cold Start 완화)
    if seed_memory:
        try:
            from .memory_seeder import seed_all_agents

            seed_all_agents(agents, world, days_of_history=memory_seed_days, verbose=verbose)
        except Exception as e:
            print(f"  [warn] memory seeding 실패: {e}")

    # 3. Brain + Scheduler 준비 (+ pgvector 메모리 옵션)
    memory_index: PgVectorMemory | None = None
    if use_pgvector:
        memory_index = PgVectorMemory(lazy=False)
        if pgvector_clear:
            memory_index.clear_collection()
        if verbose:
            print("  pgvector: sim_agent_memory 컬렉션 활성화")

    brain = LLMBrain(cfg=cfg, seed=seed, memory_index=memory_index)
    brain.register_personas(personas)

    if not cfg.mock_mode:
        # 실제 API 모드면 mock 자동전환 여부 출력
        if cfg.mock_mode:
            print("  ⚠️ API 키 없음 → MOCK 모드로 fallback")

    # 친구 네트워크 (Policy 모드에서도 동반 방문 기능으로 사용됨)
    if enable_chat or use_policy:
        build_friends(agents, k_per_agent=3, seed=seed)
        if verbose:
            print("  친구 네트워크 구축 (k=3)", flush=True)

    # 대화 엔진 (chat 전용)
    conv = None
    if enable_chat:
        conv = ConversationEngine(brain, max_chats_per_step=chat_per_step, seed=seed)
        if verbose:
            print(f"  대화: 매 step 최대 {chat_per_step}쌍 chat", flush=True)

    scheduler = Scheduler(
        world,
        agents,
        seed=seed,
        hours_map=hours_map,
        llm_concurrency=llm_concurrency,
        conversation=conv,
    )
    memory = MemoryStore()

    total_decisions = 0
    sample_stories: list[str] = []
    pending_memory: list[dict] = []  # 일별 배치 저장용

    # 에이전트 궤적 수집 (시각화용) — trajectory_path 파일 덤프 또는 collect_trajectory 인메모리 수집
    trajectory: list[dict] = []
    visits_log: list[dict] = []
    chats_log: list[dict] = []
    _need_trajectory = bool(trajectory_path) or collect_trajectory
    dong_coords = _load_dong_coords() if _need_trajectory else {}
    # 인메모리 샘플링 — 1000 agents 전부 보내면 payload 과대, sample_size 만큼만 수집
    _trajectory_sample_ids: set[int] = set()
    if collect_trajectory and agents:
        import random as _sample_rng

        _r = _sample_rng.Random(seed)
        sample_n = min(trajectory_sample_size, len(agents))
        _trajectory_sample_ids = {a.agent_id for a in _r.sample(agents, sample_n)}

    # 에이전트 홈 좌표 (동 center)
    def _home_coord(a) -> tuple[float, float] | None:
        return dong_coords.get(a.home_dong)

    # 4. 일 단위 루프
    import datetime as _dt

    if scenario.date_override:
        try:
            sim_start = _dt.date.fromisoformat(scenario.date_override)
            if verbose:
                print(f"  시나리오 날짜 override: {sim_start.isoformat()}", flush=True)
        except ValueError:
            print(f"[runner] date_override 파싱 실패: {scenario.date_override} — today() 사용")
            sim_start = _dt.date.today()
    else:
        sim_start = _dt.date.today()

    # 계절·월급일 주입 (v10 realism)
    world.month = sim_start.month
    world.is_payday = sim_start.day in (25, 26, 27)  # 월급일 +/- 1일
    if verbose:
        if world.is_payday:
            print("  [PAY] 월급일 주간 (budget × 1.15, spend_tendency × 1.3)", flush=True)
        print(f"  [SEASON] 현재 월: {world.month}월 (계절 보정 적용)", flush=True)

    # [v12] Warmup: 측정 전 N 일 시뮬 후 집계 초기화 — Layer 2/5 습관 형성
    total_loops = warmup_days + days
    for day_idx in range(1, total_loops + 1):
        day = day_idx - warmup_days  # day <= 0 이면 warmup
        is_warmup = day_idx <= warmup_days
        real_date = sim_start + _dt.timedelta(days=day_idx - 1 - warmup_days)
        hol = holiday_map.get(real_date.isoformat(), {})
        world.is_weekend = scenario.weekend_force or hol.get("is_weekend", (day_idx % 7) in (6, 0))
        world.is_holiday = hol.get("is_holiday", False)
        world.holiday_name = hol.get("holiday_name")

        if verbose:
            tag = ("WARMUP " if is_warmup else "") + ("주말" if world.is_weekend else "평일")
            if world.is_holiday:
                tag += f" · 공휴일({world.holiday_name})"
            print(f"\n  --- Day {day_idx} ({tag}) ---", flush=True)

        # Warmup 마지막 시점에 집계 리셋 — 측정 day 들부터 stats 깨끗하게 시작
        if is_warmup and day_idx == warmup_days:
            if verbose:
                print(f"  [warmup] {warmup_days}일 warmup 종료, 집계 리셋", flush=True)
            for s in world.stores.values():
                s.visits_today = 0
                s.revenue_today = 0.0
            total_decisions = 0
            visits_log.clear()
            trajectory.clear()

        for _ in range(time_cfg.total_steps):
            res = scheduler.step(brain)
            total_decisions += res.activated
            # agent_id → Agent lookup (v11: Layer 2/3/5 업데이트용)
            _agent_by_id = {a.agent_id: a for a in agents}

            for aid, dec in res.decisions:
                target_str = str(dec.target_store_id or dec.target_dong or "")
                memory.of(aid).add(
                    day=day,
                    hour=res.hour,
                    action=dec.action,
                    target=target_str,
                )
                # v11 Layer 2: 방문 기록 → agent.record_visit + store_satisfaction 갱신
                _a = _agent_by_id.get(aid)
                if _a is not None and dec.action == "visit" and dec.target_store_id:
                    _store = world.stores.get(dec.target_store_id)
                    if _store is not None:
                        # 만족도 — rating + price fit + congestion
                        cong = min(1.0, _store.visits_today / max(_store.seats, 1))
                        sat = max(
                            0.0,
                            min(
                                1.0,
                                0.5
                                + 0.1 * (_store.rating - 3.0)
                                - 0.3 * cong
                                + 0.15 * (1.0 if _store.price_level <= _a.income_level else -0.5),
                            ),
                        )
                        _a.record_visit(
                            day=day, hour=res.hour, store_id=_store.store_id, category=_store.category, satisfaction=sat
                        )
                        _a.store_satisfaction[_store.store_id] = sat
                        # 배고픔 리셋
                        if _store.category in ("음식점", "편의점"):
                            _a.hunger = max(0.0, _a.hunger - 0.8)
                        # v11 Layer 5: 친구에게 추천 전파 (만족도 >0.7 일 때만)
                        if sat > 0.7 and _a.friends:
                            # 친한 친구 최대 2명에게 추천
                            import random as _rnd

                            for fid in _a.friends[:2]:
                                friend = _agent_by_id.get(fid)
                                if friend is not None and _rnd.random() < 0.3:
                                    friend.pending_recommendations.append(
                                        {
                                            "store_id": _store.store_id,
                                            "from_agent": aid,
                                            "category": _store.category,
                                            "strength": sat,
                                        }
                                    )
                                    # 추천 큐는 최대 20건 유지
                                    if len(friend.pending_recommendations) > 20:
                                        friend.pending_recommendations = friend.pending_recommendations[-20:]
                # v11 Layer 3: 매 tick 내부 상태 진화 (visit 여부 무관)
                if _a is not None:
                    _a.tick_state(res.hour, dec.action, world)
                # 방문 이벤트 수집 (지도 시각화용) + 주문 메뉴 추정
                if trajectory_path and dec.action == "visit" and dec.target_store_id:
                    store = world.stores.get(dec.target_store_id)
                    if store and store.lat and store.lon:
                        # 주문 메뉴: 가격이 spend에 가장 가까운 것
                        ordered = None
                        if store.menu_items:
                            ordered = min(
                                store.menu_items,
                                key=lambda m: abs(m["price"] - dec.spend),
                            )
                        visits_log.append(
                            {
                                "agent_id": aid,
                                "day": day,
                                "hour": res.hour,
                                "store_id": store.store_id,
                                "store_name": store.name,
                                "store_category": store.category,
                                "store_lat": store.lat,
                                "store_lon": store.lon,
                                "spend": float(dec.spend),
                                "menu_name": ordered["name"] if ordered else None,
                                "menu_price": ordered["price"] if ordered else None,
                            }
                        )
                if memory_index is not None and dec.action != "rest":
                    # Tier S/A 만 임베딩 (Tier B는 LLM 안쓰니 인덱싱 불필요)
                    pending_memory.append(
                        {
                            "agent_id": aid,
                            "day": day,
                            "hour": res.hour,
                            "action": dec.action,
                            "target": target_str,
                            "reason": dec.reason,
                        }
                    )
                # 흥미로운 이유는 샘플 스토리로 수집
                if dec.reason and len(sample_stories) < 20:
                    sample_stories.append(f"[D{day} {res.hour}시] agent#{aid}: {dec.action} - {dec.reason}")
            if verbose:
                print(f"    {res.hour:02d}시: 활성 {res.activated} / 스킵 {res.skipped}", flush=True)

            # 매 시간 에이전트 위치 스냅샷 — visit는 매장 좌표, 그 외는 동 중심 + jitter
            if _need_trajectory and dong_coords:
                import random as _rng

                rng_jit = _rng.Random(res.hour * 1000 + day)
                # 이번 시간 visit한 에이전트 → 매장 좌표 매핑
                visited_now = {}
                for aid, dec in res.decisions:
                    if dec.action == "visit" and dec.target_store_id:
                        st = world.stores.get(dec.target_store_id)
                        if st and st.lat and st.lon:
                            visited_now[aid] = (st.lat, st.lon)

                _iter_agents = (
                    [a for a in agents if a.agent_id in _trajectory_sample_ids]
                    if collect_trajectory and _trajectory_sample_ids
                    else agents
                )
                for a in _iter_agents:
                    if a.agent_id in visited_now:
                        # 매장 좌표 사용 (사람들이 매장에 모임)
                        lat, lon = visited_now[a.agent_id]
                        lat += rng_jit.uniform(-0.0003, 0.0003)
                        lon += rng_jit.uniform(-0.0003, 0.0003)
                    else:
                        # 외부 에이전트가 마포 밖 대기 상태면 trajectory 엔트리 생략
                        # (지도 시각화 시 "목동쪽 허위 클러스터" 방지)
                        if a.current_dong == "외부":
                            continue
                        coord = dong_coords.get(a.current_dong)
                        if not coord:
                            continue
                        lat = coord[0] + rng_jit.uniform(-0.003, 0.003)
                        lon = coord[1] + rng_jit.uniform(-0.003, 0.003)
                    trajectory.append(
                        {
                            "agent_id": a.agent_id,
                            "day": day,
                            "hour": res.hour,
                            "dong": a.current_dong,
                            "action": a.last_action,
                            "tier": a.tier.value,
                            "role": a.role.value,
                            "lat": lat,
                            "lon": lon,
                        }
                    )

            # 대화 로그 (chat engine 내부 log를 지도 좌표 포함으로 복제)
            if trajectory_path and conv is not None:
                by_id = {a.agent_id: a for a in agents}
                for m in conv.log[len(chats_log) :]:
                    s = by_id.get(m.sender_id)
                    r = by_id.get(m.receiver_id)
                    s_c = dong_coords.get(s.current_dong) if s else None
                    r_c = dong_coords.get(r.current_dong) if r else None
                    if s_c and r_c:
                        chats_log.append(
                            {
                                "day": day,
                                "hour": m.hour,
                                "sender_id": m.sender_id,
                                "receiver_id": m.receiver_id,
                                "verb": m.verb,
                                "args": m.args,
                                "encoded": m.encoded(),
                                "sender_lat": s_c[0],
                                "sender_lon": s_c[1],
                                "receiver_lat": r_c[0],
                                "receiver_lon": r_c[1],
                            }
                        )

            # 매 시간 trajectory 증분 덤프 (라이브 움직임 시각화)
            if trajectory_path and trajectory:
                _dump_trajectory(trajectory_path, trajectory)
                _dump_sidecar(trajectory_path, "visits", visits_log)
                _dump_sidecar(trajectory_path, "chats", chats_log)

            # 매 시간 partial save (라이브 dashboard용)
            if save_path is not None:
                cost_now = estimate_cost(brain.stats.tier_s_calls, brain.stats.tier_a_calls, cfg)["total_usd"]
                _dump_partial(
                    save_path,
                    days=days,
                    day=day,
                    hour=res.hour,
                    total_steps_per_day=time_cfg.total_steps,
                    total_decisions=total_decisions,
                    brain_stats=brain.stats,
                    cost_usd=cost_now,
                    world=world,
                    sample_stories=sample_stories,
                    in_progress=True,
                )

        memory.end_of_day(day)

        # 일별 배치로 pgvector 인덱싱 (per-step 임베딩보다 효율적)
        if memory_index is not None and pending_memory:
            # Tier S/A 에이전트만 필터 (Tier B는 컨텍스트 활용 안함)
            interesting = [m for m in pending_memory if m["action"] in ("visit", "work")]
            if interesting:
                n = memory_index.add_batch(interesting[:500])  # 일일 상한
                if verbose:
                    print(f"  pgvector: D{day} 배치 인덱싱 {n}건")
            pending_memory.clear()

        if day < days:
            scheduler.end_of_day()

    # 5. 결과 집계
    cost = estimate_cost(
        tier_s_calls=brain.stats.tier_s_calls,
        tier_a_calls=brain.stats.tier_a_calls,
        cfg=cfg,
    )

    top_stores = sorted(world.stores.values(), key=lambda s: s.revenue_today, reverse=True)[:10]

    # 전체 매장 카테고리별/동별 집계 (검증용)
    cat_totals: dict[str, dict[str, float]] = {}
    dong_totals_: dict[str, dict[str, float]] = {}
    for s in world.stores.values():
        if s.visits_today == 0:
            continue
        cat_totals.setdefault(s.category, {"visits": 0, "revenue": 0.0})
        cat_totals[s.category]["visits"] += s.visits_today
        cat_totals[s.category]["revenue"] += s.revenue_today
        dong_totals_.setdefault(s.dong, {"visits": 0, "revenue": 0.0})
        dong_totals_[s.dong]["visits"] += s.visits_today
        dong_totals_[s.dong]["revenue"] += s.revenue_today

    # B1 /api/simulate-abm 호환 필드 계산
    from collections import Counter

    total_visits_all = sum(c["visits"] for c in cat_totals.values())
    total_revenue_all = sum(c["revenue"] for c in cat_totals.values())
    daily_visits_val = int(total_visits_all / max(days, 1))
    daily_revenue_val = total_revenue_all / max(days, 1)

    # 신규 매장(공실 스팟) 시뮬 결과 — visit_share_pct 계산
    new_store_visits_val = 0
    new_store_revenue_val = 0.0
    new_store_visit_share_pct_val = 0.0
    if new_store_sim_id and new_store_sim_id in world.stores:
        ns = world.stores[new_store_sim_id]
        new_store_visits_val = int(ns.visits_today / max(days, 1))
        new_store_revenue_val = ns.revenue_today / max(days, 1)
        if total_visits_all > 0:
            new_store_visit_share_pct_val = round(100.0 * ns.visits_today / total_visits_all, 3)
    # 일일 std — 1일 시뮬이면 0, 다일이면 분산 계산 가능 (단순화)
    daily_visits_std_val = 0.0
    daily_revenue_std_val = 0.0

    # peak_hours — 방문 많은 상위 3시간
    hour_visits: Counter = Counter()
    for a in agents:
        if hasattr(a, "_hourly_visits"):
            hour_visits.update(a._hourly_visits)
    # fallback: world 시뮬 tick별 visit 집계가 없다면 빈 리스트
    peak_hours_val = [h for h, _ in hour_visits.most_common(3)] if hour_visits else []

    # customer_profile_dist — role별 방문 비율
    role_counts: Counter = Counter()
    for a in agents:
        role_counts[a.role.value] += len(a.visited_today)
    profile_total = sum(role_counts.values())
    customer_profile_dist_val = (
        {r: round(v / profile_total, 3) for r, v in role_counts.items()} if profile_total else {}
    )

    # cannibalization — 신규 매장 주변 기존 매장 매출 감소 추정 (scenario.new_store 있을 때만)
    cannibalization_val: dict = {}
    if scenario.new_store and scenario.new_store.get("district"):
        target_dong = scenario.new_store.get("district")
        if target_dong in dong_totals_:
            cannibalization_val = {
                "target_dong": target_dong,
                "cannibalize_radius_m": scenario.cannibalize_radius_m,
                "estimated_impact_pct": 5.0,  # 간이 추정 (추후 반경 기반 정밀 계산)
                "affected_stores": len(world.stores_by_dong.get(target_dong, [])),
            }

    # narrator_summary — 간단한 자연어 요약
    narrator_summary_val = (
        f"마포구 {pop.residents + pop.commuters + pop.visitors + pop.owners + pop.ext_commuters + pop.ext_visitors}명 "
        f"에이전트가 {days}일간 총 {total_decisions:,}회 의사결정, "
        f"{daily_visits_val:,}회 방문 발생. 일 매출 약 {int(daily_revenue_val):,}원."
    )

    if verbose:
        print("\n=== 결과 ===")
        print(f"  총 결정: {total_decisions:,}")
        print(f"  Tier S 호출: {brain.stats.tier_s_calls}")
        print(f"  Tier A 호출: {brain.stats.tier_a_calls}")
        print(f"  실패: {brain.stats.failures}")
        print(
            f"  토큰 (S): in={brain.stats.tier_s_input_tokens} / "
            f"cache_r={brain.stats.tier_s_cache_read} / "
            f"cache_w={brain.stats.tier_s_cache_write} / "
            f"out={brain.stats.tier_s_output_tokens}"
        )
        print(f"  토큰 (A): in={brain.stats.tier_a_input_tokens} / out={brain.stats.tier_a_output_tokens}")
        print(f"  추정 비용: ${cost['total_usd']:.4f} (S=${cost['tier_s_usd']:.4f}, A=${cost['tier_a_usd']:.4f})")
        print("\n  매출 TOP 5:")
        for s in top_stores[:5]:
            print(f"    [{s.store_id}] {s.name} ({s.dong}) - 방문 {s.visits_today} / 매출 {int(s.revenue_today):,}원")

    result = SimulationResult(
        days=days,
        total_decisions=total_decisions,
        tier_s_calls=brain.stats.tier_s_calls,
        tier_a_calls=brain.stats.tier_a_calls,
        estimated_cost_usd=cost["total_usd"],
        top_stores=[
            {
                "store_id": s.store_id,
                "name": s.name,
                "dong": s.dong,
                "category": s.category,
                "visits": s.visits_today,
                "revenue": s.revenue_today,
            }
            for s in top_stores
        ],
        sample_stories=sample_stories,
        in_progress=False,
        current_day=days,
        current_hour=time_cfg.end_hour,
        progress_pct=1.0,
        category_totals=cat_totals,
        dong_totals=dong_totals_,
        daily_visits=daily_visits_val,
        daily_visits_std=daily_visits_std_val,
        daily_revenue=daily_revenue_val,
        daily_revenue_std=daily_revenue_std_val,
        peak_hours=peak_hours_val,
        customer_profile_dist=customer_profile_dist_val,
        cannibalization=cannibalization_val,
        narrator_summary=narrator_summary_val,
        trajectory=trajectory if trajectory else None,
        new_store_visits=new_store_visits_val,
        new_store_revenue=new_store_revenue_val,
        new_store_visit_share_pct=new_store_visit_share_pct_val,
    )

    # final partial 저장 (in_progress=False로 덮어쓰기)
    if save_path is not None:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2)

    # 궤적 + 사이드 파일 저장
    if trajectory_path and trajectory:
        _dump_trajectory(trajectory_path, trajectory)
        _dump_sidecar(trajectory_path, "visits", visits_log)
        _dump_sidecar(trajectory_path, "chats", chats_log)

        # 매장 좌표 dump
        stores_rows = [
            {
                "store_id": s.store_id,
                "name": s.name,
                "dong": s.dong,
                "category": s.category,
                "lat": s.lat,
                "lon": s.lon,
                "revenue_today": s.revenue_today,
                "visits_today": s.visits_today,
            }
            for s in world.stores.values()
            if s.lat and s.lon
        ]
        _dump_sidecar(trajectory_path, "stores", stores_rows)

        # 친구 네트워크 dump
        friends_rows = []
        for a in agents:
            if not a.friends:
                continue
            for fid in a.friends:
                if fid > a.agent_id:  # 중복 방지
                    b = next((x for x in agents if x.agent_id == fid), None)
                    if not b:
                        continue
                    c1 = dong_coords.get(a.home_dong)
                    c2 = dong_coords.get(b.home_dong)
                    if c1 and c2:
                        friends_rows.append(
                            {
                                "a": a.agent_id,
                                "b": fid,
                                "a_lat": c1[0],
                                "a_lon": c1[1],
                                "b_lat": c2[0],
                                "b_lon": c2[1],
                                "a_dong": a.home_dong,
                                "b_dong": b.home_dong,
                            }
                        )
        _dump_sidecar(trajectory_path, "friends", friends_rows)

        if verbose:
            print(
                f"  [trajectory] {len(trajectory):,}건, "
                f"visits {len(visits_log):,}, chats {len(chats_log):,}, "
                f"stores {len(stores_rows):,}, friends {len(friends_rows):,} 저장",
                flush=True,
            )

    return result
