import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CompletionBar } from "../components/CompletionBar";
import { HistoryLog } from "../components/HistoryLog";
import { ImageLightbox } from "../components/ImageLightbox";
import { PartsGrid } from "../components/PartsGrid";
import { ResyncButton } from "../components/ResyncButton";
import { SortingStateButton } from "../components/SortingStateButton";
import { StatusBadge } from "../components/StatusBadge";
import {
  useAdjustSetPartFound,
  useResyncSet,
  useSet,
  useSetHistory,
  useSetMinifigs,
  useSetPartsFound,
  useUpdateSetSorting,
} from "../hooks/useSets";
import { completionPercent } from "../lib/completion";

/**
 * Jumps to this set's minifigures on the Minifigures page, which is where they are tracked.
 * A set with none says so rather than offering a link into an empty view — that is also how a
 * roster that failed to fetch becomes visible from the set itself.
 */
function MinifigsLink({ setNum, count, isLoading }: { setNum: string; count: number; isLoading: boolean }) {
  if (isLoading) return null;

  if (count === 0) {
    return (
      <span
        className="flex-shrink-0 rounded border border-dashed border-gray-300 px-3 py-1.5 text-sm text-gray-400"
        title="This set has no tracked minifigures. If it should have some, resync it."
      >
        No minifigures
      </span>
    );
  }

  return (
    <Link
      to={`/minifigs?set=${encodeURIComponent(setNum)}`}
      className="ui-control ui-control-secondary ui-control-md flex-shrink-0 gap-1.5"
    >
      Minifigures <span className="font-mono text-xs text-gray-500">{count}</span>
    </Link>
  );
}

export function SetDetailPage() {
  const { setNum = "" } = useParams<{ setNum: string }>();
  const { data: set, isLoading, error } = useSet(setNum);
  const adjustFound = useAdjustSetPartFound(setNum);
  const setPartsFound = useSetPartsFound(setNum);
  const updateSorting = useUpdateSetSorting(setNum);
  const resync = useResyncSet(setNum);
  const minifigs = useSetMinifigs(setNum);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [imageOpen, setImageOpen] = useState(false);
  const history = useSetHistory(setNum, { enabled: historyOpen });

  if (isLoading) return <p className="p-4 text-sm text-gray-500">Loading...</p>;
  if (error || !set) return <p className="p-4 text-sm text-red-600">Set not found.</p>;

  const unaccounted = set.quantity_required_total - set.quantity_found_total;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 p-4 pb-2">
        <div className="h-20 w-20 flex-shrink-0 overflow-hidden rounded border border-gray-200 bg-white">
          {set.image_url && (
            <button
              type="button"
              onClick={() => setImageOpen(true)}
              title="Show larger image"
              className="h-full w-full cursor-zoom-in"
            >
              <img src={set.image_url} alt={set.name} className="h-full w-full object-contain" />
            </button>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-bold">
            {set.set_num} &mdash; {set.name}
          </h1>
          <p className="text-sm text-gray-600">
            {set.quantity_found_total} of {set.quantity_required_total} pieces found &middot;{" "}
            {completionPercent(set)}%
          </p>
          <div className="mt-1.5 flex items-center gap-2">
            <StatusBadge status={set.status} missingCount={set.quantity_missing_total} />
            {!set.is_complete && set.status !== "sorted" && (
              <span className="font-mono text-[11px] text-gray-500">{unaccounted} left to check</span>
            )}
          </div>
          <CompletionBar entity={set} className="mt-1.5 max-w-xs" />
        </div>
        <MinifigsLink setNum={set.set_num} count={minifigs.data?.length ?? 0} isLoading={minifigs.isLoading} />
        <SortingStateButton
          status={set.status}
          isSorted={set.sorting_finished_at !== null}
          unaccountedCount={unaccounted}
          isPending={updateSorting.isPending}
          onChange={(finished) => updateSorting.mutate(finished)}
        />
        <ResyncButton onClick={() => resync.mutate()} isPending={resync.isPending} />
      </div>

      <PartsGrid
        parts={set.parts}
        status={set.status}
        onMark={(partNum, colorId, foundDelta) => adjustFound.mutate({ partNum, colorId, foundDelta })}
        onSetPartsFound={(targets) => setPartsFound.mutateAsync(targets)}
        isBulkPending={setPartsFound.isPending}
      />

      <HistoryLog
        entries={history.data}
        parts={set.parts}
        isLoading={history.isLoading}
        isOpen={historyOpen}
        onToggle={() => setHistoryOpen((v) => !v)}
      />

      {imageOpen && set.image_url && (
        <ImageLightbox src={set.image_url} alt={set.name} onClose={() => setImageOpen(false)} />
      )}
    </div>
  );
}
