import { create } from 'zustand';

export type ToastVariant = 'success' | 'error' | 'info';

export interface Toast {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  durationMs?: number;
  /**
   * 동일 dedupeKey 의 기존 토스트는 새 push 시 제거됨 (replace + duration 재시작).
   * 재시도 연타로 같은 토스트가 stack 누적되는 회귀 방지용.
   */
  dedupeKey?: string;
}

interface ToastState {
  toasts: Toast[];
  push: (t: Omit<Toast, 'id'>) => string;
  dismiss: (id: string) => void;
}

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (t) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const toast: Toast = { durationMs: 5000, ...t, id };
    const prev = get().toasts;
    const next = toast.dedupeKey ? prev.filter((x) => x.dedupeKey !== toast.dedupeKey) : prev;
    set({ toasts: [...next, toast] });
    if (toast.durationMs && toast.durationMs > 0) {
      setTimeout(() => get().dismiss(id), toast.durationMs);
    }
    return id;
  },
  dismiss: (id) => {
    set({ toasts: get().toasts.filter((x) => x.id !== id) });
  },
}));
