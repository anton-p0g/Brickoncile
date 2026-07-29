import { useEffect, useRef } from "react";
import type { BulkAddMinifigResultItem } from "../api/types";

interface AddMinifigsResultDialogProps {
  results: BulkAddMinifigResultItem[];
  onClose: () => void;
}

/** What was pasted, and the fig ID it resolved to when normalization changed it — a bare "68"
 *  landing as "fig-000068" should be traceable back to the line that produced it. */
function resultLabel(result: BulkAddMinifigResultItem): string {
  if (!result.fig_num) return result.input_reference;
  return result.fig_num === result.input_reference
    ? result.fig_num
    : `${result.input_reference} → ${result.fig_num}`;
}

/**
 * Report for a finished bulk minifig add. Every line is reported individually — a paste of twenty
 * references with one BrickLink link in it needs to say which one, not just that something failed.
 *
 * There is no "already owned" outcome, unlike the set report: a second copy of a minifig is a
 * second figure in the box, so it is added and merely noted.
 */
export function AddMinifigsResultDialog({ results, onClose }: AddMinifigsResultDialogProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  const added = results.filter((r) => r.status === "ok");
  const failed = results.filter((r) => r.status === "error");
  const duplicates = added.filter((r) => r.already_owned_count > 0);

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
      : `All ${added.length} minifigure${added.length === 1 ? "" : "s"} added`;

  const summary = [
    `${added.length} added`,
    duplicates.length > 0 && `${duplicates.length} you already owned`,
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
        aria-labelledby="add-minifigs-results-title"
        className="relative flex max-h-[80vh] w-full max-w-md flex-col rounded border border-gray-300 bg-white shadow-xl"
      >
        <div className="border-b border-gray-200 p-4 pb-3">
          <h2 id="add-minifigs-results-title" className="text-base font-bold">
            {title}
          </h2>
          <p className="mt-0.5 font-mono text-xs text-gray-500">{summary}</p>
        </div>

        <div className="overflow-y-auto p-4">
          {added.length > 0 && (
            <section>
              <h3 className="flex items-baseline gap-2 text-sm font-semibold">
                <span className="h-2 w-2 rounded-full bg-green-600" aria-hidden="true" />
                Added
                <span className="font-mono text-xs font-normal text-gray-400">{added.length}</span>
              </h3>
              <ul className="mt-1 divide-y divide-gray-100 border-t border-gray-100">
                {added.map((item) => (
                  <li key={item.instance_id} className="flex flex-wrap gap-x-2 py-1 text-xs">
                    <span className="font-mono font-semibold">{resultLabel(item)}</span>
                    <span className="text-gray-500">{item.fig_name}</span>
                    {item.already_owned_count > 0 && (
                      <span className="text-amber-700">
                        you now own {item.already_owned_count + 1}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {failed.length > 0 && (
            <section className="mt-3">
              <h3 className="flex items-baseline gap-2 text-sm font-semibold">
                <span className="h-2 w-2 rounded-full bg-red-600" aria-hidden="true" />
                Failed
                <span className="font-mono text-xs font-normal text-gray-400">{failed.length}</span>
              </h3>
              <ul className="mt-1 divide-y divide-gray-100 border-t border-gray-100">
                {failed.map((item, index) => (
                  <li key={`${item.input_reference}-${index}`} className="flex flex-col py-1 text-xs">
                    <span className="font-mono font-semibold break-all">{item.input_reference}</span>
                    {/* The reason is the point of the report: it says whether to fix the line or retry. */}
                    <span className="text-red-600">{item.error ?? "unknown error"}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-gray-500">
                The failed lines were kept in the box so you can correct them and try again.
              </p>
            </section>
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
