interface UndoToastProps {
  message: string;
  onUndo: () => void;
  onDismiss: () => void;
}

/** Bottom-anchored confirmation of the last change, so a stray tap on a card costs nothing. */
export function UndoToast({ message, onUndo, onDismiss }: UndoToastProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 bottom-3 z-50 flex justify-center px-3 print:hidden"
    >
      <div className="flex items-center gap-3 rounded border border-gray-700 bg-gray-900 py-1.5 pr-1.5 pl-3 text-sm text-white shadow-lg">
        <span className="font-mono text-xs">{message}</span>
        <button
          type="button"
          onClick={onUndo}
          className="ui-control border-gray-500 px-2 py-0.5 text-xs font-semibold hover:border-gray-300 hover:bg-gray-800"
        >
          Undo
        </button>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="ui-control border-transparent px-1 text-gray-400 hover:bg-gray-800 hover:text-white"
        >
          &#10005;
        </button>
      </div>
    </div>
  );
}
