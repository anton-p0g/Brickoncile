import type { SortingStatus } from "../api/types";
import { completionRatio } from "./completion";

export type SortOption =
  | "least-complete"
  | "most-complete"
  | "most-missing"
  | "recently-added"
  | "oldest"
  | "name";

export const SORT_LABELS: Record<SortOption, string> = {
  "least-complete": "Least complete first (%)",
  "most-complete": "Most complete first (%)",
  "most-missing": "Most pieces missing first",
  "recently-added": "Recently added",
  oldest: "Oldest first",
  name: "Name",
};

export const SORT_OPTIONS = Object.keys(SORT_LABELS) as SortOption[];

/** Guards a restored value: an option dropped since it was stored must not reach the comparator. */
export function isSortOption(value: unknown): value is SortOption {
  return typeof value === "string" && SORT_OPTIONS.includes(value as SortOption);
}

export interface Sortable {
  quantity_required_total: number;
  quantity_found_total: number;
  quantity_missing_total: number;
  added_at: string;
}

/**
 * Comparator shared by the dashboard and the minifigures roster so both screens offer the same
 * ordering. `nameOf` supplies whichever label counts as the item's name.
 */
export function compareBySort<T extends Sortable>(sort: SortOption, nameOf: (item: T) => string) {
  return (a: T, b: T): number => {
    switch (sort) {
      case "least-complete":
        return completionRatio(a) - completionRatio(b);
      case "most-complete":
        return completionRatio(b) - completionRatio(a);
      case "most-missing":
        return b.quantity_missing_total - a.quantity_missing_total;
      // added_at is ISO 8601 with a fixed offset, so lexicographic order is chronological.
      case "recently-added":
        return b.added_at.localeCompare(a.added_at);
      case "oldest":
        return a.added_at.localeCompare(b.added_at);
      case "name":
        return nameOf(a).localeCompare(nameOf(b));
    }
  };
}

export type StatusFilter = "all" | "not_started" | "sorting" | "sorted" | "complete";

/** Every filter but "all" names one status, and they are listed in the order work moves through them. */
export const STATUS_FILTER_LABELS: Record<StatusFilter, string> = {
  all: "All",
  not_started: "Not started",
  sorting: "Sorting",
  sorted: "Sorted",
  complete: "Complete",
};

export const STATUS_FILTERS = Object.keys(STATUS_FILTER_LABELS) as StatusFilter[];

export function isStatusFilter(value: unknown): value is StatusFilter {
  return typeof value === "string" && STATUS_FILTERS.includes(value as StatusFilter);
}

export function matchesStatusFilter(status: SortingStatus, filter: StatusFilter): boolean {
  return filter === "all" || status === filter;
}
