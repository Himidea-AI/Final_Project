import { useToastStore } from '../../stores/toastStore';
import { X, CheckCircle2, AlertCircle, Info } from 'lucide-react';

const VARIANT_STYLES: Record<string, { ring: string; icon: JSX.Element }> = {
  success: {
    ring: 'ring-success/60',
    icon: <CheckCircle2 className="h-5 w-5 text-success" />,
  },
  error: {
    ring: 'ring-danger/60',
    icon: <AlertCircle className="h-5 w-5 text-danger" />,
  },
  info: {
    ring: 'ring-border',
    icon: <Info className="h-5 w-5 text-foreground" />,
  },
};

export function ToastHost() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div
      role="region"
      aria-live="polite"
      aria-label="알림"
      className="pointer-events-none fixed top-6 right-6 z-[60] flex flex-col gap-2"
    >
      {toasts.map((t) => {
        const style = VARIANT_STYLES[t.variant] ?? VARIANT_STYLES.info;
        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-lg bg-card px-4 py-3 shadow-lg ring-1 ${style.ring} min-w-[280px] max-w-sm text-foreground`}
          >
            {style.icon}
            <div className="flex-1">
              <div className="text-sm font-semibold">{t.title}</div>
              {t.description && (
                <div className="mt-0.5 text-xs text-muted-foreground">{t.description}</div>
              )}
              {t.action
                ? ((action) => (
                    <button
                      onClick={() => {
                        action.onClick();
                        dismiss(t.id);
                      }}
                      className="mt-2 text-xs font-medium text-primary hover:text-primary/80"
                    >
                      {action.label} →
                    </button>
                  ))(t.action)
                : null}
            </div>
            <button
              onClick={() => dismiss(t.id)}
              className="text-muted-foreground hover:text-foreground"
              aria-label="닫기"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
