import { useQuery } from "@tanstack/react-query";
import { getMissingSummary } from "../api/client";
import type { GroupBy } from "../api/types";

export function useMissingSummary(groupBy: GroupBy) {
  return useQuery({ queryKey: ["missing-parts", groupBy], queryFn: () => getMissingSummary(groupBy) });
}
