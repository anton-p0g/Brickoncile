import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addLooseMinifig,
  addMinifigByReference,
  adjustMinifigPartFound,
  bulkAddMinifigsByReference,
  changeMinifigFigNum,
  deleteMinifigInstance,
  getMinifigInstance,
  identifyMinifig,
  getMinifigInstanceHistory,
  listMinifigInstances,
  markMinifigInstanceFound,
  resyncMinifigInstance,
  setMinifigInstancePartsFound,
  updateMinifigInstanceSorting,
} from "../api/client";
import type {
  MinifigInstanceDetail,
  MinifigInstanceSummary,
  PartFoundTarget,
  PartOut,
} from "../api/types";
import { applyFoundDelta, replacePart, replaceParts, totalFound, totalUnaccounted } from "../lib/parts";

export const minifigsKeys = {
  all: ["minifigs", "instances"] as const,
  identify: ["minifigs", "identify"] as const,
  detail: (instanceId: string) => ["minifigs", "instances", instanceId] as const,
  historyAll: (instanceId: string) => ["minifigs", "instances", instanceId, "history"] as const,
  history: (instanceId: string, partNum?: string, colorId?: number) =>
    ["minifigs", "instances", instanceId, "history", partNum, colorId] as const,
};

/** Mirror of withSetTotals for a minifig instance; see the comment there. */
function withInstanceTotals(instance: MinifigInstanceDetail, parts: PartOut[]): MinifigInstanceDetail {
  const found = totalFound(parts);
  const isSorted = instance.sorting_finished_at !== null;
  const unaccounted = totalUnaccounted(parts);
  const isComplete = found >= instance.quantity_required_total;
  return {
    ...instance,
    parts,
    quantity_found_total: found,
    quantity_missing_total: isSorted ? unaccounted : 0,
    is_complete: isComplete,
    status: isComplete ? "complete" : isSorted ? "sorted" : found > 0 ? "sorting" : "not_started",
  };
}

export function useMinifigInstances() {
  return useQuery({ queryKey: minifigsKeys.all, queryFn: listMinifigInstances });
}

export function useMinifigInstance(instanceId: string) {
  return useQuery({
    queryKey: minifigsKeys.detail(instanceId),
    queryFn: () => getMinifigInstance(instanceId),
    enabled: !!instanceId,
  });
}

