import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { SetProgress } from "../../api/types";
import { completionFill, completionInk } from "../../lib/chart";
import { completionPercent, STATUS_LABELS } from "../../lib/completion";
import { StatusBadge } from "../StatusBadge";
import { ChartEmpty } from "./ChartCard";

/** Fixed so the preview can be kept inside the grid without measuring it after every hover. */
const PREVIEW_WIDTH = 180;
/**
 * The preview's actual rendered height: a 96px image, three short lines of text and the padding.
 * Used to decide whether there is room above the tile, so it has to track the markup below.
 */
const PREVIEW_HEIGHT = 182;
const GAP = 6;

interface Preview {
  set: SetProgress;
  /** Centre of the hovered tile, and the preview's final top edge. Both already clamped. */
  x: number;
  y: number;
}

/**
 * One tile per set, shaded by how much of it is confirmed present and ordered least-complete
 * first, so the work still to do sits at the top left where reading starts.
 *
 * Small multiples rather than a bar chart: at a collection's scale there are too many sets for
 * labelled bars and too few for a distribution, and every tile stays big enough to click through
 * to the set it stands for.
 *
 * Identity lives in a hover preview rather than in the tiles themselves. Set renders are large and
 * highly saturated, and putting fifty of them in the grid would drown the shading that the chart
 * exists to show. Only the hovered set's picture is ever mounted, so the grid costs one image
 * request at a time instead of one per set.
 */
export function CompletionGrid({ sets }: { sets: SetProgress[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [preview, setPreview] = useState<Preview | null>(null);

  const ordered = useMemo(
    () => [...sets].sort((a, b) => ratioOf(a) - ratioOf(b) || a.name.localeCompare(b.name)),
    [sets],
  );

  function show(set: SetProgress, tile: HTMLElement) {
    const container = containerRef.current;
    if (!container) return;

    const tileBox = tile.getBoundingClientRect();
    const gridBox = container.getBoundingClientRect();
    const centre = tileBox.left - gridBox.left + tileBox.width / 2;
    const top = tileBox.top - gridBox.top;
    const half = PREVIEW_WIDTH / 2;

    // Whichever side of the tile has more room, then clamped into the grid. Clamping rather than
    // only flipping matters in the middle rows, where neither side has a full preview's height.
    const roomBelow = gridBox.height - (top + tileBox.height);
    const y = roomBelow >= top ? top + tileBox.height + GAP : top - PREVIEW_HEIGHT - GAP;

    setPreview({
      set,
      x: Math.min(Math.max(centre, half), Math.max(half, gridBox.width - half)),
      y: Math.min(Math.max(y, 0), Math.max(0, gridBox.height - PREVIEW_HEIGHT)),
    });
  }

  if (sets.length === 0) return <ChartEmpty>No sets yet.</ChartEmpty>;

  return (
    <div ref={containerRef} className="relative" onMouseLeave={() => setPreview(null)}>
      <ul className="grid grid-cols-6 gap-1 sm:grid-cols-8 md:grid-cols-10 lg:grid-cols-12 xl:grid-cols-14">
        {ordered.map((set) => {
          const ratio = ratioOf(set);
          const percent = completionPercent(toCompletable(set));
          return (
            <li key={set.set_num}>
              <Link
                to={`/sets/${encodeURIComponent(set.set_num)}`}
                aria-label={`${set.set_num} ${set.name}, ${percent}% found, ${STATUS_LABELS[set.status]}`}
                onMouseEnter={(e) => show(set, e.currentTarget)}
                // Keyboard users tab through the tiles, so the preview follows focus too.
                onFocus={(e) => show(set, e.currentTarget)}
                onBlur={() => setPreview(null)}
                className="flex aspect-square items-center justify-center rounded-sm font-mono text-[10px] font-semibold hover:ring-2 hover:ring-gray-900 focus:ring-2 focus:ring-gray-900 focus:outline-none"
                style={{ backgroundColor: completionFill(ratio), color: completionInk(ratio) }}
              >
                {percent}
              </Link>
            </li>
          );
        })}
      </ul>

      {preview && <PreviewCard preview={preview} />}
    </div>
  );
}

function PreviewCard({ preview }: { preview: Preview }) {
  const { set } = preview;
  const percent = completionPercent(toCompletable(set));

  return (
    <div
      // Never a hover target itself, so moving toward it cannot make it flicker.
      className="pointer-events-none absolute z-10 rounded-lg border border-gray-300 bg-white p-2 shadow-lg"
      style={{ width: PREVIEW_WIDTH, left: preview.x, top: preview.y, transform: "translateX(-50%)" }}
    >
      {/* A fixed height rather than a square: set renders are wide, so a square box would be
          mostly empty backdrop and would make the card tall enough to cover the grid it explains. */}
      {set.image_url ? (
        <img src={set.image_url} alt="" className="mb-1.5 h-24 w-full rounded bg-gray-100 object-contain" />
      ) : (
        <div className="mb-1.5 flex h-24 w-full items-center justify-center rounded bg-gray-100 text-[11px] text-gray-400">
          no image
        </div>
      )}
      <p className="truncate font-mono text-[11px] font-semibold text-gray-900">{set.set_num}</p>
      <p className="truncate text-[11px] text-gray-600" title={set.name}>
        {set.name}
      </p>
      <p className="mt-1 flex items-center justify-between gap-2">
        <StatusBadge status={set.status} missingCount={set.quantity_missing} />
        <span className="font-mono text-[11px] text-gray-500">
          {percent}% of {set.quantity_required}
        </span>
      </p>
    </div>
  );
}

function toCompletable(set: SetProgress) {
  return { quantity_required_total: set.quantity_required, quantity_found_total: set.quantity_found };
}

function ratioOf(set: SetProgress): number {
  return set.quantity_required > 0 ? set.quantity_found / set.quantity_required : 1;
}
