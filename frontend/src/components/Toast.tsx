import { useEffect } from "react";

export type ToastTone = "success" | "info" | "warning" | "error";

export interface ToastMessage {
  tone: ToastTone;
  text: string;
  /** Bumped on every new toast so repeating the same message restarts the auto-dismiss timer. */
  id: number;
}

interface ToastProps {
  toast: ToastMessage;
  onDismiss: () => void;
}

const TONE_CLASSES: Record<ToastTone, { border: string; dot: string }> = {
  success: { border: "border-green-600", dot: "bg-green-600" },
  info: { border: "border-gray-400", dot: "bg-gray-400" },
  warning: { border: "border-amber-500", dot: "bg-amber-500" },
  error: { border: "border-red-600", dot: "bg-red-600" },
};

/** Anything the user has to act on stays until dismissed; only plain confirmations time out. */
const SELF_DISMISSING: ToastTone[] = ["success", "info"];
const AUTO_DISMISS_MS = 4000;

/** Bottom-anchored confirmation that an action landed, so adding a set is never a silent no-op. */
export function Toast({ toast, onDismiss }: ToastProps) {
  const tone = TONE_CLASSES[toast.tone];

  useEffect(() => {
    if (!SELF_DISMISSING.includes(toast.tone)) return;
    const timer = setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [toast.id, toast.tone, onDismiss]);

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 bottom-3 z-50 flex justify-center px-3 print:hidden"
    >
      <div
        className={`flex max-w-lg items-start gap-2.5 rounded border-l-4 bg-white py-2 pr-1.5 pl-3 text-sm shadow-lg ${tone.border}`}
      >
        <span aria-hidden="true" className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} />
        <span className="py-0.5">{toast.text}</span>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="shrink-0 px-1 text-gray-400 hover:text-gray-900"
        >
          &#10005;
        </button>
      </div>
    </div>
  );
}