export function useAdjustMinifigPartFound(instanceId: string) {
  const queryClient = useQueryClient();
  const detailKey = minifigsKeys.detail(instanceId);

  return useMutation({
    mutationFn: ({ partNum, colorId, foundDelta }: { partNum: string; colorId: number; foundDelta: number }) =>
      adjustMinifigPartFound(instanceId, partNum, colorId, foundDelta),

    // Patch the cache instead of refetching, so the grid responds on the tap itself.
    onMutate: async ({ partNum, colorId, foundDelta }) => {
      await queryClient.cancelQueries({ queryKey: detailKey });
      const previous = queryClient.getQueryData<MinifigInstanceDetail>(detailKey);
      if (previous) {
        const parts = applyFoundDelta(previous.parts, partNum, colorId, foundDelta);
        queryClient.setQueryData<MinifigInstanceDetail>(detailKey, withInstanceTotals(previous, parts));
      }
      return { previous };
    },

    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(detailKey, context.previous);
    },

    onSuccess: (response) => {
      queryClient.setQueryData<MinifigInstanceDetail>(detailKey, (current) =>
        current ? withInstanceTotals(current, replacePart(current.parts, response.part)) : current,
      );
      queryClient.setQueryData<MinifigInstanceSummary[]>(minifigsKeys.all, (current) =>
        current?.map((summary) =>
          summary.instance_id === instanceId ? { ...summary, ...response.instance_summary } : summary,
        ),
      );
      queryClient.invalidateQueries({ queryKey: minifigsKeys.historyAll(instanceId) });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

/** Bulk counterpart to useAdjustMinifigPartFound. See useSetPartsFound. */
export function useMinifigInstancePartsFound(instanceId: string) {
  const queryClient = useQueryClient();
  const detailKey = minifigsKeys.detail(instanceId);

  return useMutation({
    mutationFn: (parts: PartFoundTarget[]) => setMinifigInstancePartsFound(instanceId, parts),
    onSuccess: (response) => {
      queryClient.setQueryData<MinifigInstanceDetail>(detailKey, (current) =>
        current ? withInstanceTotals(current, replaceParts(current.parts, response.parts)) : current,
      );
      queryClient.setQueryData<MinifigInstanceSummary[]>(minifigsKeys.all, (current) =>
        current?.map((summary) =>
          summary.instance_id === instanceId ? { ...summary, ...response.summary } : summary,
        ),
      );
      queryClient.invalidateQueries({ queryKey: minifigsKeys.historyAll(instanceId) });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

/**
 * Whole-minifig toggle for the roster card: confirm every piece at once, or put every count back
 * to zero if it was already confirmed.
 *
 * Clearing has no endpoint of its own — it is the bulk parts-found write with every target at 0,
 * which needs the parts list a summary does not carry, so the detail is fetched first. Written
 * without an instanceId so each card can own its own pending state.
 */
export function useToggleMinifigInstanceFound() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      instanceId,
      found,
    }: {
      instanceId: string;
      found: boolean;
    }): Promise<MinifigInstanceDetail> => {
      if (found) return markMinifigInstanceFound(instanceId);
      const detail = await queryClient.fetchQuery({
        queryKey: minifigsKeys.detail(instanceId),
        queryFn: () => getMinifigInstance(instanceId),
      });
      const response = await setMinifigInstancePartsFound(
        instanceId,
        detail.parts
          .filter((part) => !part.is_spare)
          .map((part) => ({ part_num: part.part_num, color_id: part.color_id, quantity_found: 0 })),
      );
      return withInstanceTotals(detail, replaceParts(detail.parts, response.parts));
    },

    onSuccess: (instance) => {
      const { parts: _parts, ...summary } = instance;
      queryClient.setQueryData(minifigsKeys.detail(instance.instance_id), instance);
      queryClient.setQueryData<MinifigInstanceSummary[]>(minifigsKeys.all, (current) =>
        current?.map((current_summary) =>
          current_summary.instance_id === instance.instance_id ? { ...current_summary, ...summary } : current_summary,
        ),
      );
      queryClient.invalidateQueries({ queryKey: minifigsKeys.historyAll(instance.instance_id) });
      // Its pieces just stopped, or started, being outstanding — both views of that are stale.
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

export function useUpdateMinifigSorting(instanceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (finished: boolean) => updateMinifigInstanceSorting(instanceId, finished),
    onSuccess: (updated) => {
      queryClient.setQueryData(minifigsKeys.detail(instanceId), updated);
      queryClient.invalidateQueries({ queryKey: minifigsKeys.all });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
    },
  });
}

export function useResyncMinifigInstance(instanceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => resyncMinifigInstance(instanceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: minifigsKeys.detail(instanceId) });
      queryClient.invalidateQueries({ queryKey: minifigsKeys.all });
    },
  });
}

export interface QueuedPhoto {
  /** Stable across the photo's life so its identification can be cached and prefetched. */
  id: string;
  file: File;
  previewUrl: string;
}

const PREFETCH_AHEAD = 1;
/** One photo ahead. Identifying costs a recogniser call and several catalog searches, and deciding
 * on the current photo takes long enough that a single head start is already fully hidden. */

/**
 * Identify a whole queue of photos, keeping ahead of the person working through it.
 *
 * Queries rather than a mutation, because the answer for a given photo is worth having before it is
 * asked for: the next photo is identified while the current one is still being decided, so moving on
 * shows a result immediately instead of starting a fresh wait. Results stay cached for the session,
 * which also makes stepping back to an earlier photo instant.
 */
export function useIdentifyQueue(photos: QueuedPhoto[], index: number) {
  return useQueries({
    queries: photos.map((photo, i) => ({
      queryKey: [...minifigsKeys.identify, photo.id],
      queryFn: () => identifyMinifig(photo.file),
      enabled: i <= index + PREFETCH_AHEAD,
      // The photo never changes, so its identification is never stale; a retry is explicit.
      staleTime: Infinity,
      retry: false,
    })),
  });
}

