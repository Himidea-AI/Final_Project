/**
 * 슈퍼어드민 brand picker 모달.
 *
 * 사용 흐름:
 * 1. 시뮬 입력폼에서 슈퍼어드민이 [브랜드 선택] 버튼 클릭 → 모달 열림
 * 2. 검색어 입력 + 업종 필터 → /admin/brands 조회
 * 3. 클릭 → onSelect 콜백으로 AdminBrand 전달, 모달 닫힘
 *
 * 호스트 (App.tsx) 가 onSelect 받아 brand_name 오버라이드 + businessType 자동 설정.
 */

import { useEffect, useMemo, useState } from 'react';
import { Search, Building2, X, Store, AlertCircle } from 'lucide-react';
import { useAdminBrands } from '../../hooks/useAdminBrands';
import type { AdminBrand } from '../../types/admin';

export interface AdminBrandPickerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (brand: AdminBrand) => void;
  /** 초기 업종 필터 (canonical key). 비우면 전체. */
  initialIndustry?: string;
}

const PAGE_SIZE = 50;

export function AdminBrandPicker({
  open,
  onClose,
  onSelect,
  initialIndustry,
}: AdminBrandPickerProps) {
  const [query, setQuery] = useState('');
  const [industry, setIndustry] = useState<string>(initialIndustry ?? '');
  const [page, setPage] = useState(1);

  // 모달 열릴 때 초기화
  useEffect(() => {
    if (open) {
      setQuery('');
      setIndustry(initialIndustry ?? '');
      setPage(1);
    }
  }, [open, initialIndustry]);

  // ESC → close
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  const { items, total, supportedIndustries, loading, error, forbidden } = useAdminBrands({
    q: query,
    industry: industry || undefined,
    page,
    size: PAGE_SIZE,
    enabled: open,
  });

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="브랜드 선택"
    >
      <div
        className="w-full max-w-3xl max-h-[85vh] bg-card border border-border rounded-xl shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Building2 size={18} className="text-primary" />
            <h2 className="text-base font-semibold text-foreground">
              브랜드 선택 <span className="text-xs text-muted-foreground ml-2">슈퍼어드민</span>
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="닫기"
          >
            <X size={18} />
          </button>
        </div>

        {/* Filters */}
        <div className="px-5 py-3 border-b border-border space-y-2">
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              placeholder="브랜드명 또는 기업명 검색 (예: 스타벅스)"
              className="w-full pl-9 pr-3 h-9 rounded-lg border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              autoFocus
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => {
                setIndustry('');
                setPage(1);
              }}
              className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                industry === ''
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-border text-muted-foreground hover:text-foreground'
              }`}
            >
              전체
            </button>
            {supportedIndustries.map((ind) => (
              <button
                key={ind.key}
                type="button"
                onClick={() => {
                  setIndustry(ind.key);
                  setPage(1);
                }}
                className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                  industry === ind.key
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'border-border text-muted-foreground hover:text-foreground'
                }`}
              >
                {ind.label}
              </button>
            ))}
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {forbidden && (
            <div className="p-6 text-center text-sm text-destructive flex flex-col items-center gap-2">
              <AlertCircle size={20} />
              슈퍼어드민 권한이 없습니다. 일반 master / manager 는 picker 사용 불가.
            </div>
          )}
          {error && !forbidden && (
            <div className="p-6 text-center text-sm text-destructive">{error}</div>
          )}
          {!forbidden && !error && loading && (
            <div className="p-6 text-center text-sm text-muted-foreground">조회 중…</div>
          )}
          {!forbidden && !error && !loading && items.length === 0 && (
            <div className="p-6 text-center text-sm text-muted-foreground">
              검색 결과 없음. 다른 키워드 / 업종 필터를 시도하세요.
            </div>
          )}
          {!forbidden && !error && items.length > 0 && (
            <ul className="divide-y divide-border">
              {items.map((b, i) => (
                <li key={`${b.brand_name}-${b.corp_name ?? ''}-${i}`}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(b);
                      onClose();
                    }}
                    className="w-full text-left px-5 py-3 hover:bg-muted transition-colors flex items-start gap-3"
                  >
                    <div className="mt-0.5 shrink-0">
                      <Store size={16} className="text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="text-sm font-medium text-foreground truncate">
                          {b.brand_name}
                        </span>
                        <span className="text-xs text-muted-foreground truncate">
                          {b.industry_medium ?? b.business_type}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5 truncate">
                        {b.corp_name ?? '—'}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5 flex gap-3">
                        {typeof b.franchise_count === 'number' && (
                          <span>가맹점 {b.franchise_count.toLocaleString()}개</span>
                        )}
                        {typeof b.avg_sales === 'number' && b.avg_sales > 0 && (
                          <span>
                            평균매출 {Math.round(b.avg_sales / 1000).toLocaleString()}백만원
                          </span>
                        )}
                        <span className="ml-auto text-[10px] text-muted-foreground/70">
                          {b.source === 'biz_brand_mapping' ? '회원사' : 'FTC'}
                        </span>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer — pagination */}
        {!forbidden && !error && items.length > 0 && (
          <div className="px-5 py-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
            <span>
              총 {total.toLocaleString()}개 · {page} / {totalPages} 페이지
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2 py-1 border border-border rounded disabled:opacity-30 hover:text-foreground"
              >
                이전
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-2 py-1 border border-border rounded disabled:opacity-30 hover:text-foreground"
              >
                다음
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
