import { useEffect, useRef, useState, type ReactNode } from "react";

interface ConfirmDialogProps {
  title: string;
  body: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  isPending?: boolean;
  requiredConfirmationText?: string;
}

/** Modal confirmation for an irreversible action. Typed confirmations focus the required field;
 *  simpler confirmations put initial focus on Cancel. */
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  onConfirm,
  onCancel,
  isPending,
  requiredConfirmationText,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmationRef = useRef<HTMLInputElement>(null);
  const [confirmationText, setConfirmationText] = useState("");

  useEffect(() => {
    if (requiredConfirmationText !== undefined) confirmationRef.current?.focus();
    else cancelRef.current?.focus();
  }, [requiredConfirmationText]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        aria-hidden="true"
        onClick={onCancel}
        className="absolute inset-0 bg-gray-900/40"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="relative w-full max-w-sm rounded border border-gray-300 bg-white p-4 shadow-xl"
      >
        <h2 id="confirm-dialog-title" className="text-base font-bold">
          {title}
        </h2>
        <div className="mt-1.5 text-sm text-gray-600">{body}</div>
        {requiredConfirmationText !== undefined && (
          <label className="mt-3 block text-sm font-medium text-gray-700">
            Type <span className="font-semibold text-gray-900">{requiredConfirmationText}</span> to confirm
            <input
              ref={confirmationRef}
              value={confirmationText}
              onChange={(event) => setConfirmationText(event.target.value)}
              disabled={isPending}
              autoComplete="off"
              spellCheck={false}
              className="ui-field mt-1 w-full px-3 py-2 text-sm font-normal"
            />
          </label>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            className="ui-control ui-control-secondary ui-control-md"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={
              isPending ||
              (requiredConfirmationText !== undefined && confirmationText !== requiredConfirmationText)
            }
            className="ui-control ui-control-md border-red-600 bg-red-600 font-semibold text-white hover:border-red-700 hover:bg-red-700"
          >
            {isPending ? "Working..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
