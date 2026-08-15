import { Link } from "react-router-dom";
import type { MissingPartStatOut } from "../../api/types";
import { ColorSwatch } from "../ColorSwatch";
import { ChartEmpty } from "./ChartCard";

/**
 * The parts most owed across the collection, ranked.
 *
 * Deliberately a list rather than a chart: the counts are small enough that bars would encode
 * almost no difference, while the part's picture is what makes an entry recognisable.
 */
export function TopMissingList({ parts }: { parts: MissingPartStatOut[] }) {
  if (parts.length === 0) {
    return (
      <ChartEmpty>
        Nothing confirmed missing. Pieces only count as missing once you finish sorting a set.
      </ChartEmpty>
    );
  }

  return (
    <ul className="flex flex-col gap-1.5">
      {parts.map((part) => (
        <li key={`${part.part_num}-${part.color_id}`} className="flex items-center gap-2 text-xs">
          {part.image_url ? (
            <img
              src={part.image_url}
              alt=""
              loading="lazy"
              className="size-7 shrink-0 rounded border border-gray-200 object-contain"
            />
          ) : (
            <span className="size-7 shrink-0 rounded border border-gray-200" />
          )}
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="flex items-center gap-1 truncate text-gray-900" title={part.part_name}>
              <ColorSwatch colorId={part.color_id} colorName={part.color_name} />
              <span className="truncate">{part.part_name}</span>
            </span>
            <span className="truncate text-[11px] text-gray-400">
              {part.color_name} · wanted by {part.source_count} {part.source_count === 1 ? "source" : "sources"}
            </span>
          </span>
          <span className="shrink-0 rounded bg-red-50 px-1.5 py-0.5 font-mono text-xs font-bold text-red-700">
            ×{part.total_missing}
          </span>
        </li>
      ))}
      <li className="mt-1">
        <Link to="/missing" className="text-xs text-gray-500 underline hover:text-gray-900">
          See every missing part →
        </Link>
      </li>
    </ul>
  );
}
