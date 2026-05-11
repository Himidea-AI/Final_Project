/**
 * ClosureRiskDetailModal — 동별 폐업위험도 "분석 상세" 모달
 *
 * 메인 카드는 단순(점수 + 신호 3개)로 두고, 두 분석 관점(과거 데이터 / 최근 추세)
 * 각각의 위험 신호 5개와 자연어 요약을 깊이 보고 싶을 때 여기서 펼쳐 봄.
 *
 * 내부적으로 LGBM(과거 패턴) / TCN(시계열 흐름) 결과를 사용하지만,
 * 사용자 라벨에서 모델명은 노출하지 않음 — "과거 데이터 분석" / "최근 추세 분석".
 */

import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { BrainCircuit, X } from 'lucide-react';
import type { ClosureRisk } from '../../../../types';
import { ClosureSignalsBar } from './ClosureSignalsBar';

interface Props {
  open: boolean;
  district: string;
  closure: ClosureRisk | null;
  onClose: () => void;
}

export function ClosureRiskDetailModal({ open, district, closure, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onEsc = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onEsc);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onEsc);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {open && closure && (
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
                <BrainCircuit className="text-primary" size={20} />
                {district} · 폐업위험도 분석 상세
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

            <div className="p-8 max-h-[70vh] overflow-y-auto space-y-6">
              <p className="text-[0.75rem] text-muted-foreground leading-relaxed">
                두 가지 분석 관점으로 위험 요인을 살펴봅니다.{' '}
                <span className="font-bold text-foreground">과거 데이터 분석</span>은 유사 상권의
                폐업 패턴 학습 결과이고,{' '}
                <span className="font-bold text-foreground">최근 추세 분석</span>은 최근 분기들의
                흐름 변화를 본 결과입니다.
              </p>

              {/* 과거 데이터 분석 (LGBM) */}
              <section>
                <div className="flex items-center gap-2 mb-2">
                  <span className="h-2 w-2 rounded-full bg-primary" />
                  <h4 className="text-xs font-black text-foreground uppercase tracking-widest">
                    과거 데이터 분석
                  </h4>
                </div>
                {closure.summary_lgbm?.[0] && (
                  <p className="text-[0.75rem] text-foreground leading-relaxed mb-2">
                    {closure.summary_lgbm[0]}
                  </p>
                )}
                <ClosureSignalsBar
                  signals={closure.top_signals_lgbm}
                  title="과거 패턴 위험 신호 TOP 5"
                  accent="lgbm"
                />
              </section>

              {/* 최근 추세 분석 (TCN) */}
              <section>
                <div className="flex items-center gap-2 mb-2">
                  <span className="h-2 w-2 rounded-full bg-chart-3" />
                  <h4 className="text-xs font-black text-foreground uppercase tracking-widest">
                    최근 추세 분석
                  </h4>
                </div>
                {closure.summary_tcn?.[0] && (
                  <p className="text-[0.75rem] text-foreground leading-relaxed mb-2">
                    {closure.summary_tcn[0]}
                  </p>
                )}
                <ClosureSignalsBar
                  signals={closure.top_signals_tcn}
                  title="최근 추세 위험 신호 TOP 5"
                  accent="tcn"
                />
              </section>

              <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
                ※ 위험 신호는 빨강(↑)일수록 폐업 위험을 높이는 요인, 초록(↓)일수록 낮추는
                요인입니다. 위험 점수는 두 가지 분석을 모두 반영해 산출됩니다.
              </p>
            </div>

            <div className="p-6 bg-card/50 border-t border-border flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="px-6 py-2.5 bg-card text-foreground font-bold rounded-xl hover:bg-muted transition-colors"
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
