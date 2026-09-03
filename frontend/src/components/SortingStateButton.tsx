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
        className="ui-control ui-control-secondary ui-control-md flex-shrink-0"
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
      className="ui-control ui-control-primary ui-control-md flex-shrink-0"
    >
      {isPending
        ? "Working..."
        : unaccountedCount > 0
          ? `Finish sorting (${unaccountedCount} missing)`
          : "Finish sorting"}
    </button>
  );
}
