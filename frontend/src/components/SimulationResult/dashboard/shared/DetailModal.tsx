import { BrainCircuit, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useEffect } from 'react';
import { createPortal } from 'react-dom';

export interface DetailModalContent {
  title: string;
  content: string;
}

interface DetailModalProps {
  modalContent: DetailModalContent | null;
  onClose: () => void;
}

/**
 * 전역 상세 모달 — 에이전트 원본 narrative, 법률 조문, 방법론 설명 등
 * AnimatePresence 로 등장/퇴장 애니메이션. ESC 닫기 지원.
 */
export function DetailModal({ modalContent, onClose }: DetailModalProps) {
  useEffect(() => {
    if (!modalContent) return;
    const onEsc = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onEsc);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onEsc);
      document.body.style.overflow = '';
    };
  }, [modalContent, onClose]);

  // SimulatorDashboard 컨테이너(absolute inset-0 z-40)가 자체 stacking context를 만들어,
  // 그 안의 z-[100]도 외부 z-50(글로벌 header)을 못 이김. document.body로 portal하여
  // DOM 트리상 SimulatorDashboard 밖으로 빠져나와 글로벌 header와 형제 stacking.
  if (typeof document === 'undefined') return null;
  return createPortal(
    <AnimatePresence>
      {modalContent && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 backdrop-blur-md bg-black/60">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-card border border-border w-full max-w-3xl rounded-3xl overflow-hidden shadow-2xl"
            role="dialog"
            aria-modal="true"
          >
            <div className="p-6 border-b border-border flex justify-between items-center bg-card/50">
              <h3 className="text-xl font-black text-foreground flex items-center gap-3 text-left">
                <BrainCircuit className="text-primary" size={20} /> {modalContent.title}
              </h3>
              <button
                type="button"
                onClick={onClose}
                aria-label="닫기"
                className="p-2 hover:bg-card rounded-full transition-colors"
              >
                <X size={20} className="text-muted-foreground" />
              </button>
            </div>
            <div className="p-8 max-h-[70vh] overflow-y-auto text-foreground leading-relaxed space-y-4 font-medium text-left">
              {modalContent.content.split('\n').map((line, i) => (
                <p key={i}>{line}</p>
              ))}
            </div>
            <div className="p-6 bg-card/50 border-t border-border flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="px-6 py-2.5 bg-card text-white font-bold rounded-xl hover:bg-muted transition-colors"
              >
                닫기
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
