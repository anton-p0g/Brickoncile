import { useMemo } from "react";
import type { ThemeStats } from "../../api/types";
import { completionFill, completionInk, formatCount, treemap } from "../../lib/chart";
import { NO_THEME_LABEL } from "../../lib/themes";
import { ChartEmpty } from "./ChartCard";

const WIDTH = 720;
const HEIGHT = 300;

/**
 * The collection by theme: tile area is pieces, shading is how much of that theme is found.
 *
 * Sizes across themes span three orders of magnitude, which a bar chart cannot show — the smallest
 * lines would be invisible next to the biggest. A treemap keeps every theme pointable while still
 * encoding size faithfully.
 */
export function ThemeTreemap({ themes }: { themes: ThemeStats[] }) {
  const tiles = useMemo(
    () => treemap(themes, (theme) => theme.quantity_required, WIDTH, HEIGHT),
    [themes],
  );

  if (tiles.length === 0) return <ChartEmpty>No themed sets yet.</ChartEmpty>;

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" role="img" aria-label="Collection size by theme">
      {tiles.map(({ item, x, y, width, height }) => {
        const ratio = item.quantity_required > 0 ? item.quantity_found / item.quantity_required : 0;
        const label = item.theme_name ?? NO_THEME_LABEL;
        // Only tiles with room get text; the rest rely on their tooltip, which every tile has.
        const showName = width > 62 && height > 26;
        const showCount = width > 62 && height > 42;

        return (
          <g key={label}>
            <title>{`${label} · ${formatCount(item.quantity_required)} pieces across ${item.sets} set${item.sets === 1 ? "" : "s"}, ${Math.round(ratio * 100)}% found`}</title>
            {/* A 2px inset gives every tile a surface-coloured gutter instead of a shared edge. */}
            <rect
              x={x + 1}
              y={y + 1}
              width={Math.max(0, width - 2)}
              height={Math.max(0, height - 2)}
              rx={2}
              fill={completionFill(ratio)}
            />
            {showName && (
              <text x={x + 7} y={y + 16} fontSize={11} fontWeight={600} fill={completionInk(ratio)}>
                {clip(label, width)}
              </text>
            )}
            {showCount && (
              <text x={x + 7} y={y + 30} fontSize={10} fill={completionInk(ratio)} opacity={0.85}>
                {formatCount(item.quantity_required)} pcs · {Math.round(ratio * 100)}%
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/** Rough character budget for the tile width, so a long theme name cannot bleed past its tile. */
function clip(label: string, width: number): string {
  const budget = Math.floor((width - 14) / 6);
  return label.length <= budget ? label : `${label.slice(0, Math.max(1, budget - 1))}…`;
}
