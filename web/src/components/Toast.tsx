import { useEffect } from "react";

export type ToastKind = "success" | "error" | "info";

export interface ToastMessage {
  kind: ToastKind;
  text: string;
}

interface ToastProps {
  toast: ToastMessage | null;
  onDismiss: () => void;
}

const accent: Record<ToastKind, string> = {
  success: "before:bg-brand-500",
  error: "before:bg-red-500",
  info: "before:bg-sky-500",
};

/** Transient notification. Auto-dismisses after a few seconds. */
export function Toast({ toast, onDismiss }: ToastProps) {
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(onDismiss, toast.kind === "error" ? 7000 : 4000);
    return () => clearTimeout(timer);
  }, [toast, onDismiss]);

  if (!toast) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`animate-rise fixed bottom-5 right-5 z-50 flex max-w-sm items-start gap-3
        overflow-hidden rounded-2xl border border-line bg-surface/95 py-3.5 pl-5 pr-3
        shadow-lift backdrop-blur-sm before:absolute before:inset-y-0 before:left-0
        before:w-1.5 before:content-[''] ${accent[toast.kind]}`}
    >
      <span className="text-sm leading-snug text-ink">{toast.text}</span>
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={onDismiss}
        className="-mr-1 grid h-6 w-6 shrink-0 cursor-pointer place-items-center rounded-full
          text-faint transition-colors hover:bg-paper hover:text-ink"
      >
        ×
      </button>
    </div>
  );
}
