import { useMemo, useState } from "react";
import type { BurnUp } from "../../api/types";
import { areaPath, axisScale, formatCompact, formatCount, INK, linePath, SERIES_BLUE } from "../../lib/chart";
import { ChartEmpty } from "./ChartCard";

const WIDTH = 720;
const HEIGHT = 240;
const PAD = { top: 14, right: 14, bottom: 24, left: 46 };
const PLOT_WIDTH = WIDTH - PAD.left - PAD.right;
const PLOT_HEIGHT = HEIGHT - PAD.top - PAD.bottom;

interface BurnUpChartProps {
  burnUp: BurnUp;
  /** The ceiling the curve is climbing toward — every piece the collection needs. */
  target: number;
}

/**
 * Cumulative pieces confirmed present, against the total the collection needs.
 *
 * The y axis runs to the target rather than to the curve's own maximum. That keeps the chart
 * honest about how much is left: a curve rescaled to its own peak always looks nearly finished.
 */
export function BurnUpChart({ burnUp, target }: BurnUpChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const geometry = useMemo(() => {
    const points = burnUp.points;
    if (points.length < 2) return null;

    const times = points.map((p) => new Date(p.timestamp).getTime());
    const start = times[0];
    const span = times[times.length - 1] - start || 1;
    // Rounded up past the target, so the gridlines land on numbers worth reading rather than on
    // quarters of the collection's arbitrary piece count.
    const { max: ceiling, ticks } = axisScale(Math.max(target, points[points.length - 1].quantity_found, 1));

    const xOf = (time: number) => PAD.left + ((time - start) / span) * PLOT_WIDTH;
    const yOf = (value: number) => PAD.top + PLOT_HEIGHT - (value / ceiling) * PLOT_HEIGHT;

    return {
      ceiling,
      plotted: points.map((p, i) => ({ x: xOf(times[i]), y: yOf(p.quantity_found), point: p })),
      ticks: ticks.map((value) => ({ value, y: yOf(value) })),
      firstLabel: formatDay(points[0].timestamp),
      lastLabel: formatDay(points[points.length - 1].timestamp),
    };
  }, [burnUp, target]);

  if (!geometry) {
    return <ChartEmpty>Nothing sorted yet.</ChartEmpty>;
  }

  const { ceiling, plotted, ticks, firstLabel, lastLabel } = geometry;
  const active = hoverIndex === null ? null : plotted[hoverIndex];
  const baselineY = PAD.top + PLOT_HEIGHT;

  // Nearest point by x, so the crosshair tracks the pointer without needing per-mark hit targets.
  function handleMove(event: React.MouseEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * WIDTH;
    let nearest = 0;
    for (let i = 1; i < plotted.length; i += 1) {
      if (Math.abs(plotted[i].x - x) < Math.abs(plotted[nearest].x - x)) nearest = i;
    }
    setHoverIndex(nearest);
  }

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full"
        role="img"
        aria-label={`Pieces found over time, reaching ${formatCount(plotted[plotted.length - 1].point.quantity_found)} of ${formatCount(ceiling)}`}
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {ticks.map((tick) => (
          <g key={tick.value}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={tick.y} y2={tick.y} stroke={INK.grid} strokeWidth={1} />
            <text x={PAD.left - 8} y={tick.y + 3} textAnchor="end" fontSize={10} fill={INK.label}>
              {formatCompact(tick.value)}
            </text>
          </g>
        ))}

        <path d={areaPath(plotted, baselineY)} fill={SERIES_BLUE} fillOpacity={0.12} />
        <path d={linePath(plotted)} fill="none" stroke={SERIES_BLUE} strokeWidth={2} strokeLinejoin="round" />

        <text x={PAD.left} y={HEIGHT - 6} fontSize={10} fill={INK.label}>
          {firstLabel}
        </text>
        <text x={WIDTH - PAD.right} y={HEIGHT - 6} textAnchor="end" fontSize={10} fill={INK.label}>
          {lastLabel}
        </text>

        {active && (
          <g pointerEvents="none">
            <line
              x1={active.x}
              x2={active.x}
              y1={PAD.top}
              y2={baselineY}
              stroke={INK.axis}
              strokeWidth={1}
              strokeDasharray="3 3"
            />
            {/* A surface-coloured ring keeps the dot readable where it sits on the line. */}
            <circle cx={active.x} cy={active.y} r={4.5} fill={SERIES_BLUE} stroke="#ffffff" strokeWidth={2} />
          </g>
        )}
      </svg>

      <figcaption className="mt-1 flex flex-wrap items-baseline gap-x-2 text-xs text-gray-500">
        {active ? (
          <>
            <span className="font-medium text-gray-900">{formatCount(active.point.quantity_found)} pieces</span>
            <span>
              by {formatMoment(active.point.timestamp, burnUp.granularity)},{" "}
              {Math.round((active.point.quantity_found / ceiling) * 100)}% of the collection
            </span>
          </>
        ) : (
          <span>Hover to read a moment.{burnUp.granularity === "hour" ? " Hourly." : " Daily."}</span>
        )}
      </figcaption>
    </figure>
  );
}

function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function formatMoment(iso: string, granularity: "hour" | "day"): string {
  const date = new Date(iso);
  return granularity === "day"
    ? date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
    : date.toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric" });
}
