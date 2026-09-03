import type { CommonPartOut } from "../../api/types";
import { SERIES_BLUE } from "../../lib/chart";
import { ColorSwatch } from "../ColorSwatch";
import { ChartEmpty } from "./ChartCard";

interface CommonPartsChartProps {
  parts: CommonPartOut[];
  /** Total sets owned, so a bar reads as a share of the collection rather than a bare count. */
  totalSets: number;
}

/**
 * The parts that turn up across the most sets — the ones worth their own bin.
 *
 * Horizontal bars because the labels are long part names, which a vertical axis cannot hold.
 * Ranked, so the order itself is information.
 */
export function CommonPartsChart({ parts, totalSets }: CommonPartsChartProps) {
  if (parts.length === 0) return <ChartEmpty>No parts cached yet.</ChartEmpty>;

  const max = Math.max(...parts.map((part) => part.set_count));

  return (
    <ul className="flex flex-col gap-1.5">
      {parts.map((part) => (
        <li
          key={`${part.part_num}-${part.color_id}`}
          className="-mx-1.5 flex items-center gap-2 rounded px-1.5 py-0.5 text-xs transition-[background-color,transform] duration-150 hover:translate-x-0.5 hover:bg-gray-50"
        >
          {part.image_url ? (
            <img
              src={part.image_url}
              alt=""
              loading="lazy"
              className="size-6 shrink-0 rounded border border-gray-200 bg-white object-contain"
            />
          ) : (
            <span className="size-6 shrink-0 rounded border border-gray-200 bg-white" />
          )}
          <span className="flex w-28 shrink-0 items-center gap-1 truncate text-gray-600 sm:w-44">
            <ColorSwatch colorId={part.color_id} colorName={part.color_name} />
            <span className="truncate" title={`${part.part_name} (${part.color_name})`}>
              {part.part_name}
            </span>
          </span>
          <span className="flex h-4 min-w-0 flex-1 items-center">
            <span
              className="h-full rounded-sm"
              style={{ width: `${(part.set_count / max) * 100}%`, backgroundColor: SERIES_BLUE }}
              title={`${part.part_name} in ${part.color_name}: ${part.set_count} of ${totalSets} sets, ${part.quantity_required} pieces in total`}
            />
          </span>
          <span className="w-16 shrink-0 text-right font-mono text-gray-900">
            {part.set_count}
            <span className="text-gray-400">/{totalSets}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