/** Confirms an identified minifig into the collection as one owned without a set. */
export function useAddLooseMinifig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (figNum: string) => addLooseMinifig(figNum),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: minifigsKeys.all });
      // A new instance brings parts nothing has accounted for yet, which both of these summarise.
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

/**
 * Accounts for a minifig an owned set already expects, rather than filing a loose duplicate.
 *
 * The set is left holding the copy it always listed, now complete, so the collection never grows a
 * second Sebulba just because one was photographed.
 */
export function useMarkMinifigInstanceFound() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (instanceId: string) => markMinifigInstanceFound(instanceId),
    onSuccess: (updated) => {
      queryClient.setQueryData(minifigsKeys.detail(updated.instance_id), updated);
      queryClient.invalidateQueries({ queryKey: minifigsKeys.all, exact: true });
      queryClient.invalidateQueries({ queryKey: minifigsKeys.historyAll(updated.instance_id) });
      // Its pieces stop being outstanding, which both of these summarise.
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

/** Everything a new loose minifig changes: the roster, and the two views of what is outstanding. */
function invalidateAfterAdd(queryClient: ReturnType<typeof useQueryClient>): void {
  queryClient.invalidateQueries({ queryKey: minifigsKeys.all });
  queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
  queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
}

/** Adds a minifig from a pasted link or fig ID — the manual route in when a photo will not resolve. */
export function useAddMinifigByReference() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reference: string) => addMinifigByReference(reference),
    onSuccess: () => invalidateAfterAdd(queryClient),
  });
}

/** Bulk counterpart. Invalidates once at the end rather than per line. */
export function useBulkAddMinifigsByReference() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (references: string[]) => bulkAddMinifigsByReference(references),
    onSuccess: (response) => {
      if (response.results.some((result) => result.status === "ok")) invalidateAfterAdd(queryClient);
    },
  });
}

/**
 * Refiles a loose minifig under a corrected catalog id.
 *
 * Every cache entry keyed on the old instance is dropped rather than patched: unless the outcome is
 * "unchanged" that instance no longer exists, and its parts, history and totals all described a
 * different figure.
 */
export function useChangeMinifigFigNum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ instanceId, figNum }: { instanceId: string; figNum: string }) =>
      changeMinifigFigNum(instanceId, figNum),
    onSuccess: (response) => {
      if (response.outcome !== "unchanged") {
        queryClient.removeQueries({ queryKey: minifigsKeys.detail(response.previous_instance_id) });
      }
      queryClient.setQueryData(minifigsKeys.detail(response.instance.instance_id), response.instance);
      // Exact, for the same reason as the delete below: a broad invalidation would refetch the
      // instance that just stopped existing.
      queryClient.invalidateQueries({ queryKey: minifigsKeys.all, exact: true });
      queryClient.invalidateQueries({
        queryKey: minifigsKeys.historyAll(response.instance.instance_id),
      });
      // A different parts list is now outstanding, and a claimed set is no longer short a minifig.
      queryClient.invalidateQueries({ queryKey: ["sets"] });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

/** Removes a loose minifig and its rows. Shared cached images are retained for other collections. */
export function useDeleteMinifigInstance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (instanceId: string) => deleteMinifigInstance(instanceId),
    onSuccess: (_data, instanceId) => {
      queryClient.removeQueries({ queryKey: minifigsKeys.detail(instanceId) });
      // Exact, because a detail key extends the list key: a broad invalidation would refetch the
      // instance that was just deleted and answer 404 while its page is still on screen.
      queryClient.invalidateQueries({ queryKey: minifigsKeys.all, exact: true });
      // Its parts stop counting towards what is still unaccounted for.
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

/** `enabled` lets callers defer the request until the log is actually opened. */
export function useMinifigInstanceHistory(
  instanceId: string,
  options?: { enabled?: boolean; partNum?: string; colorId?: number },
) {
  const { enabled = true, partNum, colorId } = options ?? {};
  return useQuery({
    queryKey: minifigsKeys.history(instanceId, partNum, colorId),
    queryFn: () => getMinifigInstanceHistory(instanceId, partNum, colorId),
    enabled: !!instanceId && enabled,
  });
}
