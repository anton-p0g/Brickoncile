import type {
  AddMinifigByReferenceResponse,
  AddSetResponse,
  BulkAddMinifigsResponse,
  BulkAddSetsResponse,
  ChangeMinifigFigNumResponse,
  CollectionOut,
  CollectionStatsOut,
  GroupBy,
  HistoryEntryOut,
  IdentifyMinifigResponse,
  MarkMinifigPartResponse,
  MarkSetPartResponse,
  MinifigInstanceDetail,
  MinifigInstanceSummary,
  PartAggregateOut,
  PartFoundTarget,
  PartSearchResultOut,
  SetDetail,
  SetPartsFoundResponse,
  SetSummary,
  SourceAggregateOut,
} from "./types";

const API_BASE = "/api";
let activeCollectionId: string | null = null;

/** Set before collection-scoped screens mount, so every request is bound to one database. */
export function setApiCollectionId(collectionId: string | null): void {
  activeCollectionId = collectionId;
}

/** FastAPI puts the human-readable reason in `detail`; anything else is shown as-is so an
 *  unexpected failure still says something rather than being swallowed. */
function errorMessage(status: number, statusText: string, body: string): string {
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
  } catch {
    // Not JSON (a proxy error page, an empty body) — fall through to the raw text.
  }
  return body.trim() || `${status} ${statusText}`;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (activeCollectionId) headers.set("X-Collection-ID", activeCollectionId);
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(errorMessage(res.status, res.statusText, body));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function getHealth() {
  return apiFetch<{ status: string }>("/health");
}

// ---- Collections ----

export function listCollections() {
  return apiFetch<CollectionOut[]>("/collections");
}

