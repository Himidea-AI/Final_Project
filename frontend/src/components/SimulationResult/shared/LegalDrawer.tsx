import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { useEffect } from 'react';
import type { LegalChecklistItem } from '../../../types';

interface LegalRiskDetail {
  type: string;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  articles?: { article_ref: string; content: string }[];
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

  return (
    <AnimatePresence>
      {open && risk && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/50"
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
            className="fixed right-0 top-0 z-50 h-full w-full max-w-[480px] overflow-y-auto bg-card border-l border-border"
          >
            <div className="flex items-start justify-between border-b border-border p-6">
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

            <div className="p-6 space-y-6">
              {risk.recommendation && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                    AI 권고
                  </h3>
                  <p className="text-sm text-foreground leading-relaxed">{risk.recommendation}</p>
                </section>
              )}

              {risk.checklist && risk.checklist.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                    창업 체크리스트
                  </h3>
                  <ul className="space-y-2">
                    {risk.checklist.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          disabled
                          className="mt-1 shrink-0 cursor-not-allowed"
                          aria-label={item.text}
                        />
                        <span className="text-foreground">
                          {item.text}
                          {item.isRequired && <span className="ml-1 text-danger">*</span>}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {risk.articles && risk.articles.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                    조항 본문
                  </h3>
                  <div className="space-y-3">
                    {risk.articles.map((a, i) => (
                      <div key={i} className="border-l-2 border-primary pl-4 py-2">
                        <div className="text-sm font-semibold text-primary">{a.article_ref}</div>
                        <div className="mt-1 text-sm text-foreground whitespace-pre-line leading-relaxed">
                          {a.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
