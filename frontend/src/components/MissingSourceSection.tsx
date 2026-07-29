import { Link } from "react-router-dom";
import type { SourceAggregateOut, SourceItemOut } from "../api/types";
import { markKey, sourceHref } from "../lib/sources";
import { ColorSwatch } from "./ColorSwatch";

interface MissingSourceSectionProps {
  aggregate: SourceAggregateOut;
  onZoom: (item: SourceItemOut) => void;
  /** The set's or figure's own image, full size. */
  onZoomSource: () => void;
  onMarkFound: (item: SourceItemOut) => void;
  /** markKey of the write in flight, so only that one card shows as busy. */
  pendingKey: string | null;
  isOpen: boolean;
  onToggle: () => void;
}

/**
 * Everything one set or minifig is short of, behind a heading that summarises it.
 *
 * Collapsed by default: the collection has far more sets than fit on a screen at once, and the
 * question this page answers first is which sets are short and by how much. The parts are the
 * follow-up, opened for the one being worked on.
 *
 * The grid is denser than the by-part one on purpose: the owning inventory is already named by the
 * heading, so each card spends its space on the part instead of repeating where it belongs.
 */
export function MissingSourceSection({
  aggregate,
  onZoom,
  onZoomSource,
  onMarkFound,
  pendingKey,
  isOpen,
  onToggle,
}: MissingSourceSectionProps) {
  const isMinifig = aggregate.source_type === "minifig_instance";
  const panelId = `missing-${aggregate.source_type}-${aggregate.source_id}`;

  return (
    <section>
      <div
        className={`relative flex items-center gap-3 rounded border p-2 ${
          isMinifig ? "border-blue-200 bg-blue-50" : "border-gray-200 bg-gray-50"
        } ${isOpen ? "mb-2" : ""}`}
      >
        {/* The toggle covers the whole heading, and the three things that mean something else sit
            above it. A link cannot be nested inside a button, and this is how PartCard already
            solves the same problem. */}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={isOpen}
          aria-controls={isOpen ? panelId : undefined}
          aria-label={
            isOpen ? `Hide ${aggregate.name}'s missing parts` : `Show ${aggregate.name}'s missing parts`
          }
          title={isOpen ? "Hide the missing parts" : "Show the missing parts"}
          className="absolute inset-0 z-10 cursor-pointer rounded"
        />

        {/* Its own target rather than part of the toggle: the picture is how you recognise a set,
            and wanting a better look at it is not the same as wanting its parts list. */}
        <button
          type="button"
          onClick={onZoomSource}
          disabled={!aggregate.image_url}
          title={aggregate.image_url ? `Show ${aggregate.name} larger` : `No image for ${aggregate.name}`}
          className="relative z-20 h-12 w-12 flex-shrink-0 overflow-hidden rounded bg-white enabled:cursor-zoom-in"
        >
          {aggregate.image_url && (
            <img src={aggregate.image_url} alt="" loading="lazy" className="h-full w-full object-contain" />
          )}
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-white uppercase ${
                isMinifig ? "bg-blue-600" : "bg-gray-600"
              }`}
            >
              {isMinifig ? "Minifig" : "Set"}
            </span>
            {/* Padded well past the text, and pulled back out by the same amount, so the target is
                comfortable without the row growing around it. */}
            <Link
              to={sourceHref(aggregate)}
              title={`Open ${aggregate.name}`}
              className="relative z-20 -my-1 min-w-0 truncate rounded px-2 py-1.5 font-semibold hover:bg-white hover:underline"
            >
              {aggregate.name}
            </Link>
          </div>
          <div className="mt-0.5 flex items-center gap-2 font-mono text-[11px] text-gray-500">
            {aggregate.reference}
            {/* Kinds, not pieces: the badge beside this counts pieces, and one kind can be short
                several copies. Saying "lines" assumed the reader thinks in inventory rows. */}
            <span className="text-gray-400">
              {aggregate.items.length} {aggregate.items.length === 1 ? "kind" : "kinds"} of piece
            </span>
          </div>
        </div>

        <span className="flex-shrink-0 rounded bg-red-600 px-1.5 py-0.5 font-mono text-[11px] font-bold text-white">
          {aggregate.total_missing} missing
        </span>
        {/* The caret a dropdown would have, on the side one expects it. Purely a visual affordance
            — the overlay behind it is what toggles — so it is hidden from screen readers, which
            would otherwise hear the same control twice, and it must not swallow the click either:
            raised only to paint above the overlay, never to receive its pointer events. */}
        <span
          aria-hidden="true"
          className="relative z-20 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-gray-500 select-none pointer-events-none"
        >
          <span className="text-xs">{isOpen ? "▾" : "▸"}</span>
        </span>
      </div>

      {/* Not merely hidden: a collapsed section renders nothing, so a hundred sets do not queue a
          thousand part images the owner never asked to see. */}
      {isOpen && (
        <div
          id={panelId}
          className="grid grid-cols-3 gap-2 sm:grid-cols-5 md:grid-cols-7 lg:grid-cols-9 xl:grid-cols-10"
        >
          {aggregate.items.map((item) => {
            const key = markKey(aggregate.source_id, item.part_num, item.color_id);
            return (
              <div key={key} className="relative flex flex-col gap-1 rounded border border-red-200 bg-white p-1.5">
                <button
                  type="button"
                  onClick={() => onZoom(item)}
                  disabled={!item.image_url}
                  title={item.image_url ? "Show the part image larger" : "No image for this part"}
                  className="aspect-square w-full overflow-hidden rounded bg-gray-100 enabled:cursor-zoom-in"
                >
                  {item.image_url && (
                    <img
                      src={item.image_url}
                      alt={item.part_name}
                      loading="lazy"
                      className="h-full w-full object-contain"
                    />
                  )}
                </button>

                <div className="font-mono text-[10px] leading-tight text-gray-700">
                  <Link
                    to={`/find?q=${encodeURIComponent(item.part_num)}`}
                    title={`Look up ${item.part_num} across your collection`}
                    className="block truncate font-bold hover:underline"
                  >
                    {item.part_num}
                  </Link>
                  <div className="flex items-center gap-1">
                    <ColorSwatch colorId={item.color_id} colorName={item.color_name} />
                    <span className="truncate">{item.color_name}</span>
                  </div>
                </div>
                <div className="line-clamp-2 text-[10px] leading-tight text-gray-500" title={item.part_name}>
                  {item.part_name}
                </div>

                {/* Doubles as the count and the action: tap it when one of them turns up. */}
                <button
                  type="button"
                  onClick={() => onMarkFound(item)}
                  disabled={pendingKey === key}
                  title={`${item.quantity_missing} missing — tap to confirm one present`}
                  aria-label={`${item.quantity_missing} of ${item.part_num} ${item.color_name} missing from ${aggregate.name}. Confirm one present.`}
                  className="absolute top-0.5 right-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 font-mono text-[10px] font-bold text-white transition hover:bg-green-600 active:scale-90 disabled:opacity-40"
                >
                  {item.quantity_missing}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