export function createCollection(name: string) {
  return apiFetch<CollectionOut>("/collections", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

// ---- Sets ----

export function listSets() {
  return apiFetch<SetSummary[]>("/sets");
}

export function addSet(setNum: string) {
  return apiFetch<AddSetResponse>("/sets", { method: "POST", body: JSON.stringify({ set_num: setNum }) });
}

export function bulkAddSets(setNums: string[]) {
  return apiFetch<BulkAddSetsResponse>("/sets/bulk", { method: "POST", body: JSON.stringify({ set_nums: setNums }) });
}

export function getSet(setNum: string) {
  return apiFetch<SetDetail>(`/sets/${encodeURIComponent(setNum)}`);
}

/** `foundDelta` changes how many pieces are confirmed present; negative walks a find back. */
export function adjustSetPartFound(setNum: string, partNum: string, colorId: number, foundDelta: number) {
  return apiFetch<MarkSetPartResponse>(
    `/sets/${encodeURIComponent(setNum)}/parts/${encodeURIComponent(partNum)}/colors/${colorId}/found`,
    { method: "POST", body: JSON.stringify({ found_delta: foundDelta }) },
  );
}

/** Write many parts' found counts in one request, for confirming a whole filtered grid at once. */
export function setSetPartsFound(setNum: string, parts: PartFoundTarget[]) {
  return apiFetch<SetPartsFoundResponse>(`/sets/${encodeURIComponent(setNum)}/parts/found`, {
    method: "POST",
    body: JSON.stringify({ parts }),
  });
}

/** Finishing turns unfound pieces into confirmed missing ones; resuming withdraws that. */
export function updateSetSorting(setNum: string, finished: boolean) {
  return apiFetch<SetDetail>(`/sets/${encodeURIComponent(setNum)}/sorting`, {
    method: "POST",
    body: JSON.stringify({ finished }),
  });
}

export function deleteSet(setNum: string) {
  return apiFetch<void>(`/sets/${encodeURIComponent(setNum)}`, { method: "DELETE" });
}

/** Accounts for an assembled minifig in hand by confirming all of its pieces at once. */
export function markMinifigInstanceFound(instanceId: string) {
  return apiFetch<MinifigInstanceDetail>(
    `/minifigs/instances/${encodeURIComponent(instanceId)}/found`,
    { method: "POST" },
  );
}

/** Loose minifigs only; the API refuses one a set accounts for, since a resync would restore it. */
export function deleteMinifigInstance(instanceId: string) {
  return apiFetch<void>(`/minifigs/instances/${encodeURIComponent(instanceId)}`, { method: "DELETE" });
}

export function resyncSet(setNum: string) {
  return apiFetch<SetDetail>(`/sets/${encodeURIComponent(setNum)}/resync`, { method: "POST" });
}

export function getSetHistory(setNum: string, partNum?: string, colorId?: number) {
  const params = new URLSearchParams();
  if (partNum !== undefined) params.set("part_num", partNum);
  if (colorId !== undefined) params.set("color_id", String(colorId));
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<HistoryEntryOut[]>(`/sets/${encodeURIComponent(setNum)}/history${query}`);
}

export function getSetMinifigs(setNum: string) {
  return apiFetch<MinifigInstanceSummary[]>(`/sets/${encodeURIComponent(setNum)}/minifigs`);
}

// ---- Minifigs ----

export function listMinifigInstances() {
  return apiFetch<MinifigInstanceSummary[]>("/minifigs/instances");
}

export function getMinifigInstance(instanceId: string) {
  return apiFetch<MinifigInstanceDetail>(`/minifigs/instances/${encodeURIComponent(instanceId)}`);
}

export function adjustMinifigPartFound(
  instanceId: string,
  partNum: string,
  colorId: number,
  foundDelta: number,
) {
  return apiFetch<MarkMinifigPartResponse>(
    `/minifigs/instances/${encodeURIComponent(instanceId)}/parts/${encodeURIComponent(partNum)}/colors/${colorId}/found`,
    { method: "POST", body: JSON.stringify({ found_delta: foundDelta }) },
  );
}

export function setMinifigInstancePartsFound(instanceId: string, parts: PartFoundTarget[]) {
  return apiFetch<SetPartsFoundResponse>(
    `/minifigs/instances/${encodeURIComponent(instanceId)}/parts/found`,
    { method: "POST", body: JSON.stringify({ parts }) },
  );
}

export function updateMinifigInstanceSorting(instanceId: string, finished: boolean) {
  return apiFetch<MinifigInstanceDetail>(`/minifigs/instances/${encodeURIComponent(instanceId)}/sorting`, {
    method: "POST",
    body: JSON.stringify({ finished }),
  });
}

export function resyncMinifigInstance(instanceId: string) {
  return apiFetch<MinifigInstanceDetail>(`/minifigs/instances/${encodeURIComponent(instanceId)}/resync`, {
    method: "POST",
  });
}

export function getMinifigInstanceHistory(instanceId: string, partNum?: string, colorId?: number) {
  const params = new URLSearchParams();
  if (partNum !== undefined) params.set("part_num", partNum);
  if (colorId !== undefined) params.set("color_id", String(colorId));
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<HistoryEntryOut[]>(`/minifigs/instances/${encodeURIComponent(instanceId)}/history${query}`);
}

/**
 * Identify a photographed minifig. Read-only: it suggests candidates but changes nothing, so it
 * is safe to re-run on a different photo until one of the results is recognisably right.
 *
 * `Content-Type` is deliberately left unset — the browser has to set the multipart boundary
 * itself, and apiFetch's JSON default would break the upload.
 */
export function identifyMinifig(photo: File) {
  const body = new FormData();
  body.append("photo", photo);
  return apiFetch<IdentifyMinifigResponse>("/minifigs/identify", { method: "POST", body, headers: {} });
}

/** Take a confirmed fig_num into the collection as a minifig owned without a set. */
export function addLooseMinifig(figNum: string) {
  return apiFetch<MinifigInstanceDetail>("/minifigs/instances/loose", {
    method: "POST",
    body: JSON.stringify({ fig_num: figNum }),
  });
}

/**
 * Add a minifig from pasted text: a Rebrickable link or fig ID, or a BrickLink link.
 *
 * The manual way in when a photo cannot be identified. A reference that cannot become a fig ID
 * fails with 400 and a message explaining which part of it could not be read.
 */
export function addMinifigByReference(reference: string) {
  return apiFetch<AddMinifigByReferenceResponse>("/minifigs/instances/manual", {
    method: "POST",
    body: JSON.stringify({ reference }),
  });
}

/** Bulk counterpart, reporting each pasted line separately so one bad entry costs only itself. */
export function bulkAddMinifigsByReference(references: string[]) {
  return apiFetch<BulkAddMinifigsResponse>("/minifigs/instances/manual/bulk", {
    method: "POST",
    body: JSON.stringify({ references }),
  });
}

/**
 * Correct which catalog entry a loose minifig is filed under.
 *
 * Loose instances only. The response says where the figure ended up, which is a different instance
 * than the one addressed unless the outcome is "unchanged".
 */
export function changeMinifigFigNum(instanceId: string, figNum: string) {
  return apiFetch<ChangeMinifigFigNumResponse>(
    `/minifigs/instances/${encodeURIComponent(instanceId)}/fig-num`,
    { method: "POST", body: JSON.stringify({ fig_num: figNum }) },
  );
}

// ---- Part search ----

/** "Which of my sets needs this brick?" — `q` matches part number, name, or element id. */
export function searchParts(q: string, colorId?: number) {
  const params = new URLSearchParams({ q });
  if (colorId !== undefined) params.set("color_id", String(colorId));
  return apiFetch<PartSearchResultOut[]>(`/parts/search?${params.toString()}`);
}

// ---- Missing parts ----

export function getMissingSummary(groupBy: GroupBy) {
  return apiFetch<PartAggregateOut[] | SourceAggregateOut[]>(`/missing-parts?group_by=${groupBy}`);
}

export function exportMissingPartsCsvUrl(groupBy: GroupBy) {
  const params = new URLSearchParams({ group_by: groupBy });
  if (activeCollectionId) params.set("collection_id", activeCollectionId);
  return `${API_BASE}/missing-parts/export.csv?${params.toString()}`;
}

// ---- Dashboard ----

/** Every dashboard section in one request, so the figures on screen always agree with each other. */
export function getCollectionStats() {
  return apiFetch<CollectionStatsOut>("/stats");
}
