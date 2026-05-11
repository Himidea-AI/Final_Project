/**
 * AddCandidateModal — 후보 추가 모달 (동×업종 선택).
 *
 * 변경 (2026-05-03):
 *   - 동 옵션 = 시뮬 입력 4동 한정 (props.availableDongs)
 *   - 16동 자유 비교 폐기 — props 로만 동 list 받음
 *   - 업종 옵션 = BIZ_TO_INDUSTRY_CODE 의 한국어 키 (한식/중식/.../카페/편의점)
 *   - DongDropdown 패턴 재사용 (ChevronRight + listbox)
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { BIZ_TO_INDUSTRY_CODE } from '../../../../constants/bizToIndustry';
import { DropdownSelect } from '../../../ui/DropdownSelect';

interface AddInput {
  dong: string;
  dongCode: string;
  industry: string;
  industryCode: string;
}

interface Props {
  onClose: () => void;
  onAdd: (input: AddInput) => boolean;
  /** 시뮬 입력 동 list (4동 한정). 비어있으면 모달은 disabled 안내 표시. */
  availableDongs: { name: string; code: string }[];
}

/** 한국어 업종 옵션 — 같은 industry_code 의 첫 한국어 키만. */
const INDUSTRY_OPTIONS: { name: string; code: string }[] = (() => {
  const seen = new Set<string>();
  const out: { name: string; code: string }[] = [];
  for (const [name, code] of Object.entries(BIZ_TO_INDUSTRY_CODE)) {
    if (!/[가-힣]/.test(name)) continue; // 한국어만
    if (seen.has(code)) continue;
    seen.add(code);
    out.push({ name, code });
  }
  return out;
})();

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function AddCandidateModal({ onClose, onAdd, availableDongs }: Props) {
  const noDongs = availableDongs.length === 0;
  const [dong, setDong] = useState<string>(availableDongs[0]?.name ?? '');
  const [industry, setIndustry] = useState<string>(INDUSTRY_OPTIONS[0]?.name ?? '');
  const dialogRef = useRef<HTMLDivElement>(null);

  const dongCode = useMemo(
    () => availableDongs.find((d) => d.name === dong)?.code ?? null,
    [dong, availableDongs],
  );
  const industryCode = useMemo(
    () => INDUSTRY_OPTIONS.find((i) => i.name === industry)?.code ?? null,
    [industry],
  );

  const canAdd = !!dongCode && !!industryCode && !noDongs;

  // ESC + outside click close
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  // autofocus 첫 focusable + 닫힐 때 트리거 버튼 focus 복귀 (WCAG 2.1 AA)
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    focusables?.[0]?.focus();
    return () => {
      previouslyFocused?.focus();
    };
  }, []);

  // focus trap (Tab / Shift+Tab wraparound)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'Tab') return;
    const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    if (!focusables || focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  // SSR safety — document 미존재 시 portal 생성 불가
  if (typeof document === 'undefined') return null;

  const dialog = (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="후보 추가"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onKeyDown={handleKeyDown}
    >
      <div
        ref={dialogRef}
        className="w-full max-w-md rounded-3xl border border-border bg-card p-6 shadow-2xl"
      >
        <h3 className="text-base font-black tracking-tight text-foreground">후보 추가</h3>
        <p className="mt-1 text-[0.6875rem] text-muted-foreground">
          {noDongs
            ? '시뮬 입력 동이 없어 후보를 추가할 수 없습니다.'
            : '비교할 동과 업종을 선택하세요. 시뮬 입력 동 한정.'}
        </p>

        <div className="mt-4 space-y-3">
          <DropdownSelect
            label="행정동"
            value={dong}
            onChange={setDong}
            options={availableDongs.map((d) => d.name)}
            disabled={noDongs}
          />
          <DropdownSelect
            label="업종"
            value={industry}
            onChange={setIndustry}
            options={INDUSTRY_OPTIONS.map((i) => i.name)}
          />
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center rounded-lg border border-border bg-card px-3 text-xs font-bold text-foreground transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
          >
            취소
          </button>
          <button
            type="button"
            disabled={!canAdd}
            onClick={() => {
              if (!canAdd || !dongCode || !industryCode) return;
              onAdd({ dong, dongCode, industry, industryCode });
            }}
            className="inline-flex h-9 items-center rounded-lg bg-primary px-3 text-xs font-black text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 disabled:opacity-40"
          >
            추가
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(dialog, document.body);
}
