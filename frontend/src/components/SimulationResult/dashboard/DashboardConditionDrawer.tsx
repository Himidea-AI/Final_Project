import { AnimatePresence, motion } from 'framer-motion';
import { Edit3, Sliders, Store, UserCheck, X } from 'lucide-react';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import type { SimulationInput } from '../../../types';

/**
 * DashboardConditionDrawer — 우측 slide-out 으로 시뮬 입력 조건 상세 표시.
 * §3.7: 빈/null/default row 자체 hide. 섹션 전체가 비면 섹션도 hide.
 *
 * Default 정의 (App.tsx 기본값과 일치):
 * - DEFAULT_RADIUS: 500m  (App.tsx:693 const [radius, setRadius] = useState(500))
 * - DEFAULT_OPERATING_HOURS: []  (빈 배열 = 미선택)
 */

interface Props {
  open: boolean;
  onClose: () => void;
  params: SimulationInput | null;
  brandFallback?: string;
}

const DEFAULT_RADIUS = 500;

const BIZ_LABEL_MAP: Record<string, string> = {
  한식: '한식음식점',
  중식: '중식음식점',
  일식: '일식음식점',
  양식: '양식음식점',
  제과점: '제과점',
  패스트푸드: '패스트푸드점',
  치킨: '치킨전문점',
  분식: '분식전문점',
  호프: '호프-간이주점',
  커피: '커피-음료',
};

const PRICE_LABEL_MAP: Record<string, string> = {
  under5k: '5천원 이하',
  '5to10k': '5천-1만',
  '10to20k': '1-2만',
  over20k: '2만 이상',
};

const GENDER_LABEL: Record<string, string> = {
  male: '남성',
  female: '여성',
};

const DAY_TYPE_LABEL: Record<string, string> = {
  weekday: '평일',
  weekend: '주말',
};

/** 시간대 raw key → 사용자 라벨 (App.tsx:1399 ChipGroup options 와 동기). */
const TIME_SLOT_LABEL: Record<string, string> = {
  time_00_06: '심야',
  time_06_11: '오전',
  time_11_14: '점심',
  time_14_17: '오후',
  time_17_21: '저녁',
  time_21_24: '야간',
};

function formatCapital(v: number): string {
  if (!Number.isFinite(v) || v <= 0) return '';
  if (v >= 1e8) return `${(v / 1e8).toFixed(1)}억`;
  if (v >= 1e4) return `${Math.round(v / 1e4).toLocaleString()}만원`;
  return `${v.toLocaleString()}원`;
}

function formatRent(v: number): string {
  if (!Number.isFinite(v) || v <= 0) return '';
  if (v >= 1_000_000) return `${Math.round(v / 1e4).toLocaleString()}만원/월`;
  return `${v.toLocaleString()}원/월`;
}

function formatTargetSales(v: number): string {
  if (!Number.isFinite(v) || v <= 0) return '';
  if (v >= 1e8) return `${(v / 1e8).toFixed(1)}억/월`;
  if (v >= 1e4) return `${Math.round(v / 1e4).toLocaleString()}만원/월`;
  return `${v.toLocaleString()}원/월`;
}

interface RowProps {
  label: string;
  value: string;
}

function Row({ label, value }: RowProps) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2 last:border-b-0">
      <span className="shrink-0 text-sm text-muted-foreground">{label}</span>
      <span
        className="min-w-0 text-right text-sm font-bold text-foreground tabular-nums"
        style={{ wordBreak: 'keep-all', overflowWrap: 'anywhere' }}
      >
        {value}
      </span>
    </div>
  );
}

interface SectionProps {
  icon: React.ReactNode;
  title: string;
  rows: { label: string; value: string }[];
  children?: React.ReactNode;
}

function Section({ icon, title, rows, children }: SectionProps) {
  if (rows.length === 0 && !children) return null;
  return (
    <section className="rounded-2xl border border-border bg-secondary p-5">
      <div className="mb-3 flex items-center gap-2 text-sm font-bold text-foreground">
        <span className="text-primary">{icon}</span>
        {title}
      </div>
      <div>
        {rows.map((r) => (
          <Row key={r.label} label={r.label} value={r.value} />
        ))}
      </div>
      {children}
    </section>
  );
}

