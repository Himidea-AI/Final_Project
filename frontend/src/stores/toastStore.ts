import { create } from 'zustand';

export type ToastVariant = 'success' | 'error' | 'info';

export interface Toast {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  durationMs?: number;
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
    set({ toasts: [...get().toasts, toast] });
    if (toast.durationMs && toast.durationMs > 0) {
      setTimeout(() => get().dismiss(id), toast.durationMs);
    }
    return id;
  },
  dismiss: (id) => {
    set({ toasts: get().toasts.filter((x) => x.id !== id) });
  },
}));
