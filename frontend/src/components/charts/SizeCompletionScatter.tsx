import { useMemo } from "react";
import type { SetProgress, SortingStatus } from "../../api/types";
import { formatCompact, INK } from "../../lib/chart";
import { STATUS_HEX, STATUS_LABELS } from "../../lib/completion";
import { ChartEmpty } from "./ChartCard";

const WIDTH = 720;
// Tall enough for two rows of text below the plot: the decade ticks and the axis caption.
const HEIGHT = 272;
// The bottom pad carries two rows of text below the plot, so it has to clear the markers sitting
// on the 0% baseline as well as the axis itself.
const PAD = { top: 12, right: 14, bottom: 44, left: 40 };
const PLOT_WIDTH = WIDTH - PAD.left - PAD.right;
const PLOT_HEIGHT = HEIGHT - PAD.top - PAD.bottom;

const STATUS_ORDER: SortingStatus[] = ["not_started", "sorting", "sorted", "complete"];

/**
 * Set size against how much of it is found — "am I only doing the small ones?".
 *
 * The x axis is logarithmic because set sizes run from a handful of pieces to several thousand;
 * on a linear axis every small set would pile against the left edge.
 *
 * Status is drawn as a distinct marker shape as well as a colour. Under red-green colour
 * blindness the "sorted" red and "complete" green are nearly the same hue, so shape carries the
 * distinction on its own and the colour only reinforces it.
 */
export function SizeCompletionScatter({ sets }: { sets: SetProgress[] }) {
  const geometry = useMemo(() => {
    const plottable = sets.filter((set) => set.quantity_required > 0);
    if (plottable.length === 0) return null;

    const sizes = plottable.map((set) => set.quantity_required);
    const minSize = Math.max(1, Math.min(...sizes));
    const maxSize = Math.max(...sizes);
    const lowerLog = Math.log10(minSize);
    const span = Math.log10(maxSize) - lowerLog || 1;

    const xOf = (size: number) => PAD.left + ((Math.log10(size) - lowerLog) / span) * PLOT_WIDTH;
    const yOf = (ratio: number) => PAD.top + PLOT_HEIGHT - ratio * PLOT_HEIGHT;

    // Powers of ten inside the data's range, which is what a log axis can label honestly.
    const decades: number[] = [];
    for (let power = Math.floor(lowerLog); power <= Math.ceil(Math.log10(maxSize)); power += 1) {
      const value = 10 ** power;
      if (value >= minSize && value <= maxSize) decades.push(value);
    }

    return {
      decades: decades.map((value) => ({ value, x: xOf(value) })),
      marks: plottable.map((set) => ({
        set,
        x: xOf(set.quantity_required),
        y: yOf(set.quantity_found / set.quantity_required),
        percent: Math.round((set.quantity_found / set.quantity_required) * 100),
      })),
    };
  }, [sets]);

  if (!geometry) return <ChartEmpty>No sets with a cached parts list yet.</ChartEmpty>;

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" role="img" aria-label="Set size against completion">
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const y = PAD.top + PLOT_HEIGHT - fraction * PLOT_HEIGHT;
          return (
            <g key={fraction}>
              <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y} y2={y} stroke={INK.grid} strokeWidth={1} />
              <text x={PAD.left - 8} y={y + 3} textAnchor="end" fontSize={10} fill={INK.label}>
                {fraction * 100}%
              </text>
            </g>
          );
        })}

        {geometry.decades.map((decade) => (
          <text key={decade.value} x={decade.x} y={HEIGHT - 24} textAnchor="middle" fontSize={10} fill={INK.label}>
            {formatCompact(decade.value)}
          </text>
        ))}
        <text x={WIDTH - PAD.right} y={HEIGHT - 7} textAnchor="end" fontSize={10} fill={INK.label}>
          set size in pieces (log scale)
        </text>

        {geometry.marks.map(({ set, x, y, percent }) => (
          <g key={set.set_num}>
            <title>{`${set.set_num} ${set.name} · ${set.quantity_required} pieces, ${percent}% found, ${STATUS_LABELS[set.status]}`}</title>
            <StatusMark x={x} y={y} status={set.status} />
          </g>
        ))}
      </svg>

      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
        {STATUS_ORDER.map((status) => (
          <li key={status} className="flex items-center gap-1.5 text-xs text-gray-600">
            <svg width={14} height={14} viewBox="0 0 14 14" aria-hidden>
              <StatusMark x={7} y={7} status={status} />
            </svg>
            {STATUS_LABELS[status]}
          </li>
        ))}
      </ul>
    </figure>
  );
}

/**
 * One marker per status, each a different silhouette: hollow circle, filled circle, triangle,
 * square. A white ring keeps overlapping marks separable where sets cluster.
 */
function StatusMark({ x, y, status }: { x: number; y: number; status: SortingStatus }) {
  const fill = STATUS_HEX[status];
  const common = { stroke: "#ffffff", strokeWidth: 1.5 };

  if (status === "not_started") {
    return <circle cx={x} cy={y} r={4} fill="#ffffff" stroke={fill} strokeWidth={2} />;
  }
  if (status === "sorting") {
    return <circle cx={x} cy={y} r={4.5} fill={fill} {...common} />;
  }
  if (status === "sorted") {
    return <polygon points={`${x},${y - 5} ${x + 4.8},${y + 3.6} ${x - 4.8},${y + 3.6}`} fill={fill} {...common} />;
  }
  return <rect x={x - 4} y={y - 4} width={8} height={8} rx={1} fill={fill} {...common} />;
}