export function DashboardConditionDrawer({ open, onClose, params, brandFallback }: Props) {
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const handleEsc = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEsc);
    };
  }, [open, onClose]);

  const handleEditConditions = () => {
    onClose();
    // state.intent='edit' → SimulatorDashboard 의 auto-redirect effect (App.tsx) 가 skip.
    // params 보존된 채 simulator 폼으로 진입.
    navigate('/simulator', { state: { intent: 'edit' } });
  };

  // === 섹션 1: 핵심 파라미터 ===
  const brandName = (params?.brand_name && params.brand_name.trim()) || brandFallback || '';
  const bizKey = params?.business_type ?? '';
  const bizLabel = BIZ_LABEL_MAP[bizKey] ?? bizKey;
  const dongs: string[] = (() => {
    if (!params) return [];
    if (params.target_districts && params.target_districts.length > 0)
      return params.target_districts;
    if (params.target_district) return [params.target_district];
    return [];
  })();
  const section1Rows: { label: string; value: string }[] = [];
  if (brandName) section1Rows.push({ label: '브랜드', value: brandName });
  if (bizLabel) section1Rows.push({ label: '업종', value: bizLabel });

  // === 섹션 2: 운영 조건 ===
  const section2Rows: { label: string; value: string }[] = [];
  if (params?.initial_capital && params.initial_capital > 0)
    section2Rows.push({ label: '초기 자본', value: formatCapital(params.initial_capital) });
  if (params?.store_area && params.store_area > 0)
    section2Rows.push({ label: '매장 면적', value: `${params.store_area}평` });
  if (params?.monthly_rent && params.monthly_rent > 0)
    section2Rows.push({ label: '월 임대료', value: formatRent(params.monthly_rent) });
  if (
    params?.commercial_radius &&
    params.commercial_radius > 0 &&
    params.commercial_radius !== DEFAULT_RADIUS
  )
    section2Rows.push({ label: '분석 반경', value: `${params.commercial_radius}m` });
  if (params?.operating_hours && params.operating_hours.length > 0)
    section2Rows.push({ label: '운영 시간', value: params.operating_hours.join(', ') });
  if (params?.target_price_range) {
    const priceLabel = PRICE_LABEL_MAP[params.target_price_range] ?? params.target_price_range;
    section2Rows.push({ label: '타겟 가격대', value: priceLabel });
  }

  // === 섹션 3: 타겟 고객 ===
  // 5 row 항상 표시 — 미선택은 "전체" 또는 "미입력" 으로 명시 (§3.7: simulator '전체' 옵션의
  // explicit fact 표시. null/undefined = 사용자가 '전체' 선택했거나 미선택, 둘 다 의미 동일).
  const ageGroups = params?.target_age_groups ?? [];
  const timeSlots = params?.target_time_slots ?? [];
  const section3Rows: { label: string; value: string }[] = [
    {
      label: '연령대',
      value: ageGroups.length > 0 ? ageGroups.join(', ') : '전체',
    },
    {
      label: '성별',
      value: params?.target_gender ? (GENDER_LABEL[params.target_gender] ?? '전체') : '전체',
    },
    {
      label: '시간대',
      value:
        timeSlots.length > 0 ? timeSlots.map((t) => TIME_SLOT_LABEL[t] ?? t).join(', ') : '전체',
    },
    {
      label: '요일',
      value: params?.target_day_type ? (DAY_TYPE_LABEL[params.target_day_type] ?? '전체') : '전체',
    },
    {
      label: '목표 월 매출',
      value:
        params?.target_monthly_sales && params.target_monthly_sales > 0
          ? formatTargetSales(params.target_monthly_sales)
          : '미입력',
    },
  ];

  // 모두 미선택/미입력 인 케이스 — 섹션 헤더 + 작은 캡션만 (5 row 모두 fallback 일 때).
  const allTargetEmpty =
    ageGroups.length === 0 &&
    !params?.target_gender &&
    timeSlots.length === 0 &&
    !params?.target_day_type &&
    (!params?.target_monthly_sales || params.target_monthly_sales <= 0);

  // 분석 대상 동 리스트는 별도 children 처리 (섹션 1 안)
  const hasDongs = dongs.length > 0;

  return (
    <AnimatePresence>
      {open && params && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="condition-drawer-title"
            className="fixed inset-y-0 right-0 z-[101] flex h-full w-full flex-col overflow-hidden border-l border-border bg-card md:w-[420px]"
          >
            {/* 헤더 */}
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <h2 id="condition-drawer-title" className="text-lg font-bold text-foreground">
                분석 조건
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="닫기"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* 본문 (스크롤) */}
            <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
              {(section1Rows.length > 0 || hasDongs) && (
                <Section icon={<Store size={16} />} title="핵심 파라미터" rows={section1Rows}>
                  {hasDongs && (
                    <div className="mt-2 border-t border-border pt-3">
                      <div className="mb-2 text-sm text-muted-foreground">
                        분석 대상 ({dongs.length}동)
                      </div>
                      <ul className="space-y-1">
                        {dongs.map((d) => (
                          <li
                            key={d}
                            className="flex items-center gap-2 text-sm font-bold text-foreground"
                          >
                            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                            {d}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Section>
              )}

              <Section icon={<Sliders size={16} />} title="운영 조건" rows={section2Rows} />

              {/* 타겟 고객 — 5 row 항상 표시. 모두 fallback 이면 섹션 헤더 + 캡션만. */}
              <Section
                icon={<UserCheck size={16} />}
                title="타겟 고객"
                rows={allTargetEmpty ? [] : section3Rows}
              >
                {allTargetEmpty && (
                  <p className="text-xs italic text-muted-foreground leading-relaxed">
                    페르소나 선택 없음 — 전체 고객 기준 분석.
                  </p>
                )}
              </Section>
            </div>

            {/* 하단 버튼 */}
            <div className="border-t border-border bg-card px-6 py-4">
              <button
                type="button"
                onClick={handleEditConditions}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary bg-primary px-4 py-3 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
              >
                <Edit3 size={14} />
                조건 수정 (시뮬레이터로 이동)
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
