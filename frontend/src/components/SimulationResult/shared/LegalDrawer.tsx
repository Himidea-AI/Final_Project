import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import type { LegalChecklistItem } from '../../../types';

const STORAGE_PREFIX = 'legal-checklist-v1:';

function loadChecked(typeKey: string): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_PREFIX + typeKey);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function saveChecked(typeKey: string, state: Record<string, boolean>): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_PREFIX + typeKey, JSON.stringify(state));
  } catch {
    /* quota or privacy mode — ignore */
  }
}

interface LegalRiskDetail {
  type: string;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  summary?: string;
  articles?: {
    article_ref: string;
    content: string;
    kind?: 'article' | 'precedent';
    /** B 단계 — backend LLM 풀어쓰기 결과 (케이스 맞춤 1~2문장). */
    explanation?: string;
  }[];
  checklist?: LegalChecklistItem[];
  recommendation?: string;
}

interface LegalDrawerProps {
  risk: LegalRiskDetail | null;
  open: boolean;
  onClose: () => void;
}

const RISK_BADGE: Record<string, { cls: string; label: string }> = {
  HIGH: { cls: 'bg-danger/10 text-danger border-danger/30', label: '필수이행' },
  MEDIUM: { cls: 'bg-warning/10 text-warning border-warning/30', label: '확인필요' },
  LOW: { cls: 'bg-success/10 text-success border-success/30', label: '참고사항' },
};

