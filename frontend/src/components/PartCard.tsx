import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { PartOut } from "../api/types";
import { BrokenBrickIcon } from "./BrokenBrickIcon";

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
  const activePointer = useRef<number | null>(null);
  const startedAt = useRef(0);
  const suppressNextClick = useRef(false);

  const clearTimer = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  };

  const endPress = () => {
    clearTimer();
    origin.current = null;
    activePointer.current = null;
  };

  const fireLongPress = () => {
    if (activePointer.current === null) return false;

    // Set this before opening the dialog. React may render the dialog before the browser emits the
    // compatibility click that follows pointerup, but that click still belongs to this gesture.
    suppressNextClick.current = true;
    endPress();
    onLongPress();
    return true;
  };

  useEffect(
    () => () => {
      clearTimer();
      activePointer.current = null;
    },
    [],
  );

  return {
    /** True when this compatibility click belongs to a hold or cancelled scroll gesture. */
    consumedClick: () => {
      const consumed = suppressNextClick.current;
      suppressNextClick.current = false;
      return consumed;
    },
    handlers: {
      onPointerDown: (event: ReactPointerEvent) => {
        if (!enabled || event.button !== 0) return;
        endPress();
        suppressNextClick.current = false;
        activePointer.current = event.pointerId;
        startedAt.current = performance.now();
        origin.current = { x: event.clientX, y: event.clientY };
        timer.current = window.setTimeout(fireLongPress, LONG_PRESS_MS);
      },
      onPointerMove: (event: ReactPointerEvent) => {
        if (activePointer.current !== event.pointerId || !origin.current) return;
        const { x, y } = origin.current;
        if (
          Math.abs(event.clientX - x) > LONG_PRESS_SLOP_PX ||
          Math.abs(event.clientY - y) > LONG_PRESS_SLOP_PX
        ) {
          // A scroll must not become a tap if the browser later emits a compatibility click.
          suppressNextClick.current = true;
          endPress();
        }
      },
      onPointerUp: (event: ReactPointerEvent) => {
        if (activePointer.current !== event.pointerId) return;

        // This closes the narrow race at the timer boundary: pointerup can be handled while the
        // elapsed timer callback is queued but has not run yet. The gesture is still a hold.
        if (performance.now() - startedAt.current >= LONG_PRESS_MS) {
          event.preventDefault();
          fireLongPress();
        } else {
          endPress();
        }
      },
      onPointerLeave: () => {
        if (activePointer.current === null) return;
        suppressNextClick.current = true;
        endPress();
      },
      onPointerCancel: () => {
        if (activePointer.current === null) return;
        suppressNextClick.current = true;
        endPress();
      },
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
    quantity_broken: broken,
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

  const longPress = useLongPress(onRequestStepper, true);

  const cardLabel =
    mode === "find"
      ? `${part.part_num} ${part.color_name}, ${found} of ${required} found, ${broken} broken.` +
        (fullyFound ? " Clear this line." : ` Confirm all ${required} present.`)
      : `${part.part_num} ${part.color_name}, ${unaccounted} of ${required} unaccounted for, ${broken} broken.` +
        (tapDisabled
          ? " Nothing left to mark missing."
          : " Mark one more missing.");

  const cardHint =
    mode === "find"
      ? fullyFound
        ? "Tap to clear this line, long-press to edit condition"
        : `Tap to confirm all ${required} found, long-press to edit found and broken counts`
      : tapDisabled
        ? "Long-press to edit found and broken counts"
        : "Tap to mark one more missing, long-press to edit condition";

  const borderClass = fullyFound
    ? "border-green-300 bg-green-50 hover:border-green-500"
    : mode === "missing" && unaccounted > 0
      ? "border-red-300 bg-red-50 hover:border-red-500"
      : partial
        ? "border-amber-300 bg-amber-50 hover:border-amber-500"
        : "border-gray-300 bg-white hover:border-gray-500";

  return (
    <div
      className={`relative flex flex-col gap-1 rounded border p-1.5 text-left transition-[border-color,box-shadow] duration-150 hover:z-20 hover:shadow-md ${borderClass}`}
    >
      {/* The whole card is the tap target. It overlays the content, which ignores pointers, and
          sits below the corner badge so the badge's own tap wins. */}
      <button
        type="button"
        aria-label={cardLabel}
        title={cardHint}
        aria-disabled={tapDisabled}
        onClick={(event) => {
          if (longPress.consumedClick()) {
            event.preventDefault();
            event.stopPropagation();
            return;
          }
          if (tapDisabled) return;
          onMark(tapDelta);
        }}
        {...longPress.handlers}
        className={`absolute inset-0 z-10 touch-manipulation rounded focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:outline-none ${tapDisabled ? "cursor-default" : "cursor-pointer"}`}
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
            {broken > 0 && (
              <span className="text-violet-700"> &middot; {broken} broken</span>
            )}
          </div>
        </div>
      </div>

      {broken > 0 && (
        <button
          type="button"
          aria-label={`${broken} broken ${broken === 1 ? "piece" : "pieces"}. Edit condition.`}
          title="Edit found and broken counts"
          onClick={onRequestStepper}
          className="absolute top-1 left-1 z-20 flex h-6 min-w-6 items-center justify-center gap-0.5 rounded-full bg-violet-700 px-1.5 font-mono text-[11px] font-bold text-white transition active:scale-90 focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:outline-none"
        >
          <BrokenBrickIcon />
          {broken}
        </button>
      )}

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
