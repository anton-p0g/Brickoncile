import { Link } from "react-router-dom";
import type { ContributorOut, PartAggregateOut } from "../api/types";
import { markKey, sourceHref } from "../lib/sources";
import { ColorSwatch } from "./ColorSwatch";

interface MissingPartCardProps {
  aggregate: PartAggregateOut;
  /** Opens the part image full size. */
  onZoom: () => void;
  /** Confirms one piece of this part present in that one source. */
  onMarkFound: (contributor: ContributorOut) => void;
  /** markKey of the write in flight, if any. */
  pendingKey: string | null;
}

/**
 * One missing part, with every set and minifig waiting on it.
 *
 * The contributors are the point of the card, not a footnote: a part missing from three sets is a
 * different problem than one missing from a single set, and each is a link straight into the
 * inventory that wants it.
 */
export function MissingPartCard({ aggregate, onZoom, onMarkFound, pendingKey }: MissingPartCardProps) {
  return (
    <div className="flex flex-col gap-1.5 rounded border border-red-200 bg-white p-2">
      <div className="relative">
        {/* Disabled without an image, rather than a target that looks live and does nothing. */}
        <button
          type="button"
          onClick={onZoom}
          disabled={!aggregate.image_url}
          title={aggregate.image_url ? "Show the part image larger" : "No image for this part"}
          className="aspect-square w-full overflow-hidden rounded bg-gray-100 enabled:cursor-zoom-in"
        >
          {aggregate.image_url && (
            <img
              src={aggregate.image_url}
              alt={aggregate.part_name}
              loading="lazy"
              className="h-full w-full object-contain"
            />
          )}
        </button>
        <span
          title={`${aggregate.total_missing} pieces missing in total`}
          className="pointer-events-none absolute top-0.5 right-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 font-mono text-[10px] font-bold text-white"
        >
          {aggregate.total_missing}
        </span>
      </div>

      {/* To the part search, which also lists the inventories that already have this piece. */}
      <Link
        to={`/find?q=${encodeURIComponent(aggregate.part_num)}`}
        title={`Look up ${aggregate.part_num} across your collection`}
        className="w-full truncate font-mono text-[10px] font-bold text-gray-700 hover:underline"
      >
        {aggregate.part_num}
      </Link>
      <div className="flex items-center gap-1 text-[10px] text-gray-600">
        <ColorSwatch colorId={aggregate.color_id} colorName={aggregate.color_name} />
        <span className="truncate">{aggregate.color_name}</span>
      </div>
      {/* The full name never fits at this density, so it is also the hover title. */}
      <div className="line-clamp-2 text-[10px] leading-tight text-gray-500" title={aggregate.part_name}>
        {aggregate.part_name}
      </div>

      {/* At ten columns a set's name has no room to be legible, so the thumbnail and set number
          identify it and the name lives in the tooltip. */}
      <div className="mt-auto flex flex-col gap-0.5 border-t border-dashed border-gray-200 pt-1">
        {aggregate.contributors.map((contributor) => (
          <div key={`${contributor.source_type}-${contributor.source_id}`} className="flex items-center gap-0.5">
            <Link
              to={sourceHref(contributor)}
              title={`Open ${contributor.name} (${contributor.reference})`}
              className="flex min-w-0 flex-1 items-center gap-1 rounded hover:bg-gray-100"
            >
              <span className="h-4 w-4 flex-shrink-0 overflow-hidden rounded-sm bg-gray-100">
                {contributor.image_url && (
                  <img
                    src={contributor.image_url}
                    alt=""
                    loading="lazy"
                    className="h-full w-full object-contain"
                  />
                )}
              </span>
              <span
                className={`min-w-0 flex-1 truncate font-mono text-[10px] leading-tight ${
                  contributor.source_type === "minifig_instance" ? "text-blue-700" : "text-gray-600"
                }`}
              >
                {contributor.reference}
              </span>
              <span className="flex-shrink-0 font-mono text-[10px] font-bold text-red-700">
                &times;{contributor.quantity}
              </span>
            </Link>
            <button
              type="button"
              onClick={() => onMarkFound(contributor)}
              disabled={
                pendingKey === markKey(contributor.source_id, aggregate.part_num, aggregate.color_id)
              }
              title={`Confirm one present in ${contributor.name}`}
              aria-label={`Confirm one ${aggregate.part_num} ${aggregate.color_name} present in ${contributor.name}`}
              className="ui-control h-4 w-4 flex-shrink-0 border-green-300 text-[9px] font-bold text-green-700 hover:border-green-500 hover:bg-green-50 disabled:opacity-40"
            >
              &#10003;
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
