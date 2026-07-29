import type { SortingStatus } from "../api/types";

interface SortingStateButtonProps {
  status: SortingStatus;
  isSorted: boolean;
  unaccountedCount: number;
  isPending: boolean;
  onChange: (finished: boolean) => void;
}

/**
 * Finishing sorting is the moment unfound pieces become confirmed missing and start counting toward
 * the shopping list, so the label spells out what will happen rather than just saying "done".
 */
export function SortingStateButton({
  status,
  isSorted,
  unaccountedCount,
  isPending,
  onChange,
}: SortingStateButtonProps) {
  if (isSorted) {
    return (
      <button
        type="button"
        onClick={() => onChange(false)}
        disabled={isPending}
        className="flex-shrink-0 rounded border border-gray-300 bg-white px-3 py-1.5 text-sm hover:border-gray-500 disabled:opacity-50"
      >
        {isPending ? "Working..." : "Resume sorting"}
      </button>
    );
  }

  // Nothing checked off yet, so there is no sort to finish.
  if (status === "not_started") return null;

  return (
    <button
      type="button"
      onClick={() => onChange(true)}
      disabled={isPending}
      title={
        unaccountedCount > 0
          ? `Marks the ${unaccountedCount} unfound piece${unaccountedCount === 1 ? "" : "s"} as missing`
          : "Everything is accounted for"
      }
      className="flex-shrink-0 rounded border border-gray-900 bg-gray-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
    >
      {isPending
        ? "Working..."
        : unaccountedCount > 0
          ? `Finish sorting (${unaccountedCount} missing)`
          : "Finish sorting"}
    </button>
  );
}
