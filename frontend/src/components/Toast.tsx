/**
 * Toast — 성공/에러 알림 (3초 후 자동 사라짐)
 */

import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { CheckCircle2, XCircle, Info } from 'lucide-react';

type ToastType = 'success' | 'error' | 'info';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextType {
  showToast: (type: ToastType, message: string) => void;
}

const ToastContext = createContext<ToastContextType>({
  showToast: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}

let toastId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}

      {/* Toast Container */}
      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2">
        {toasts.map((toast) => (
          <ToastCard
            key={toast.id}
            toast={toast}
            onClose={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ toast, onClose }: { toast: ToastItem; onClose: () => void }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(() => setVisible(false), 2700);
    return () => clearTimeout(timer);
  }, []);

  const config = {
    success: {
      icon: <CheckCircle2 className="w-4 h-4 text-success" />,
      border: 'border-success/30',
      bg: 'bg-success/5',
    },
    error: {
      icon: <XCircle className="w-4 h-4 text-danger" />,
      border: 'border-danger/30',
      bg: 'bg-danger/5',
    },
    info: {
      icon: <Info className="w-4 h-4 text-primary" />,
      border: 'border-primary/30',
      bg: 'bg-primary/5',
    },
  }[toast.type];

  return (
    <div
      onClick={onClose}
      className={`flex items-center gap-3 px-4 py-3 rounded-xl border bg-card shadow-2xl cursor-pointer transition-all duration-300 ${config.border} ${
        visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'
      }`}
    >
      {config.icon}
      <p className="text-xs font-medium text-foreground">{toast.message}</p>
    </div>
  );
}
