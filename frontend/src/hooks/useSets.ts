import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addSet,
  adjustSetPartFound,
  bulkAddSets,
  deleteSet,
  getSet,
  getSetHistory,
  getSetMinifigs,
  listSets,
  resyncSet,
  setSetPartsFound,
  updateSetSorting,
  updateSetPartCondition,
} from "../api/client";
import type { PartFoundTarget, PartOut, SetDetail, SetSummary } from "../api/types";
import {
  applyFoundDelta,
  applyPartCondition,
  replacePart,
  replaceParts,
  totalFound,
  totalUnaccounted,
} from "../lib/parts";
import { minifigsKeys } from "./useMinifigs";

export const setsKeys = {
  all: ["sets"] as const,
  detail: (setNum: string) => ["sets", setNum] as const,
  historyAll: (setNum: string) => ["sets", setNum, "history"] as const,
  history: (setNum: string, partNum?: string, colorId?: number) =>
    ["sets", setNum, "history", partNum, colorId] as const,
  minifigs: (setNum: string) => ["sets", setNum, "minifigs"] as const,
};

/**
 * Recompute a cached set's rolled-up totals from the parts list we just edited, mirroring the
 * backend's rules: spares excluded, and unfound pieces only count as missing once sorting is done.
 */
function withSetTotals(set: SetDetail, parts: PartOut[]): SetDetail {
  const found = totalFound(parts);
  const isSorted = set.sorting_finished_at !== null;
  const unaccounted = totalUnaccounted(parts);
  const isComplete = found >= set.quantity_required_total;
  return {
    ...set,
    parts,
    quantity_found_total: found,
    quantity_missing_total: isSorted ? unaccounted : 0,
    is_complete: isComplete,
    status: isComplete ? "complete" : isSorted ? "sorted" : found > 0 ? "sorting" : "not_started",
  };
}

export function useSets() {
  return useQuery({ queryKey: setsKeys.all, queryFn: listSets });
}

export function useSet(setNum: string) {
  return useQuery({ queryKey: setsKeys.detail(setNum), queryFn: () => getSet(setNum), enabled: !!setNum });
}

export function useAddSet() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (setNum: string) => addSet(setNum),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: setsKeys.all }),
  });
}

export function useBulkAddSets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (setNums: string[]) => bulkAddSets(setNums),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: setsKeys.all }),
  });
}

export function useDeleteSet() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (setNum: string) => deleteSet(setNum),
    onSuccess: (_data, setNum) => {
      queryClient.removeQueries({ queryKey: setsKeys.detail(setNum) });
      // The set's minifig instances and shopping-list contribution disappear with it.
      queryClient.invalidateQueries({ queryKey: setsKeys.all, exact: true });
      queryClient.invalidateQueries({ queryKey: minifigsKeys.all });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
    },
  });
}

