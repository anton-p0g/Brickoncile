import type { PartFoundTarget, PartOut } from "../api/types";

/**
 * Identity of a part row within one inventory.
 *
 * part_num + color_id alone is not unique: a set can list the same part/colour twice, once as a
 * build part and once as a spare. Leaving is_spare out collapses those two rows into one key,
 * which duplicates cards in the grid and binds them to each other.
 */
export function partKey(part: PartOut): string {
  return `${part.part_num}-${part.color_id}-${part.is_spare ? "s" : "b"}`;
}

/** True for the one row a found request addresses: the tracked (non-spare) part, matching the server. */
function isTrackedPart(part: PartOut, partNum: string, colorId: number): boolean {
  return part.part_num === partNum && part.color_id === colorId && !part.is_spare;
}

/** The server clamps found counts to [0, quantity_required]; mirror it so optimistic updates agree. */
export function clampFound(part: PartOut, foundDelta: number): number {
  return Math.max(0, Math.min(part.quantity_required, part.quantity_found + foundDelta));
}

/** Apply a found-count delta to one part, leaving the rest of the list untouched. */
export function applyFoundDelta(parts: PartOut[], partNum: string, colorId: number, foundDelta: number): PartOut[] {
  return parts.map((part) => {
    if (!isTrackedPart(part, partNum, colorId)) return part;
    const found = clampFound(part, foundDelta);
    return {
      ...part,
      quantity_found: found,
      quantity_broken: Math.min(part.quantity_broken, found),
      quantity_unaccounted: part.quantity_required - found,
      is_fully_found: found >= part.quantity_required,
    };
  });
}

/** Apply the absolute counts used by the condition editor. Broken is a subset of found. */
export function applyPartCondition(
  parts: PartOut[],
  partNum: string,
  colorId: number,
  quantityFound: number,
  quantityBroken: number,
): PartOut[] {
  return parts.map((part) => {
    if (!isTrackedPart(part, partNum, colorId)) return part;
    const found = Math.max(0, Math.min(part.quantity_required, Math.round(quantityFound)));
    const broken = Math.max(0, Math.min(found, Math.round(quantityBroken)));
    return {
      ...part,
      quantity_found: found,
      quantity_broken: broken,
      quantity_unaccounted: part.quantity_required - found,
      is_fully_found: found >= part.quantity_required,
    };
  });
}

/** Swap in the authoritative part returned by a found request. */
export function replacePart(parts: PartOut[], updated: PartOut): PartOut[] {
  return parts.map((part) => (isTrackedPart(part, updated.part_num, updated.color_id) ? updated : part));
}

/** Swap in a whole batch at once, for the bulk confirm. One pass rather than one per part. */
export function replaceParts(parts: PartOut[], updated: PartOut[]): PartOut[] {
  if (updated.length === 0) return parts;
  const byKey = new Map(updated.map((part) => [partKey(part), part]));
  return parts.map((part) => byKey.get(partKey(part)) ?? part);
}

/** The parts a "confirm everything shown" action would actually change, with their target counts. */
export function pendingConfirmTargets(parts: PartOut[]): PartFoundTarget[] {
  return parts
    .filter((part) => !part.is_spare && !part.is_fully_found)
    .map((part) => ({ part_num: part.part_num, color_id: part.color_id, quantity_found: part.quantity_required }));
}

/** The same parts' current counts, which is what undoing that action puts back. */
export function currentFoundTargets(parts: PartOut[]): PartFoundTarget[] {
  return parts
    .filter((part) => !part.is_spare && !part.is_fully_found)
    .map((part) => ({ part_num: part.part_num, color_id: part.color_id, quantity_found: part.quantity_found }));
}

/** Pieces confirmed present across a parts list, excluding spares (matching the backend). */
export function totalFound(parts: PartOut[]): number {
  return parts.reduce((sum, part) => (part.is_spare ? sum : sum + part.quantity_found), 0);
}

/** Pieces still unaccounted for, excluding spares. Only means "missing" once sorting is finished. */
export function totalUnaccounted(parts: PartOut[]): number {
  return parts.reduce((sum, part) => (part.is_spare ? sum : sum + part.quantity_unaccounted), 0);
}
