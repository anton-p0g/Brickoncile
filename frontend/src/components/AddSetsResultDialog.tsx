import { useEffect, useRef } from "react";
import type { BulkAddResultItem } from "../api/types";

interface AddSetsResultDialogProps {
  results: BulkAddResultItem[];
  onClose: () => void;
}

/** Shows the resolved set number, and what was typed when normalization changed it — a bare
 *  "70202" landing as "70202-1" should be traceable back to the line that produced it. */
function resultLabel(result: BulkAddResultItem): string {
  return result.set_num === result.input_set_num
    ? result.set_num
    : `${result.input_set_num} → ${result.set_num}`;
}

interface SectionProps {
  title: string;
  accent: string;
  items: BulkAddResultItem[];
  renderDetail: (item: BulkAddResultItem) => string | null;
  detailClass?: string;
}

function Section({ title, accent, items, renderDetail, detailClass = "text-gray-500" }: SectionProps) {
  if (items.length === 0) return null;

  return (
    <section className="mt-3 first:mt-0">
      <h3 className="flex items-baseline gap-2 text-sm font-semibold">
        <span className={`h-2 w-2 rounded-full ${accent}`} aria-hidden="true" />
        {title}
        <span className="font-mono text-xs font-normal text-gray-400">{items.length}</span>
      </h3>
      <ul className="mt-1 divide-y divide-gray-100 border-t border-gray-100">
        {items.map((item) => {
          const detail = renderDetail(item);
          return (
            <li key={`${item.status}-${item.input_set_num}`} className="flex flex-wrap gap-x-2 py-1 text-xs">
              <span className="font-mono font-semibold">{resultLabel(item)}</span>
              {detail && <span className={detailClass}>{detail}</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * Report for a finished bulk add. Every set is reported individually — a paste of twenty numbers
 * with one typo needs to say which one, not just that something went wrong.
 */
export function AddSetsResultDialog({ results, onClose }: AddSetsResultDialogProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  const added = results.filter((r) => r.status === "ok");
  const existing = results.filter((r) => r.status === "exists");
  const partial = results.filter((r) => r.status === "partial");
  const failed = results.filter((r) => r.status === "error");

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const title =
    failed.length > 0
      ? `${failed.length} of ${results.length} could not be added`
      : partial.length > 0
        ? `${partial.length} set${partial.length === 1 ? "" : "s"} added without minifigures`
        : added.length === results.length
          ? `All ${added.length} set${added.length === 1 ? "" : "s"} added`
          : "Bulk add complete";

  // Partial sets count as added here: they are in the collection, just not complete.
  const summary = [
    `${added.length + partial.length} added`,
    existing.length > 0 && `${existing.length} already owned`,
    partial.length > 0 && `${partial.length} without minifigures`,
    failed.length > 0 && `${failed.length} failed`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div aria-hidden="true" onClick={onClose} className="absolute inset-0 bg-gray-900/40" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-results-title"
        className="relative flex max-h-[80vh] w-full max-w-md flex-col rounded border border-gray-300 bg-white shadow-xl"
      >
        <div className="border-b border-gray-200 p-4 pb-3">
          <h2 id="add-results-title" className="text-base font-bold">
            {title}
          </h2>
          <p className="mt-0.5 font-mono text-xs text-gray-500">{summary}</p>
        </div>

        <div className="overflow-y-auto p-4">
          <Section
            title="Added"
            accent="bg-green-600"
            items={added}
            renderDetail={(item) => item.name}
          />
          <Section
            title="Added, but without their minifigures"
            accent="bg-amber-500"
            items={partial}
            // These sets ARE in the collection — the reason names what is missing and how to fix it.
            renderDetail={(item) => item.error ?? "minifigures missing"}
            detailClass="text-amber-700"
          />
          <Section
            title="Already in your collection"
            accent="bg-gray-400"
            items={existing}
            renderDetail={(item) => item.name}
          />
          <Section
            title="Failed"
            accent="bg-red-600"
            items={failed}
            // The reason is the point of the report: it says whether to fix the number or retry.
            renderDetail={(item) => item.error ?? "unknown error"}
            detailClass="text-red-600"
          />
          {failed.length > 0 && (
            <p className="mt-3 text-xs text-gray-500">
              The failed numbers were kept in the box so you can correct them and try again.
            </p>
          )}
        </div>

        <div className="flex justify-end border-t border-gray-200 p-3">
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded border border-gray-900 bg-gray-900 px-3 py-1.5 text-sm text-white hover:bg-gray-700"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
