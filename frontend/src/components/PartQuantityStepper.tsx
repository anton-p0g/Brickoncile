import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type RefObject,
} from "react";
import type { PartOut } from "../api/types";

interface PartQuantityStepperProps {
  part: PartOut;
  /** Saves both values together because broken is always a subset of found. */
  onSetCondition: (quantityFound: number, quantityBroken: number) => void;
  onClose: () => void;
}

/**
 * The secondary editor for a part line. Long-press works for every quantity and in both sorting
 * modes: uncommon conditions stay out of the fast tap path, but a single required piece can still
 * be recorded as broken.
 */
export function PartQuantityStepper({
  part,
  onSetCondition,
  onClose,
}: PartQuantityStepperProps) {
  const foundInputRef = useRef<HTMLInputElement>(null);
  const [foundDraft, setFoundDraft] = useState(() => String(part.quantity_found));
  const [brokenDraft, setBrokenDraft] = useState(() => String(part.quantity_broken));

  const numberFrom = (draft: string) => (draft === "" ? 0 : Number(draft));
  const foundValue = numberFrom(foundDraft);
  const brokenValue = numberFrom(brokenDraft);

  function normalized(found: number, broken: number) {
    const quantityFound = Math.max(
      0,
      Math.min(part.quantity_required, Math.round(found)),
    );
    const quantityBroken = Math.max(
      0,
      Math.min(quantityFound, Math.round(broken)),
    );
    return { quantityFound, quantityBroken };
  }

  function setCounts(found: number, broken: number) {
    const next = normalized(found, broken);
    setFoundDraft(String(next.quantityFound));
    setBrokenDraft(String(next.quantityBroken));
  }

  function adjustFound(delta: number) {
    const nextFound = Math.max(
      0,
      Math.min(part.quantity_required, foundValue + delta),
    );
    setCounts(nextFound, Math.min(brokenValue, nextFound));
  }

  function adjustBroken(delta: number) {
    const nextBroken = Math.max(
      0,
      Math.min(part.quantity_required, brokenValue + delta),
    );
    // Calling a piece broken also confirms it was physically found.
    setCounts(Math.max(foundValue, nextBroken), nextBroken);
  }

  function save() {
    const next = normalized(foundValue, brokenValue);
    onSetCondition(next.quantityFound, next.quantityBroken);
    onClose();
  }

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    foundInputRef.current?.focus();
    foundInputRef.current?.select();
  }, []);

  function handleFoundChange(event: ChangeEvent<HTMLInputElement>) {
    const digits = event.target.value.replace(/[^0-9]/g, "");
    const nextFound = numberFrom(digits);
    setFoundDraft(digits);
    if (brokenValue > nextFound) setBrokenDraft(String(nextFound));
  }

  function handleBrokenChange(event: ChangeEvent<HTMLInputElement>) {
    const digits = event.target.value.replace(/[^0-9]/g, "");
    const nextBroken = Math.min(part.quantity_required, numberFrom(digits));
    setBrokenDraft(digits);
    if (nextBroken > foundValue) setFoundDraft(String(nextBroken));
  }

  function handleInputKeyDown(
    event: ReactKeyboardEvent<HTMLInputElement>,
    kind: "found" | "broken",
  ) {
    if (event.key === "Enter") {
      event.preventDefault();
      save();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (kind === "found") adjustFound(1);
      else adjustBroken(1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      if (kind === "found") adjustFound(-1);
      else adjustBroken(-1);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 bg-gray-900/40"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Set found and broken counts for ${part.part_num} ${part.color_name}`}
        className="relative w-full max-w-xs rounded border border-gray-300 bg-white p-3 shadow-xl outline-none"
      >
        <div className="flex items-center gap-2">
          <div className="h-12 w-12 flex-shrink-0 overflow-hidden rounded bg-gray-100">
            {part.image_url && (
              <img
                src={part.image_url}
                alt=""
                className="h-full w-full object-contain"
              />
            )}
          </div>
          <div className="min-w-0">
            <div className="truncate font-mono text-xs font-bold">
              {part.part_num} {part.color_name}
            </div>
            <div className="truncate text-xs text-gray-500">
              {part.part_name}
            </div>
          </div>
        </div>

        <div className="mt-3 space-y-3">
          <CountRow
            label="Found"
            value={foundDraft}
            inputRef={foundInputRef}
            max={part.quantity_required}
            decrementDisabled={foundValue <= 0}
            incrementDisabled={foundValue >= part.quantity_required}
            onChange={handleFoundChange}
            onBlur={() => setCounts(foundValue, brokenValue)}
            onKeyDown={(event) => handleInputKeyDown(event, "found")}
            onDecrement={() => adjustFound(-1)}
            onIncrement={() => adjustFound(1)}
          />
          <CountRow
            label="Broken"
            value={brokenDraft}
            max={part.quantity_required}
            tone="broken"
            decrementDisabled={brokenValue <= 0}
            incrementDisabled={brokenValue >= part.quantity_required}
            onChange={handleBrokenChange}
            onBlur={() => setCounts(Math.max(foundValue, brokenValue), brokenValue)}
            onKeyDown={(event) => handleInputKeyDown(event, "broken")}
            onDecrement={() => adjustBroken(-1)}
            onIncrement={() => adjustBroken(1)}
          />
        </div>

        <p className="mt-2 text-[11px] text-gray-500">
          Broken pieces are included in the found count.
        </p>

        <div className="mt-3 flex justify-between gap-2">
          <button
            type="button"
            onClick={() => setCounts(0, 0)}
            className="ui-control ui-control-secondary px-2 py-1 text-xs"
          >
            None found
          </button>
          <button
            type="button"
            onClick={() => setCounts(part.quantity_required, brokenValue)}
            className="ui-control border-green-600 bg-green-600 px-2 py-1 text-xs font-semibold text-white hover:border-green-700 hover:bg-green-700"
          >
            All {part.quantity_required} found
          </button>
        </div>

        <div className="mt-2 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onClose}
            className="ui-control ui-control-secondary px-2 py-1 text-xs"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            className="ui-control border-gray-900 bg-gray-900 px-2 py-1 text-xs font-semibold text-white hover:border-gray-700 hover:bg-gray-700"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

interface CountRowProps {
  label: string;
  value: string;
  max: number;
  tone?: "broken";
  inputRef?: RefObject<HTMLInputElement | null>;
  decrementDisabled: boolean;
  incrementDisabled: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onBlur: () => void;
  onKeyDown: (event: ReactKeyboardEvent<HTMLInputElement>) => void;
  onDecrement: () => void;
  onIncrement: () => void;
}

function CountRow({
  label,
  value,
  max,
  tone,
  inputRef,
  decrementDisabled,
  incrementDisabled,
  onChange,
  onBlur,
  onKeyDown,
  onDecrement,
  onIncrement,
}: CountRowProps) {
  const toneClass = tone === "broken" ? "text-violet-700" : "text-gray-700";
  return (
    <div>
      <label className={`mb-1 block text-center text-xs font-semibold ${toneClass}`}>
        {label}
      </label>
      <div className="grid grid-cols-[2.5rem_5rem_2.5rem] items-start justify-center gap-3">
        <button
          type="button"
          aria-label={`One fewer ${label.toLowerCase()}`}
          disabled={decrementDisabled}
          onClick={onDecrement}
          className="ui-control ui-control-secondary mt-1.5 h-10 w-10 flex-shrink-0 text-lg leading-none disabled:opacity-30"
        >
          &minus;
        </button>
        <span className="flex w-20 flex-col items-center pt-1.5">
          <input
            ref={inputRef}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            enterKeyHint="done"
            aria-label={`${label} count`}
            value={value}
            onChange={onChange}
            onFocus={(event) => event.target.select()}
            onBlur={onBlur}
            onKeyDown={onKeyDown}
            className="ui-field w-20 px-1 py-1 text-center font-mono text-lg font-bold"
          />
          <span className="mt-0.5 text-xs leading-none text-gray-500">of {max}</span>
        </span>
        <button
          type="button"
          aria-label={`One more ${label.toLowerCase()}`}
          disabled={incrementDisabled}
          onClick={onIncrement}
          className="ui-control ui-control-secondary mt-1.5 h-10 w-10 flex-shrink-0 text-lg leading-none disabled:opacity-30"
        >
          +
        </button>
      </div>
    </div>
  );
}