export function LegalDrawer({ risk, open, onClose }: LegalDrawerProps) {
  const typeKey = risk?.type ?? '';
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!open || !typeKey) return;
    setChecked(loadChecked(typeKey));
  }, [open, typeKey]);

  const toggleItem = useCallback(
    (itemKey: string) => {
      setChecked((prev) => {
        const next = { ...prev, [itemKey]: !prev[itemKey] };
        if (typeKey) saveChecked(typeKey, next);
        return next;
      });
    },
    [typeKey],
  );

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

  if (typeof document === 'undefined') return null;
  return createPortal(
    <AnimatePresence>
      {open && risk && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-30 bg-black/50"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="legal-drawer-title"
            className="fixed right-0 top-20 bottom-0 z-40 flex w-full max-w-[480px] flex-col bg-card border-l border-border shadow-2xl"
          >
            <div className="flex shrink-0 items-start justify-between border-b-2 border-border bg-card p-6 shadow-sm">
              <div>
                <h2 id="legal-drawer-title" className="text-xl font-semibold text-foreground">
                  {risk.type}
                </h2>
                <span
                  className={`mt-2 inline-block rounded-full border px-2 py-0.5 text-xs font-bold ${RISK_BADGE[risk.risk_level]?.cls ?? ''}`}
                >
                  ● {RISK_BADGE[risk.risk_level]?.label ?? risk.risk_level}
                </span>
              </div>
              <button
                onClick={onClose}
                aria-label="닫기"
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-6 space-y-6">
              {/* 1. 평가 요약 — 사용자 친화 케이스 맞춤 1~2문장 (primary) */}
              {risk.summary && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                    이 케이스 평가
                  </h3>
                  <p className="text-sm text-foreground leading-relaxed font-medium">
                    {risk.summary}
                  </p>
                </section>
              )}

              {/* 2. AI 권고 — 행동 체크리스트 (primary) */}
              {risk.recommendation && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                    어떻게 해야 하나
                  </h3>
                  <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
                    {risk.recommendation}
                  </p>
                </section>
              )}

              {risk.checklist && risk.checklist.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                    창업 체크리스트
                  </h3>
                  <ul className="space-y-2">
                    {risk.checklist.map((item, i) => {
                      const itemKey = `${i}:${item.text}`;
                      const isChecked = !!checked[itemKey];
                      return (
                        <li key={itemKey} className="flex items-start gap-2 text-sm">
                          <input
                            id={`legal-check-${typeKey}-${i}`}
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleItem(itemKey)}
                            className="mt-1 shrink-0 cursor-pointer accent-primary"
                            aria-label={item.text}
                          />
                          <label
                            htmlFor={`legal-check-${typeKey}-${i}`}
                            className={`cursor-pointer select-none ${
                              isChecked ? 'text-muted-foreground line-through' : 'text-foreground'
                            }`}
                          >
                            {item.text}
                            {item.isRequired && <span className="ml-1 text-danger">*</span>}
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              )}

              {/* 3. 조문/판례 — secondary, default 접힘 (사용자 요청 시만 펼침) */}
              {(() => {
                const allArticles = risk.articles ?? [];
                const lawArticles = allArticles.filter((a) => (a.kind ?? 'article') === 'article');
                const precedents = allArticles.filter((a) => a.kind === 'precedent');
                if (lawArticles.length === 0 && precedents.length === 0) return null;
                return (
                  <details className="rounded border border-border bg-muted/30">
                    <summary className="cursor-pointer select-none p-3 text-sm font-semibold text-muted-foreground hover:bg-muted/50">
                      조문 / 판례 원문 보기 ({lawArticles.length + precedents.length}건)
                    </summary>
                    <div className="space-y-4 p-4">
                      {lawArticles.length > 0 && (
                        <section>
                          <h4 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
                            조항 본문
                          </h4>
                          <div className="space-y-3">
                            {lawArticles.map((a, i) => (
                              <div key={`art-${i}`} className="border-l-2 border-primary pl-4 py-2">
                                <div className="text-sm font-semibold text-primary">
                                  {a.article_ref}
                                </div>
                                {/* B 단계: explanation primary — 케이스 맞춤 풀어쓰기 (큰 글씨). */}
                                {a.explanation && (
                                  <div className="mt-1 text-sm text-foreground font-medium leading-relaxed">
                                    {a.explanation}
                                  </div>
                                )}
                                {/* 조문 원문은 secondary — explanation 있으면 details 토글, 없으면 fallback 으로 직접 노출. */}
                                {a.explanation ? (
                                  <details className="mt-2">
                                    <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                                      조문 원문 보기
                                    </summary>
                                    <div className="mt-1 text-xs text-muted-foreground whitespace-pre-line leading-relaxed">
                                      {a.content.length > 300
                                        ? a.content.slice(0, 300) + '…'
                                        : a.content}
                                    </div>
                                  </details>
                                ) : (
                                  <div className="mt-1 text-xs text-muted-foreground whitespace-pre-line leading-relaxed">
                                    {a.content.length > 300
                                      ? a.content.slice(0, 300) + '…'
                                      : a.content}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </section>
                      )}

                      {precedents.length > 0 && (
                        <section>
                          <h4 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
                            참고 판례
                          </h4>
                          <div className="space-y-3">
                            {precedents.map((a, i) => (
                              <div
                                key={`prec-${i}`}
                                className="border-l-2 border-warning/60 pl-4 py-2 bg-warning/5 rounded"
                              >
                                <div className="flex items-center gap-1 text-sm font-semibold text-warning">
                                  <span aria-hidden="true">⚖</span>
                                  <span>{a.article_ref}</span>
                                </div>
                                {/* B 단계: explanation primary — 케이스 맞춤 풀어쓰기. */}
                                {a.explanation && (
                                  <div className="mt-1 text-sm text-foreground font-medium leading-relaxed">
                                    {a.explanation}
                                  </div>
                                )}
                                {a.explanation ? (
                                  <details className="mt-2">
                                    <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                                      판례 원문 보기
                                    </summary>
                                    <div className="mt-1 text-xs text-muted-foreground whitespace-pre-line leading-relaxed">
                                      {a.content.length > 300
                                        ? a.content.slice(0, 300) + '…'
                                        : a.content}
                                    </div>
                                  </details>
                                ) : (
                                  <div className="mt-1 text-xs text-muted-foreground whitespace-pre-line leading-relaxed">
                                    {a.content.length > 300
                                      ? a.content.slice(0, 300) + '…'
                                      : a.content}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </section>
                      )}
                    </div>
                  </details>
                );
              })()}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}
