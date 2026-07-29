import type { SortingStatus } from "../api/types";
import { completionPercent } from "../lib/completion";

interface CompletionBarProps {
  entity: { quantity_required_total: number; quantity_found_total: number };
  /** Drives the fill colour: amber while sorting, red once pieces are confirmed missing. */
  status?: SortingStatus;
  className?: string;
}

const FILL_CLASSES: Record<SortingStatus, string> = {
  not_started: "bg-gray-400",
  sorting: "bg-amber-500",
  sorted: "bg-red-500",
  complete: "bg-green-600",
};

/** Thin progress track showing how much of an inventory is confirmed present. */
export function CompletionBar({ entity, status = "sorting", className = "" }: CompletionBarProps) {
  const percent = completionPercent(entity);

  return (
    <div
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Percent of pieces found"
      className={`h-1.5 w-full overflow-hidden rounded-full bg-gray-200 ${className}`}
    >
      <div
        className={`h-full rounded-full transition-[width] ${FILL_CLASSES[status]}`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
