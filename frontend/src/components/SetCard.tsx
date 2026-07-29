import { Link } from "react-router-dom";
import type { SetSummary } from "../api/types";
import { completionPercent } from "../lib/completion";
import { CompletionBar } from "./CompletionBar";
import { StatusBadge } from "./StatusBadge";

function TrashIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2.5 4.5h11" />
      <path d="M6.5 4.5V3h3v1.5" />
      <path d="M4 4.5l.7 8.2a1 1 0 0 0 1 .8h4.6a1 1 0 0 0 1-.8l.7-8.2" />
      <path d="M6.5 7v4M9.5 7v4" />
    </svg>
  );
}

interface SetCardProps {
  set: SetSummary;
  onRequestDelete: () => void;
}

export function SetCard({ set, onRequestDelete }: SetCardProps) {
  // A set nobody has started is the thing to surface, so give it a visible edge rather than
  // letting it blend in with finished ones.
  const borderClass =
    set.status === "not_started" ? "border-gray-400 border-dashed" : "border-gray-300";

  return (
    <div className={`relative flex h-full flex-col rounded border bg-white p-2 hover:border-gray-500 ${borderClass}`}>
      {/* Stretched link rather than a wrapping anchor, so the delete button is a real sibling
          button instead of interactive content nested inside an <a>. */}
      <Link
        to={`/sets/${encodeURIComponent(set.set_num)}`}
        aria-label={`Open ${set.set_num} ${set.name}`}
        className="absolute inset-0 z-10 rounded focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:outline-none"
      />

      <div className="pointer-events-none flex flex-1 flex-col gap-1.5">
        <div className="aspect-square w-full overflow-hidden rounded bg-gray-100">
          {set.image_url && (
            <img src={set.image_url} alt={set.name} className="h-full w-full object-contain" loading="lazy" />
          )}
        </div>
        <div className="text-sm font-bold">{set.set_num}</div>
        <div className="truncate text-xs text-gray-600">{set.name}</div>
        {set.root_theme_name && (
          // The line the set belongs to, not its narrower sub-theme, matching how the dashboard groups.
          <div className="truncate text-[11px] text-gray-400" title={set.theme_name ?? set.root_theme_name}>
            {set.root_theme_name}
          </div>
        )}
        <div className="mt-auto flex flex-col gap-1">
          <div className="flex items-baseline justify-between font-mono text-[11px]">
            <span className={set.is_complete ? "font-bold text-green-600" : "font-bold text-gray-700"}>
              {completionPercent(set)}%
            </span>
            <span className="text-gray-400">
              {set.quantity_found_total}/{set.quantity_required_total}
            </span>
          </div>
          <CompletionBar entity={set} status={set.status} />
          {/* Right padding keeps the badge clear of the delete button in the corner. */}
          <div className="pr-7">
            <StatusBadge status={set.status} missingCount={set.quantity_missing_total} />
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={onRequestDelete}
        aria-label={`Delete set ${set.set_num} ${set.name}`}
        title="Delete this set"
        className="absolute right-1 bottom-1 z-20 flex h-6 w-6 items-center justify-center rounded border border-gray-300 bg-white text-gray-400 transition hover:border-red-400 hover:text-red-600 focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:outline-none"
      >
        <TrashIcon />
      </button>
    </div>
  );
}
