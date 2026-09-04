import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  adjustMinifigPartFound,
  adjustSetPartFound,
  searchParts,
  updateMinifigPartCondition,
  updateSetPartCondition,
} from "../api/client";
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

/**
 * Just enough of a source to address it. Structural, so both a search result's `PartSourceOut` and
 * a missing-parts contributor satisfy it without either page converting to the other's shape.
 */
export interface MarkFoundSource {
  source_type: PartSourceOut["source_type"];
  source_id: string;
}

interface MarkFoundVariables {
  source: MarkFoundSource;
  partNum: string;
  colorId: number;
  foundDelta: number;
  quantityFound?: never;
  quantityBroken?: never;
}

interface UpdateConditionVariables {
  source: MarkFoundSource;
  partNum: string;
  colorId: number;
  foundDelta?: never;
  quantityFound: number;
  quantityBroken: number;
}

type MarkFromSearchVariables = MarkFoundVariables | UpdateConditionVariables;

/**
 * Mark a piece found straight from a list that spans inventories — the part search, or the missing
 * parts grid.
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
    mutationFn: async (variables: MarkFromSearchVariables): Promise<void> => {
      const { source, partNum, colorId } = variables;
      if (source.source_type === "set") {
        if (variables.foundDelta !== undefined) {
          await adjustSetPartFound(source.source_id, partNum, colorId, variables.foundDelta);
        } else {
          await updateSetPartCondition(
            source.source_id,
            partNum,
            colorId,
            variables.quantityFound,
            variables.quantityBroken,
          );
        }
      } else {
        if (variables.foundDelta !== undefined) {
          await adjustMinifigPartFound(source.source_id, partNum, colorId, variables.foundDelta);
        } else {
          await updateMinifigPartCondition(
            source.source_id,
            partNum,
            colorId,
            variables.quantityFound,
            variables.quantityBroken,
          );
        }
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
