import { Link } from "react-router-dom";
import type { MinifigInstanceSummary } from "../api/types";
import { useToggleMinifigInstanceFound } from "../hooks/useMinifigs";
import { completionPercent } from "../lib/completion";
import { CompletionBar } from "./CompletionBar";
import { StatusBadge } from "./StatusBadge";

interface MinifigInstanceCardProps {
  instance: MinifigInstanceSummary;
  /** Hidden when the card already sits under a heading for its source set. */
  showSourceSet?: boolean;
  /** How the card reports a failed toggle, which it has nowhere of its own to show. */
  onError?: (message: string) => void;
}

function MissingImagePlaceholder() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-3 text-center text-gray-400">
      <svg
        aria-hidden="true"
        viewBox="0 0 32 32"
        className="h-10 w-10 text-gray-300"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="16" cy="8" r="4" />
        <path d="M10.5 14h11l2.5 8h-5l1 6h-8l1-6H8z" />
        <path d="M13 14v8M19 14v8M16 22v6" />
      </svg>
      <span className="text-[11px] leading-tight font-medium">No image available</span>
    </div>
  );
}

export function MinifigInstanceCard({ instance, showSourceSet = false, onError }: MinifigInstanceCardProps) {
  const borderClass = instance.status === "not_started" ? "border-blue-200 border-dashed" : "border-blue-200";
  const toggle = useToggleMinifigInstanceFound();
  // While the write is in flight the box shows where it is going, not where it has been.
  const checked = toggle.isPending ? toggle.variables.found : instance.is_complete;

  return (
    <div className="group relative w-40 flex-shrink-0 rounded transition-[box-shadow,transform] duration-150 hover:-translate-y-0.5 hover:shadow-sm">
      <Link
        to={`/minifigs/${encodeURIComponent(instance.instance_id)}`}
        className={`flex h-full flex-col gap-1.5 rounded border bg-white p-2 transition-colors duration-150 group-hover:border-blue-400 ${borderClass}`}
      >
        <div className="aspect-square w-full overflow-hidden rounded bg-gray-100">
          {instance.image_url ? (
            <img src={instance.image_url} alt={instance.fig_name} className="h-full w-full object-contain" loading="lazy" />
          ) : (
            <MissingImagePlaceholder />
          )}
        </div>
        <div className="text-[10px] font-bold tracking-wide text-blue-600 uppercase">Minifig</div>
        <div className="truncate text-sm font-semibold">{instance.fig_name}</div>
        <div className="font-mono text-[11px] text-gray-400">{instance.fig_num}</div>
        {showSourceSet && (
          <div className="text-xs text-gray-600">
            {instance.source_set_num ? `from set ${instance.source_set_num}` : "loose — no set"}
          </div>
        )}
        <div className="mt-auto flex flex-col gap-1">
          <div className="flex items-baseline justify-between font-mono text-[11px]">
            <span className={instance.is_complete ? "font-bold text-green-600" : "font-bold text-gray-700"}>
              {completionPercent(instance)}%
            </span>
            <span className="text-gray-400">
              {instance.quantity_found_total}/{instance.quantity_required_total}
            </span>
          </div>
          <CompletionBar entity={instance} status={instance.status} />
          <StatusBadge status={instance.status} missingCount={instance.quantity_missing_total} />
        </div>
      </Link>

      {/* Outside the Link, so confirming a whole minifig does not also open it — which is the
          round trip this replaces. */}
      <input
        type="checkbox"
        checked={checked}
        disabled={toggle.isPending}
        onChange={(event) =>
          toggle.mutate(
            { instanceId: instance.instance_id, found: event.target.checked },
            {
              onError: (error) =>
                onError?.(
                  `Could not update ${instance.fig_name}: ${error instanceof Error ? error.message : "unknown error"}`,
                ),
            },
          )
        }
        title={checked ? "Uncheck to clear every part of this minifigure" : "Check to confirm every part of this minifigure"}
        aria-label={`Every part of ${instance.fig_name} found`}
        className="absolute top-3 right-3 h-5 w-5 cursor-pointer rounded accent-green-600 shadow-sm disabled:opacity-50"
      />
    </div>
  );
}