export function useAdjustSetPartFound(setNum: string) {
  const queryClient = useQueryClient();
  const detailKey = setsKeys.detail(setNum);

  return useMutation({
    mutationFn: ({ partNum, colorId, foundDelta }: { partNum: string; colorId: number; foundDelta: number }) =>
      adjustSetPartFound(setNum, partNum, colorId, foundDelta),

    // Patch the cache rather than refetching: a large set is hundreds of parts, and a refetch per
    // tap makes the grid lag behind the finger while sorting bricks.
    onMutate: async ({ partNum, colorId, foundDelta }) => {
      await queryClient.cancelQueries({ queryKey: detailKey });
      const previous = queryClient.getQueryData<SetDetail>(detailKey);
      if (previous) {
        const parts = applyFoundDelta(previous.parts, partNum, colorId, foundDelta);
        queryClient.setQueryData<SetDetail>(detailKey, withSetTotals(previous, parts));
      }
      return { previous };
    },

    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(detailKey, context.previous);
    },

    onSuccess: (response) => {
      queryClient.setQueryData<SetDetail>(detailKey, (current) =>
        current ? withSetTotals(current, replacePart(current.parts, response.part)) : current,
      );
      queryClient.setQueryData<SetSummary[]>(setsKeys.all, (current) =>
        current?.map((summary) => (summary.set_num === setNum ? { ...summary, ...response.set_summary } : summary)),
      );
      queryClient.invalidateQueries({ queryKey: setsKeys.historyAll(setNum) });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

export function useUpdateSetPartCondition(setNum: string) {
  const queryClient = useQueryClient();
  const detailKey = setsKeys.detail(setNum);

  return useMutation({
    mutationFn: ({
      partNum,
      colorId,
      quantityFound,
      quantityBroken,
    }: {
      partNum: string;
      colorId: number;
      quantityFound: number;
      quantityBroken: number;
    }) => updateSetPartCondition(setNum, partNum, colorId, quantityFound, quantityBroken),
    onMutate: async ({ partNum, colorId, quantityFound, quantityBroken }) => {
      await queryClient.cancelQueries({ queryKey: detailKey });
      const previous = queryClient.getQueryData<SetDetail>(detailKey);
      if (previous) {
        const parts = applyPartCondition(
          previous.parts,
          partNum,
          colorId,
          quantityFound,
          quantityBroken,
        );
        queryClient.setQueryData<SetDetail>(detailKey, withSetTotals(previous, parts));
      }
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(detailKey, context.previous);
    },
    onSuccess: (response) => {
      queryClient.setQueryData<SetDetail>(detailKey, (current) =>
        current ? withSetTotals(current, replacePart(current.parts, response.part)) : current,
      );
      queryClient.setQueryData<SetSummary[]>(setsKeys.all, (current) =>
        current?.map((summary) =>
          summary.set_num === setNum ? { ...summary, ...response.set_summary } : summary,
        ),
      );
      queryClient.invalidateQueries({ queryKey: setsKeys.historyAll(setNum) });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

/**
 * Write many parts' found counts in one request. Backs "confirm everything still showing", which
 * otherwise means a tap and a round trip per remaining part.
 *
 * No optimistic patch here, unlike the single-tap mutation: the server decides which parts actually
 * changed, and a bulk action is a deliberate click rather than something raced against a finger.
 */
export function useSetPartsFound(setNum: string) {
  const queryClient = useQueryClient();
  const detailKey = setsKeys.detail(setNum);

  return useMutation({
    mutationFn: (parts: PartFoundTarget[]) => setSetPartsFound(setNum, parts),
    onSuccess: (response) => {
      queryClient.setQueryData<SetDetail>(detailKey, (current) =>
        current ? withSetTotals(current, replaceParts(current.parts, response.parts)) : current,
      );
      queryClient.setQueryData<SetSummary[]>(setsKeys.all, (current) =>
        current?.map((summary) => (summary.set_num === setNum ? { ...summary, ...response.summary } : summary)),
      );
      queryClient.invalidateQueries({ queryKey: setsKeys.historyAll(setNum) });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      queryClient.invalidateQueries({ queryKey: ["parts", "search"] });
    },
  });
}

/** Finishing sorting is what turns unfound pieces into confirmed missing ones. */
export function useUpdateSetSorting(setNum: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (finished: boolean) => updateSetSorting(setNum, finished),
    onSuccess: (updated) => {
      queryClient.setQueryData(setsKeys.detail(setNum), updated);
      queryClient.invalidateQueries({ queryKey: setsKeys.all, exact: true });
      // Whether this set contributes to the shopping list just changed.
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
    },
  });
}

export function useResyncSet(setNum: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => resyncSet(setNum),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: setsKeys.detail(setNum) });
      queryClient.invalidateQueries({ queryKey: setsKeys.all });
    },
  });
}

/** `enabled` lets callers defer the request until the log is actually opened. */
export function useSetHistory(setNum: string, options?: { enabled?: boolean; partNum?: string; colorId?: number }) {
  const { enabled = true, partNum, colorId } = options ?? {};
  return useQuery({
    queryKey: setsKeys.history(setNum, partNum, colorId),
    queryFn: () => getSetHistory(setNum, partNum, colorId),
    enabled: !!setNum && enabled,
  });
}

export function useSetMinifigs(setNum: string) {
  return useQuery({ queryKey: setsKeys.minifigs(setNum), queryFn: () => getSetMinifigs(setNum), enabled: !!setNum });
}
