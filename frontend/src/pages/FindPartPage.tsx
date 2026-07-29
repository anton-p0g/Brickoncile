import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { PartSearchResultOut, PartSourceOut } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";
import { useMarkFoundFromSearch, usePartSearch } from "../hooks/usePartSearch";

/** Long enough that typing a part number does not fire a request per keystroke. */
const SEARCH_DEBOUNCE_MS = 250;

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function sourceHref(source: PartSourceOut): string {
  return source.source_type === "set"
    ? `/sets/${encodeURIComponent(source.source_id)}`
    : `/minifigs/${encodeURIComponent(source.source_id)}`;
}

interface SourceRowProps {
  result: PartSearchResultOut;
  source: PartSourceOut;
  onMark: (source: PartSourceOut, foundDelta: number) => void;
  isPending: boolean;
}

function SourceRow({ result, source, onMark, isPending }: SourceRowProps) {
  const satisfied = source.quantity_unaccounted <= 0;

  return (
    <li className="flex flex-wrap items-center gap-2 border-t border-gray-100 px-3 py-1.5 first:border-t-0">
      <Link
        to={sourceHref(source)}
        className="min-w-0 flex-1 truncate text-sm hover:underline"
        title={`Open ${source.label}`}
      >
        <span className="font-mono font-semibold">{source.label}</span>
        {source.source_type === "minifig_instance" && (
          <span className="ml-1.5 text-xs text-gray-400">minifig</span>
        )}
      </Link>

      <StatusBadge
        status={source.status}
        missingCount={source.quantity_unaccounted}
      />

      <span className="font-mono text-[11px] text-gray-500">
        {source.quantity_found} of {source.quantity_required} found
      </span>

      {satisfied ? (
        <span className="font-mono text-[11px] font-semibold text-green-700">
          nothing needed
        </span>
      ) : (
        <span className="flex items-center gap-1">
          <span className="rounded-full bg-red-600 px-2 py-0.5 font-mono text-[11px] font-bold text-white">
            needs {source.quantity_unaccounted}
          </span>
          <button
            type="button"
            onClick={() => onMark(source, 1)}
            disabled={isPending}
            title={`Record one ${result.part_num} found for ${source.label}`}
            className="rounded border border-green-600 bg-white px-2 py-0.5 text-xs font-semibold text-green-700 hover:bg-green-50 disabled:opacity-50"
          >
            +1 found
          </button>
          {source.quantity_unaccounted > 1 && (
            <button
              type="button"
              onClick={() => onMark(source, source.quantity_unaccounted)}
              disabled={isPending}
              title={`Record all ${source.quantity_unaccounted} found for ${source.label}`}
              className="rounded border border-gray-300 bg-white px-2 py-0.5 text-xs hover:border-gray-500 disabled:opacity-50"
            >
              all {source.quantity_unaccounted}
            </button>
          )}
        </span>
      )}
    </li>
  );
}

function ResultCard({
  result,
  onMark,
  isPending,
}: {
  result: PartSearchResultOut;
  onMark: (source: PartSourceOut, foundDelta: number) => void;
  isPending: boolean;
}) {
  // Sources that still want a copy are the actionable ones, so they lead.
  const sources = useMemo(
    () =>
      [...result.sources].sort(
        (a, b) => b.quantity_unaccounted - a.quantity_unaccounted,
      ),
    [result.sources],
  );

  return (
    <li className="overflow-hidden rounded border border-gray-300 bg-white">
      <div className="flex items-center gap-3 border-b border-gray-200 bg-gray-50 p-2">
        <div className="h-14 w-14 flex-shrink-0 overflow-hidden rounded bg-gray-100">
          {result.image_url && (
            <img
              src={result.image_url}
              alt={result.part_name}
              loading="lazy"
              className="h-full w-full object-contain"
            />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate font-mono text-sm font-bold">
            {result.part_num}{" "}
            <span className="font-normal text-gray-600">
              {result.color_name}
            </span>
          </div>
          <div className="truncate text-xs text-gray-500">
            {result.part_name}
          </div>
          {result.element_id && (
            <div className="font-mono text-[11px] text-gray-400">
              element {result.element_id}
            </div>
          )}
        </div>
        {result.total_needed > 0 ? (
          <span className="flex-shrink-0 rounded-full bg-red-600 px-2 py-0.5 font-mono text-xs font-bold text-white">
            {result.total_needed} wanted
          </span>
        ) : (
          <span className="flex-shrink-0 font-mono text-[11px] font-semibold text-green-700">
            all accounted for
          </span>
        )}
      </div>

      <ul>
        {sources.map((source) => (
          <SourceRow
            key={`${source.source_type}-${source.source_id}`}
            result={result}
            source={source}
            onMark={onMark}
            isPending={isPending}
          />
        ))}
      </ul>
    </li>
  );
}

export function FindPartPage() {
  const [query, setQuery] = useState("");
  const [hideSatisfied, setHideSatisfied] = useState(false);
  const debouncedQuery = useDebounced(query, SEARCH_DEBOUNCE_MS);
  const { data: results = [], isFetching } = usePartSearch(debouncedQuery);
  const markFound = useMarkFoundFromSearch();

  const visible = hideSatisfied
    ? results.filter((r) => r.total_needed > 0)
    : results;
  const hasQuery = debouncedQuery.trim().length > 0;

  function handleMark(
    source: PartSourceOut,
    result: PartSearchResultOut,
    foundDelta: number,
  ) {
    markFound.mutate({
      source,
      partNum: result.part_num,
      colorId: result.color_id,
      foundDelta,
    });
  }

  return (
    <div>
      <div className="border-b border-gray-200 bg-gray-50 p-4">
        <h1 className="text-lg font-bold">Find a brick</h1>
        <p className="mt-0.5 text-sm text-gray-600">
          Type the number moulded into the piece, or describe it, to see which
          of your sets still wants one.
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Part number, name or element id"
            aria-label="Search for a part"
            autoFocus
            className="min-w-56 flex-1 rounded border border-gray-300 px-3 py-1.5 text-sm"
          />
          <button
            type="button"
            aria-pressed={hideSatisfied}
            onClick={() => setHideSatisfied((v) => !v)}
            className={`rounded-full border px-2 py-0.5 text-xs ${
              hideSatisfied
                ? "border-gray-900 bg-gray-900 text-white"
                : "border-gray-300 bg-white"
            }`}
          >
            Only what is still wanted
          </button>
          {isFetching && (
            <span className="text-xs text-gray-400">Searching...</span>
          )}
        </div>
      </div>

      <div className="p-4">
        {!hasQuery ? (
          <p className="text-sm text-gray-500"></p>
        ) : results.length === 0 && !isFetching ? (
          <p className="text-sm text-gray-500">
            No part in your collection matches{" "}
            <span className="font-mono">{debouncedQuery}</span>. It may belong
            to a set you have not added yet.
          </p>
        ) : visible.length === 0 ? (
          <p className="text-sm text-gray-500">
            Every set holding this piece is already accounted for. Spares bin.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {visible.map((result) => (
              <ResultCard
                key={`${result.part_num}-${result.color_id}`}
                result={result}
                onMark={(source, foundDelta) =>
                  handleMark(source, result, foundDelta)
                }
                isPending={markFound.isPending}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
