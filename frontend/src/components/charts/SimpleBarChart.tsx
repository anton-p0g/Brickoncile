import { useState } from "react";
import { axisScale, formatCompact, INK, SERIES_BLUE } from "../../lib/chart";
import { ChartEmpty } from "./ChartCard";

export interface Bar {
  label: string;
  value: number;
  /** Tooltip text; the label alone is rarely enough to say what the bar counts. */
  title: string;
}

interface SimpleBarChartProps {
  bars: Bar[];
  height?: number;
  /** Show every nth label, for axes too dense to label at every tick. */
  labelEvery?: number;
}

const WIDTH = 720;
const PAD = { top: 10, right: 10, bottom: 22, left: 34 };

/**
 * A vertical bar chart for one series over an ordered category axis.
 *
 * One hue throughout: the bars are one measurement, and colouring them separately would imply
 * categories that carry meaning. The value is read from height against the gridlines.
 */
export function SimpleBarChart({ bars, height = 160, labelEvery = 1 }: SimpleBarChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  if (bars.length === 0) return <ChartEmpty>Nothing to show yet.</ChartEmpty>;

  const plotHeight = height - PAD.top - PAD.bottom;
  const plotWidth = WIDTH - PAD.left - PAD.right;
  const { max, ticks } = axisScale(Math.max(...bars.map((bar) => bar.value)));
  const slot = plotWidth / bars.length;
  const barWidth = Math.max(2, slot - 4);
  const activeBar = activeIndex === null ? null : bars[activeIndex];

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="w-full"
        role="img"
        aria-label={bars.map((b) => b.title).join("; ")}
        onMouseLeave={() => setActiveIndex(null)}
      >
        {ticks.map((tick) => {
          const y = PAD.top + plotHeight - (tick / max) * plotHeight;
          return (
            <g key={tick}>
              <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y} y2={y} stroke={INK.grid} strokeWidth={1} />
              <text x={PAD.left - 6} y={y + 3} textAnchor="end" fontSize={10} fill={INK.label}>
                {formatCompact(tick)}
              </text>
            </g>
          );
        })}

        {bars.map((bar, index) => {
          const barHeight = (bar.value / max) * plotHeight;
          const x = PAD.left + index * slot + (slot - barWidth) / 2;
          const active = activeIndex === index;
          const activeY = Math.max(PAD.top, PAD.top + plotHeight - barHeight - (active ? 2 : 0));
          return (
            <g
              key={bar.label}
              tabIndex={0}
              aria-label={bar.title}
              onMouseEnter={() => setActiveIndex(index)}
              onFocus={() => setActiveIndex(index)}
              onBlur={() => setActiveIndex(null)}
              className="cursor-default focus:outline-none"
            >
              {/* Full-slot hit area, so a short bar is still easy to hover. */}
              <rect
                x={PAD.left + index * slot}
                y={PAD.top}
                width={slot}
                height={plotHeight}
                fill={active ? "#f3f4f6" : "transparent"}
                className="transition-colors duration-150"
              />
              {bar.value > 0 && (
                <rect
                  x={x - (active ? 1 : 0)}
                  y={activeY}
                  width={barWidth + (active ? 2 : 0)}
                  height={PAD.top + plotHeight - activeY}
                  rx={2}
                  fill={SERIES_BLUE}
                  opacity={active ? 1 : 0.82}
                  className="transition-all duration-150"
                />
              )}
              {index % labelEvery === 0 && (
                <text
                  x={x + barWidth / 2}
                  y={height - 8}
                  textAnchor="middle"
                  fontSize={10}
                  fill={active ? INK.text : INK.label}
                  fontWeight={active ? 600 : 400}
                >
                  {bar.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <figcaption className="flex min-h-8 items-center justify-center px-2 text-center text-xs text-gray-500">
        {activeBar ? (
          <span className="font-medium text-gray-900">{activeBar.title}</span>
        ) : (
          <span className="text-gray-400">Hover or focus a bar for details.</span>
        )}
      </figcaption>
    </figure>
  );
}
