import { useEffect, useRef, useState, type FormEvent } from "react";

interface ChangeFigNumDialogProps {
  currentFigNum: string;
  currentFigName: string;
  /** Rejected ids come back from the server (unknown fig, catalog down) and are shown in place. */
  error: string | null;
  isPending: boolean;
  onSubmit: (figNum: string) => void;
  onCancel: () => void;
}

/**
 * Corrects the catalog id a loose minifig is filed under.
 *
 * The id is pre-filled and selected, since a correction is usually a small edit to what is already
 * there. What it will cost is stated up front rather than confirmed afterwards: the parts list is
 * refetched from Rebrickable, so whatever was checked off against the old one is gone.
 */
export function ChangeFigNumDialog({
  currentFigNum,
  currentFigName,
  error,
  isPending,
  onSubmit,
  onCancel,
}: ChangeFigNumDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [figNum, setFigNum] = useState(currentFigNum);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  const trimmed = figNum.trim();
  const canSubmit = trimmed.length > 0 && trimmed !== currentFigNum && !isPending;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (canSubmit) onSubmit(trimmed);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div aria-hidden="true" onClick={onCancel} className="absolute inset-0 bg-gray-900/40" />
      <form
        onSubmit={handleSubmit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="change-fig-num-title"
        className="relative w-full max-w-sm rounded border border-gray-300 bg-white p-4 shadow-xl"
      >
        <h2 id="change-fig-num-title" className="text-base font-bold">
          Change this minifigure's fig ID
        </h2>
        <p className="mt-1.5 text-sm text-gray-600">
          Currently filed as <span className="font-semibold">{currentFigName}</span>{" "}
          <span className="font-mono">({currentFigNum})</span>. A new ID is looked up on Rebrickable and
          its parts list replaces the current one, so pieces already checked off start over.
        </p>

        <label htmlFor="change-fig-num-input" className="mt-3 block text-xs font-semibold text-gray-700">
          Rebrickable fig ID
        </label>
        <input
          id="change-fig-num-input"
          ref={inputRef}
          value={figNum}
          onChange={(event) => setFigNum(event.target.value)}
          placeholder="fig-000068"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          className="ui-field mt-1 w-full px-2 py-1.5 font-mono text-sm"
        />

        <p className="mt-2 text-xs text-gray-500">
          If one of your sets is still waiting for this minifigure, it is handed to that set and checked
          off as found there instead of staying loose.
        </p>

        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="ui-control ui-control-secondary ui-control-md"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="ui-control ui-control-primary ui-control-md font-semibold"
          >
            {isPending ? "Looking up..." : "Change fig ID"}
          </button>
        </div>
      </form>
    </div>
  );
}
