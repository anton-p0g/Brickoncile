import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import type { PartOut } from "../api/types";

interface PartQuantityStepperProps {
  part: PartOut;
  /** Emits a found-count delta, same contract as the card itself. */
  onMark: (foundDelta: number) => void;
  onClose: () => void;
}

/**
 * Partial-count escape hatch for a part line: "I found 2 of the 4". Reached by long-pressing a card
 * in find mode, since finding every copy at once is the common case and needs no dialog.
 *
 * The count is a text field, pre-selected on open, so a line with dozens of copies can be answered
 * by typing the number rather than tapping the stepper that many times. The draft is what every
 * control reads and writes; each commit reconciles it with the part's real count as a delta.
 */
export function PartQuantityStepper({ part, onMark, onClose }: PartQuantityStepperProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState(() => String(part.quantity_found));

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Ready to overtype immediately: the existing count is selected, not just focused.
  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  /** Empty or half-typed input counts as zero, so +/- still have something to work from. */
  const draftValue = draft === "" ? 0 : Number(draft);

  /**
   * Push a target count to the parent as a delta. Re-committing the same value is a no-op there,
   * so the blur that follows Enter or a button press costs nothing.
   */
  function commit(target: number) {
    const clamped = Math.max(0, Math.min(part.quantity_required, Math.round(target)));
    setDraft(String(clamped));
    onMark(clamped - part.quantity_found);
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const digits = event.target.value.replace(/[^0-9]/g, "");
    setDraft(digits);
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      commit(draftValue);
      onClose();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      commit(draftValue + 1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      commit(draftValue - 1);
    }
  }

  const atMax = draftValue >= part.quantity_required;
  const atMin = draftValue <= 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div aria-hidden="true" onClick={onClose} className="absolute inset-0 bg-gray-900/40" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`How many ${part.part_num} ${part.color_name} did you find?`}
        className="relative w-full max-w-xs rounded border border-gray-300 bg-white p-3 shadow-xl outline-none"
      >
        <div className="flex items-center gap-2">
          <div className="h-12 w-12 flex-shrink-0 overflow-hidden rounded bg-gray-100">
            {part.image_url && (
              <img src={part.image_url} alt="" className="h-full w-full object-contain" />
            )}
          </div>
          <div className="min-w-0">
            <div className="truncate font-mono text-xs font-bold">
              {part.part_num} {part.color_name}
            </div>
            <div className="truncate text-xs text-gray-500">{part.part_name}</div>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-center gap-3">
          <button
            type="button"
            aria-label="One fewer found"
            disabled={atMin}
            onClick={() => commit(draftValue - 1)}
            className="h-10 w-10 flex-shrink-0 rounded-full border border-gray-300 text-lg leading-none disabled:opacity-30"
          >
            &minus;
          </button>
          <span className="flex items-baseline gap-1">
            <input
              ref={inputRef}
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              enterKeyHint="done"
              aria-label={`Number of ${part.part_num} ${part.color_name} found, out of ${part.quantity_required}`}
              value={draft}
              onChange={handleChange}
              onFocus={(event) => event.target.select()}
              onBlur={() => commit(draftValue)}
              onKeyDown={handleKeyDown}
              className="w-16 rounded border border-gray-300 px-1 py-1 text-center font-mono text-lg font-bold focus:border-gray-900 focus:outline-none"
            />
            <span className="text-sm text-gray-500">of {part.quantity_required}</span>
          </span>
          <button
            type="button"
            aria-label="One more found"
            disabled={atMax}
            onClick={() => commit(draftValue + 1)}
            className="h-10 w-10 flex-shrink-0 rounded-full border border-gray-300 text-lg leading-none disabled:opacity-30"
          >
            +
          </button>
        </div>

        <div className="mt-3 flex justify-between gap-2">
          <button
            type="button"
            onClick={() => commit(0)}
            className="rounded border border-gray-300 px-2 py-1 text-xs hover:border-gray-500"
          >
            None found
          </button>
          <button
            type="button"
            onClick={() => commit(part.quantity_required)}
            className="rounded border border-green-600 bg-green-600 px-2 py-1 text-xs font-semibold text-white hover:bg-green-700"
          >
            All {part.quantity_required} found
          </button>
        </div>

        <button
          type="button"
          onClick={() => {
            commit(draftValue);
            onClose();
          }}
          className="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-xs hover:border-gray-500"
        >
          Done
        </button>
      </div>
    </div>
  );
}
