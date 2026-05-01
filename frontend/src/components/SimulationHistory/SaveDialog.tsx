import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';

interface SaveDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (clientName: string) => Promise<void> | void;
  meta: {
    brandName: string;
    district: string;
    managerName: string;
  };
  isSaving?: boolean;
  errorMessage?: string | null;
}

export function SaveDialog({
  open,
  onClose,
  onConfirm,
  meta,
  isSaving = false,
  errorMessage = null,
}: SaveDialogProps) {
  const [clientName, setClientName] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      setClientName('');
      return;
    }
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSaving) onClose();
    };
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleEsc);
    const t = setTimeout(() => inputRef.current?.focus(), 60);
    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEsc);
      clearTimeout(t);
    };
  }, [open, onClose, isSaving]);

  const trimmed = clientName.trim();
  const canSubmit = trimmed.length > 0 && !isSaving;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    await onConfirm(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && canSubmit) {
      e.preventDefault();
      void handleSubmit();
    }
  };

  const nowLabel = new Date().toLocaleString('ko-KR', { hour12: false });

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/60 backdrop-blur-sm"
          onClick={() => {
            if (!isSaving) onClose();
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="save-dialog-title"
            onClick={(e) => e.stopPropagation()}
            className="w-[min(92vw,440px)] rounded-xl border border-stone-700 bg-stone-900 p-6 shadow-2xl"
          >
            <div className="flex items-start justify-between">
              <div>
                <h2 id="save-dialog-title" className="text-lg font-semibold text-stone-100">
                  시뮬레이션 결과 저장
                </h2>
                <p className="mt-1 text-sm text-stone-400">
                  이 시뮬레이션을 상담한 고객님의 성함을 입력해주세요.
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                disabled={isSaving}
                aria-label="닫기"
                className="text-stone-400 transition-colors hover:text-stone-100 disabled:opacity-40"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-5 space-y-4">
              <div>
                <label
                  htmlFor="client-name-input"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-widest text-stone-400"
                >
                  고객님 성함
                </label>
                <input
                  id="client-name-input"
                  ref={inputRef}
                  type="text"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isSaving}
                  placeholder="예: 김철수"
                  maxLength={100}
                  className="w-full rounded-md border border-stone-700 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder:text-stone-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/60 disabled:opacity-50"
                />
              </div>

              <div className="rounded-md border border-stone-700 bg-stone-800/50 p-3 text-xs text-stone-400">
                <div className="flex items-center gap-2">
                  <span>📅 저장 날짜</span>
                  <span className="text-stone-300">{nowLabel}</span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span>🏪 브랜드</span>
                  <span className="text-stone-300">
                    {meta.brandName} — {meta.district}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span>👤 매니저</span>
                  <span className="text-stone-300">{meta.managerName}</span>
                </div>
              </div>

              {errorMessage && (
                <div className="rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                  {errorMessage}
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isSaving}
                className="rounded-md border border-stone-700 bg-stone-800 px-4 py-2 text-sm font-medium text-stone-300 hover:bg-stone-700 disabled:opacity-40"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="rounded-md bg-indigo-500 px-4 py-2 text-sm font-semibold text-stone-900 hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isSaving ? '저장 중…' : '저장'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
