import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adjustMinifigPartFound, adjustSetPartFound, searchParts } from "../api/client";
import type { PartSourceOut } from "../api/types";
import { minifigsKeys } from "./useMinifigs";
import { setsKeys } from "./useSets";

export const partSearchKeys = {
  all: ["parts", "search"] as const,
  query: (q: string, colorId?: number) => ["parts", "search", q, colorId] as const,
};

export function usePartSearch(query: string, colorId?: number) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: partSearchKeys.query(trimmed, colorId),
    queryFn: () => searchParts(trimmed, colorId),
    // The screen is driven by a brick in hand; an empty box is not a request for the whole collection.
    enabled: trimmed.length > 0,
  });
}

interface MarkFromSearchVariables {
  source: PartSourceOut;
  partNum: string;
  colorId: number;
  foundDelta: number;
}

/**
 * Mark a piece found straight from the search results.
 *
 * Without this the workflow breaks down exactly where it should pay off: you would look up the
 * brick, then navigate into the set and find the same part a second time to record it.
 *
 * Unlike the per-set mutations there is no optimistic patch, since one result row can touch any set
 * or minifig instance in the collection. Everything the change could affect is invalidated instead.
 */
export function useMarkFoundFromSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    // The two endpoints return differently-shaped summaries and neither is used here, since the
    // affected queries are refetched rather than patched. Discard both for one mutation type.
    mutationFn: async ({ source, partNum, colorId, foundDelta }: MarkFromSearchVariables): Promise<void> => {
      if (source.source_type === "set") {
        await adjustSetPartFound(source.source_id, partNum, colorId, foundDelta);
      } else {
        await adjustMinifigPartFound(source.source_id, partNum, colorId, foundDelta);
      }
    },

    onSuccess: (_data, { source }) => {
      queryClient.invalidateQueries({ queryKey: partSearchKeys.all });
      queryClient.invalidateQueries({ queryKey: ["missing-parts"] });
      if (source.source_type === "set") {
        queryClient.invalidateQueries({ queryKey: setsKeys.detail(source.source_id) });
        queryClient.invalidateQueries({ queryKey: setsKeys.all, exact: true });
      } else {
        queryClient.invalidateQueries({ queryKey: minifigsKeys.detail(source.source_id) });
        queryClient.invalidateQueries({ queryKey: minifigsKeys.all, exact: true });
      }
    },
  });
}
