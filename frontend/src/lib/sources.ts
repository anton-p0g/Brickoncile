/** The two kinds of inventory a part can belong to, as every cross-inventory response labels them. */
export interface SourceRef {
  source_type: "set" | "minifig_instance";
  source_id: string;
}

/**
 * Where a source opens. Shared by the part search and the missing parts grid so a set found in
 * either place leads to the same page.
 */
export function sourceHref(source: SourceRef): string {
  return source.source_type === "set"
    ? `/sets/${encodeURIComponent(source.source_id)}`
    : `/minifigs/${encodeURIComponent(source.source_id)}`;
}

/**
 * Identity of one "confirm a piece present" write: which inventory, which part line.
 *
 * The source alone is not enough to show which card is busy — one set is short of many parts — and
 * the part alone is not either, since the same part can be missing from several sets at once.
 */
export function markKey(sourceId: string, partNum: string, colorId: number): string {
  return `${sourceId}|${partNum}|${colorId}`;
}
