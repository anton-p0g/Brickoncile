import { useQuery } from "@tanstack/react-query";
import { getCollectionStats } from "../api/client";

export const statsKeys = {
  all: ["stats"] as const,
};

/**
 * The whole dashboard in one query.
 *
 * Nothing invalidates this from elsewhere: the dashboard is a read-only view, and every mutation
 * that would move a number on it happens on another screen, which unmounts this one. Coming back
 * refetches on mount, so the figures are current without a cache key threaded through every
 * sorting action in the app.
 */
export function useCollectionStats() {
  return useQuery({ queryKey: statsKeys.all, queryFn: getCollectionStats });
}
