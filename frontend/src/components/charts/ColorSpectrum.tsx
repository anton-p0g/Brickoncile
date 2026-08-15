import type { ColorStats } from "../../api/types";
import { formatCount } from "../../lib/chart";
import { colorHex, needsSwatchOutline } from "../../lib/colors";
import { ChartEmpty } from "./ChartCard";

/**
 * The collection's palette, as pieces per colour.
 *
 * The one chart here that does not take its colours from the design system: each bar is drawn in
 * the brick's own colour, because the colour *is* the category being measured. Every bar carries
 * its name and count, so the encoding never depends on telling two similar grays apart.
 */
export function ColorSpectrum({ colors, limit = 18 }: { colors: ColorStats[]; limit?: number }) {
  if (colors.length === 0) return <ChartEmpty>No parts cached yet.</ChartEmpty>;

  const shown = colors.slice(0, limit);
  const rest = colors.slice(limit);
  const max = Math.max(...shown.map((color) => color.quantity_required));
  const restTotal = rest.reduce((sum, color) => sum + color.quantity_required, 0);

  return (
    <div>
      <ul className="flex flex-col gap-1">
        {shown.map((color) => {
          const hex = colorHex(color.color_id);
          return (
            <li key={color.color_id} className="flex items-center gap-2 text-xs">
              <span className="w-28 shrink-0 truncate text-gray-600" title={color.color_name}>
                {color.color_name}
              </span>
              <span className="flex h-4 min-w-0 flex-1 items-center">
                <span
                  className={`h-full rounded-sm ${hex && needsSwatchOutline(hex) ? "border border-gray-300" : ""}`}
                  style={{
                    width: `${Math.max(1, (color.quantity_required / max) * 100)}%`,
                    // An unlisted colour has no honest swatch, so it shows as neutral rather than
                    // inventing an appearance the brick does not have.
                    backgroundColor: hex ?? "#d1d5db",
                  }}
                  title={`${color.color_name}: ${formatCount(color.quantity_required)} pieces across ${color.distinct_parts} part${color.distinct_parts === 1 ? "" : "s"}`}
                />
              </span>
              <span className="w-12 shrink-0 text-right font-mono text-gray-900">
                {formatCount(color.quantity_required)}
              </span>
            </li>
          );
        })}
      </ul>
      {rest.length > 0 && (
        <p className="mt-2 text-[11px] text-gray-400">
          + {rest.length} more colours, {formatCount(restTotal)} pieces between them.
        </p>
      )}
    </div>
  );
}
