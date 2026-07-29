import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { PartOut } from "../api/types";

const LONG_PRESS_MS = 250;
/** A press that wanders this far is a scroll, not a long-press. */
const LONG_PRESS_SLOP_PX = 10;

/**
 * What a tap on a card does.
 * - `find`: confirm the whole part line present, or clear it again. The sorting workflow.
 * - `missing`: mark one more piece gone, for annotating a set already sorted.
 */
export type GridMode = "find" | "missing";

interface PartCardProps {
  part: PartOut;
  mode: GridMode;
  /** Emits the intended found-count change; the grid clamps it before it reaches the server. */
  onMark: (foundDelta: number) => void;
  /** Long-press in find mode, for the "found 2 of 4" case. */
  onRequestStepper: () => void;
}

function useLongPress(onLongPress: () => void, enabled: boolean) {
  const timer = useRef<number | null>(null);
  const origin = useRef<{ x: number; y: number } | null>(null);
  const fired = useRef(false);

  const clear = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    origin.current = null;
  };

  useEffect(() => clear, []);

  return {
    /** True when the press already ran the long-press action, so the trailing click is a no-op. */
    consumedClick: () => {
      const consumed = fired.current;
      fired.current = false;
      return consumed;
    },
    handlers: {
      onPointerDown: (event: ReactPointerEvent) => {
        if (!enabled || event.button !== 0) return;
        fired.current = false;
        origin.current = { x: event.clientX, y: event.clientY };
        timer.current = window.setTimeout(() => {
          fired.current = true;
          timer.current = null;
          onLongPress();
        }, LONG_PRESS_MS);
      },
      onPointerMove: (event: ReactPointerEvent) => {
        if (timer.current === null || !origin.current) return;
        const { x, y } = origin.current;
        if (
          Math.abs(event.clientX - x) > LONG_PRESS_SLOP_PX ||
          Math.abs(event.clientY - y) > LONG_PRESS_SLOP_PX
        ) {
          clear();
        }
      },
      onPointerUp: clear,
      onPointerLeave: clear,
      onPointerCancel: clear,
      // Suppress the touch callout so a long-press doesn't open the OS context menu instead.
      onContextMenu: (event: ReactMouseEvent) => event.preventDefault(),
    },
  };
}

function CheckIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 8.5l3.5 3.5L13 5" />
    </svg>
  );
}

export function PartCard({
  part,
  mode,
  onMark,
  onRequestStepper,
}: PartCardProps) {
  const [loaded, setLoaded] = useState(false);
  const {
    quantity_found: found,
    quantity_required: required,
    quantity_unaccounted: unaccounted,
  } = part;
  const fullyFound = part.is_fully_found;
  const partial = found > 0 && !fullyFound;

  // Find mode is a checkbox over the whole line: tap confirms every copy, tap again clears it.
  // Missing mode walks the count down one piece at a time.
  const tapDelta =
    mode === "find" ? (fullyFound ? -required : required - found) : -1;
  const tapDisabled = mode === "missing" && found <= 0;

  const longPress = useLongPress(
    onRequestStepper,
    mode === "find" && required > 1,
  );

  const cardLabel =
    mode === "find"
      ? `${part.part_num} ${part.color_name}, ${found} of ${required} found.` +
        (fullyFound ? " Clear this line." : ` Confirm all ${required} present.`)
      : `${part.part_num} ${part.color_name}, ${unaccounted} of ${required} unaccounted for.` +
        (tapDisabled
          ? " Nothing left to mark missing."
          : " Mark one more missing.");

  const cardHint =
    mode === "find"
      ? fullyFound
        ? "Tap to clear this line"
        : required > 1
          ? `Tap to confirm all ${required} present, long-press for a partial count`
          : "Tap to confirm present"
      : tapDisabled
        ? "Nothing left to mark missing"
        : "Tap to mark one more missing";

  const borderClass = fullyFound
    ? "border-green-300 bg-green-50"
    : mode === "missing" && unaccounted > 0
      ? "border-red-300 bg-red-50"
      : partial
        ? "border-amber-300 bg-amber-50"
        : "border-gray-300 bg-white";

  return (
    <div
      className={`relative flex flex-col gap-1 rounded border p-1.5 text-left ${borderClass}`}
    >
      {/* The whole card is the tap target. It overlays the content, which ignores pointers, and
          sits below the corner badge so the badge's own tap wins. */}
      <button
        type="button"
        aria-label={cardLabel}
        title={cardHint}
        disabled={tapDisabled}
        onClick={() => {
          if (longPress.consumedClick()) return;
          onMark(tapDelta);
        }}
        {...longPress.handlers}
        className="absolute inset-0 z-10 cursor-pointer touch-manipulation rounded focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:outline-none disabled:cursor-default"
      />

      <div className="pointer-events-none flex flex-col gap-1 select-none">
        <div className="relative aspect-square w-full overflow-hidden rounded bg-gray-100">
          {part.image_url && (
            <img
              src={part.image_url}
              alt={part.part_name}
              loading="lazy"
              onLoad={() => setLoaded(true)}
              className={`h-full w-full object-contain transition-opacity ${loaded ? "opacity-100" : "opacity-0"} ${
                fullyFound ? "opacity-50" : ""
              }`}
            />
          )}
          {!loaded && (
            <div className="absolute inset-0 animate-pulse bg-gray-200" />
          )}
        </div>

        <div className="font-mono text-[11px] leading-tight text-gray-700">
          <div className="truncate">
            {part.part_num} {part.color_name}
          </div>
          <div
            className={
              fullyFound
                ? "font-bold text-green-700"
                : partial
                  ? "font-bold text-amber-700"
                  : ""
            }
          >
            {found} of {required} found
          </div>
        </div>
      </div>

      {/* Found lines get a check; in missing mode the outstanding count is a tappable badge that
          gives pieces back one at a time. */}
      {fullyFound ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute top-1 right-1 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-green-600 text-white"
        >
          <CheckIcon />
        </span>
      ) : mode === "missing" ? (
        <button
          type="button"
          aria-label={`${unaccounted} of ${part.part_num} ${part.color_name} unaccounted for. Mark one found.`}
          title="Tap to mark one found"
          onClick={() => onMark(1)}
          className="absolute top-1 right-1 z-20 flex h-6 min-w-6 items-center justify-center rounded-full bg-red-600 px-1.5 font-mono text-[11px] font-bold text-white transition active:scale-90 focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:outline-none"
        >
          {unaccounted}
        </button>
      ) : (
        partial && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute top-1 right-1 z-20 flex h-6 min-w-6 items-center justify-center rounded-full bg-amber-500 px-1.5 font-mono text-[11px] font-bold text-white"
          >
            {found}
          </span>
        )
      )}
    </div>
  );
}
