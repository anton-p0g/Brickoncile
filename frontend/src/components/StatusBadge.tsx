import type { SortingStatus } from "../api/types";
import { STATUS_CLASSES, STATUS_LABELS } from "../lib/completion";

interface StatusBadgeProps {
  status: SortingStatus;
  /** Confirmed missing count, appended when the inventory is sorted and short of pieces. */
  missingCount?: number;
}

export function StatusBadge({ status, missingCount = 0 }: StatusBadgeProps) {
  const label =
    status === "sorted" && missingCount > 0 ? `${missingCount} missing` : STATUS_LABELS[status];

  return (
    <span className={`w-fit rounded px-1.5 py-0.5 font-mono text-[11px] font-bold ${STATUS_CLASSES[status]}`}>
      {label}
    </span>
  );
}
