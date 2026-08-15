import type { SortingStatus } from "../api/types";

interface Completable {
  quantity_required_total: number;
  quantity_found_total: number;
}

/**
 * Fraction of an inventory's required pieces confirmed present, in [0, 1]. This doubles as sorting
 * progress while working through a pile and as completeness once finished, because both questions
 * are answered by the same number.
 */
export function completionRatio({ quantity_required_total, quantity_found_total }: Completable): number {
  if (quantity_required_total <= 0) return 1;
  return Math.min(1, Math.max(0, quantity_found_total / quantity_required_total));
}

/**
 * Completion as a whole-number percent. Rounded toward 99 so that an inventory with any piece still
 * unaccounted for never reads as "100%".
 */
export function completionPercent(entity: Completable): number {
  const ratio = completionRatio(entity);
  if (ratio === 1) return 100;
  return Math.min(99, Math.round(ratio * 100));
}

export const STATUS_LABELS: Record<SortingStatus, string> = {
  not_started: "not started",
  sorting: "sorting",
  sorted: "sorted",
  complete: "complete",
};

/** Tailwind classes per status. Amber marks work in progress, red confirmed loss, green done. */
export const STATUS_CLASSES: Record<SortingStatus, string> = {
  not_started: "bg-gray-200 text-gray-700",
  sorting: "bg-amber-500 text-white",
  sorted: "bg-red-600 text-white",
  complete: "bg-green-600 text-white",
};

/**
 * The same four status colours as hex, for SVG charts, which cannot wear Tailwind classes.
 *
 * Red and green are close enough under red-green colour blindness that hue alone cannot separate
 * them, so every chart using these pairs the colour with a label or a distinct marker shape and
 * never asks the colour to carry the meaning by itself.
 */
export const STATUS_HEX: Record<SortingStatus, string> = {
  not_started: "#9ca3af",
  sorting: "#f59e0b",
  sorted: "#dc2626",
  complete: "#16a34a",
};
