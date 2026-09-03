import { useMemo, useState } from "react";
import type {
  ContributorOut,
  GroupBy,
  PartAggregateOut,
  SourceAggregateOut,
  SourceItemOut,
} from "../api/types";
import {
  ColorFilterSelect,
  type ColorOption,
} from "../components/ColorFilterSelect";
import { CopyListButton } from "../components/CopyListButton";
import { ExportCsvButton } from "../components/ExportCsvButton";
import { GroupToggle } from "../components/GroupToggle";
import { ImageLightbox } from "../components/ImageLightbox";
import { MissingPartCard } from "../components/MissingPartCard";
import { MissingSourceSection } from "../components/MissingSourceSection";
import { SortSelect } from "../components/SortSelect";
import { StatsBar } from "../components/StatsBar";
import { useMinifigInstances } from "../hooks/useMinifigs";
import { useMissingSummary } from "../hooks/useMissingParts";
import { useMarkFoundFromSearch } from "../hooks/usePartSearch";
import { useSets } from "../hooks/useSets";
import {
  isString,
  isStringArray,
  usePersistentState,
} from "../hooks/usePersistentState";
import { markKey } from "../lib/sources";

type MissingSort = "most-missing" | "part-num" | "color" | "name";

const MISSING_SORT_LABELS: Record<MissingSort, string> = {
  "most-missing": "Most missing first",
  "part-num": "Part number",
  color: "Colour",
  name: "Name",
};

const MISSING_SORT_OPTIONS = Object.keys(MISSING_SORT_LABELS) as MissingSort[];

function isMissingSort(value: unknown): value is MissingSort {
  return typeof value === "string" && value in MISSING_SORT_LABELS;
}

/** What the lightbox is currently showing. */
interface ZoomTarget {
  src: string;
  alt: string;
}

export function MissingPartsPage() {
  const [groupBy, setGroupBy] = usePersistentState<GroupBy>(
    "missing.groupBy",
    "part",
    (v): v is GroupBy => v === "part" || v === "set",
  );
  const [sort, setSort] = usePersistentState<MissingSort>(
    "missing.sort",
    "most-missing",
    isMissingSort,
  );
  const [search, setSearch] = usePersistentState(
    "missing.search",
    "",
    isString,
  );
  const [colorFilter, setColorFilter] = usePersistentState<number | null>(
    "missing.colorFilter",
    null,
    (v): v is number | null => v === null || typeof v === "number",
  );
  // Which by-set sections are open. Kept for the session, so working through one set's pile and
  // stepping into the set and back does not close it again.
  const [expanded, setExpanded] = usePersistentState<string[]>(
    "missing.expanded",
    [],
    isStringArray,
  );
  const [zoom, setZoom] = useState<ZoomTarget | null>(null);

  const { data, isLoading } = useMissingSummary(groupBy);
  const markFound = useMarkFoundFromSearch();
  // Only to explain an emptier page than expected; both lists are already cached by other screens.
  const sets = useSets();
  const minifigs = useMinifigInstances();

  const pendingKey = markFound.isPending
    ? markKey(
        markFound.variables.source.source_id,
        markFound.variables.partNum,
        markFound.variables.colorId,
      )
    : null;

  // Unfinished sorting contributes nothing here, which is why a set with gaps can be absent
  // entirely. Ones already fully found are left out of the count: finishing their sort would add
  // nothing to this page, so naming them would only overstate what is hidden.
  const stillSorting =
    (sets.data?.filter((s) => s.sorting_finished_at === null && !s.is_complete)
      .length ?? 0) +
    (minifigs.data?.filter(
      (m) => m.sorting_finished_at === null && !m.is_complete,
    ).length ?? 0);

  // Built from the unfiltered response so the list never shifts as you narrow the grid, and the
  // colour you just picked cannot disappear out of its own dropdown.
  const colorOptions = useMemo<ColorOption[]>(() => {
    if (!data) return [];
    const counts = new Map<number, ColorOption>();
    const count = (colorId: number, colorName: string) => {
      const existing = counts.get(colorId);
      if (existing) existing.count += 1;
      else counts.set(colorId, { colorId, colorName, count: 1 });
    };

    if (groupBy === "part") {
      for (const aggregate of data as PartAggregateOut[])
        count(aggregate.color_id, aggregate.color_name);
    } else {
      for (const aggregate of data as SourceAggregateOut[]) {
        for (const item of aggregate.items)
          count(item.color_id, item.color_name);
      }
    }
    return [...counts.values()].sort((a, b) =>
      a.colorName.localeCompare(b.colorName),
    );
  }, [data, groupBy]);

  const byPart = useMemo(() => {
    if (groupBy !== "part" || !data) return [];
    const query = search.trim().toLowerCase();
    const matching = (data as PartAggregateOut[]).filter((a) => {
      if (colorFilter !== null && a.color_id !== colorFilter) return false;
      if (!query) return true;
      return (
        a.part_num.toLowerCase().includes(query) ||
        a.part_name.toLowerCase().includes(query) ||
        a.color_name.toLowerCase().includes(query) ||
        a.contributors.some(
          (c) =>
            c.name.toLowerCase().includes(query) ||
            c.reference.toLowerCase().includes(query),
        )
      );
    });
    return [...matching].sort((a, b) => {
      switch (sort) {
        case "most-missing":
          return b.total_missing - a.total_missing;
        case "part-num":
          return a.part_num.localeCompare(b.part_num, undefined, {
            numeric: true,
          });
        case "color":
          return (
            a.color_name.localeCompare(b.color_name) ||
            a.part_num.localeCompare(b.part_num)
          );
        case "name":
          return a.part_name.localeCompare(b.part_name);
      }
    });
  }, [data, groupBy, search, sort, colorFilter]);

  const bySource = useMemo(() => {
    if (groupBy !== "set" || !data) return [];
    const query = search.trim().toLowerCase();
    return (data as SourceAggregateOut[])
      .map((aggregate) => {
        // A text hit on the set keeps all of its parts; otherwise the parts are matched themselves.
        // The colour filter is applied either way — it narrows what you are looking at, not what
        // you searched for.
        const sourceMatches =
          !query ||
          aggregate.name.toLowerCase().includes(query) ||
          aggregate.reference.toLowerCase().includes(query);
        const items = aggregate.items.filter((i) => {
          if (colorFilter !== null && i.color_id !== colorFilter) return false;
          if (sourceMatches) return true;
          return (
            i.part_num.toLowerCase().includes(query) ||
            i.part_name.toLowerCase().includes(query) ||
            i.color_name.toLowerCase().includes(query)
          );
        });
        const sorted = [...items].sort((a, b) => {
          switch (sort) {
            case "most-missing":
              return b.quantity_missing - a.quantity_missing;
            case "part-num":
              return a.part_num.localeCompare(b.part_num, undefined, {
                numeric: true,
              });
            case "color":
              return (
                a.color_name.localeCompare(b.color_name) ||
                a.part_num.localeCompare(b.part_num)
              );
            case "name":
              return a.part_name.localeCompare(b.part_name);
          }
        });
        return { ...aggregate, items: sorted };
      })
      .filter((aggregate) => aggregate.items.length > 0)
      .sort((a, b) =>
        sort === "name" || sort === "color"
          ? a.name.localeCompare(b.name)
          : b.total_missing - a.total_missing,
      );
  }, [data, groupBy, search, sort, colorFilter]);

  const totals = useMemo(() => {
    if (!data) return { pieces: 0, lines: 0, sources: 0 };
    if (groupBy === "part") {
      const aggregates = data as PartAggregateOut[];
      const sources = new Set(
        aggregates.flatMap((a) =>
          a.contributors.map((c) => `${c.source_type}-${c.source_id}`),
        ),
      );
      return {
        pieces: aggregates.reduce((sum, a) => sum + a.total_missing, 0),
        lines: aggregates.length,
        sources: sources.size,
      };
    }
    const aggregates = data as SourceAggregateOut[];
    return {
      pieces: aggregates.reduce((sum, a) => sum + a.total_missing, 0),
      lines: aggregates.reduce((sum, a) => sum + a.items.length, 0),
      sources: aggregates.length,
    };
  }, [data, groupBy]);

  function buildCopyText(): string {
    if (!data) return "";
    if (groupBy === "part") {
      return byPart
        .map(
          (a) =>
            `${a.part_num} ${a.color_name} ${a.part_name} — needs ${a.total_missing} (${a.contributors
              .map((c) => `${c.label} x${c.quantity}`)
              .join(", ")})`,
        )
        .join("\n");
    }
    return bySource
      .map(
        (s) =>
          `${s.label} — ${s.total_missing} missing\n` +
          s.items
            .map(
              (i) =>
                `  ${i.part_num} ${i.color_name} ${i.part_name} x${i.quantity_missing}`,
            )
            .join("\n"),
      )
      .join("\n\n");
  }

  function toggleExpanded(key: string) {
    setExpanded((current) =>
      current.includes(key)
        ? current.filter((entry) => entry !== key)
        : [...current, key],
    );
  }

  function markContributorFound(
    aggregate: PartAggregateOut,
    contributor: ContributorOut,
  ) {
    markFound.mutate({
      source: contributor,
      partNum: aggregate.part_num,
      colorId: aggregate.color_id,
      foundDelta: 1,
    });
  }

  function markItemFound(aggregate: SourceAggregateOut, item: SourceItemOut) {
    markFound.mutate({
      source: aggregate,
      partNum: item.part_num,
      colorId: item.color_id,
      foundDelta: 1,
    });
  }

  const selectedColorName =
    colorOptions.find((option) => option.colorId === colorFilter)?.colorName ??
    null;
  const isEmpty = !data || data.length === 0;
  const filteredEverythingOut =
    !isEmpty &&
    (groupBy === "part" ? byPart.length === 0 : bySource.length === 0);

  return (
    <div>
      <StatsBar
        isLoading={isLoading}
        stats={[
          { label: "pieces missing", value: totals.pieces },
          { label: "kinds of piece", value: totals.lines },
          { label: "sets affected", value: totals.sources },
        ]}
        sortControl={
          <SortSelect
            value={sort}
            onChange={setSort}
            options={MISSING_SORT_OPTIONS}
            labels={MISSING_SORT_LABELS}
          />
        }
      />

      <div className="flex flex-wrap items-center gap-2 bg-gray-50 px-4 pt-1.5 pb-2.5">
        <GroupToggle value={groupBy} onChange={setGroupBy} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter missing parts"
          aria-label="Filter missing parts by part number, name, colour or set"
          className="ui-field w-44 px-2 py-0.5 text-xs"
        />
        <ColorFilterSelect
          options={colorOptions}
          value={colorFilter}
          onChange={setColorFilter}
        />
        <details className="relative ml-auto">
          <summary className="ui-control ui-control-secondary ui-control-sm list-none text-gray-600">
            Export
          </summary>
          <div className="absolute right-0 z-20 mt-1 flex gap-2 rounded border border-gray-200 bg-white p-2 shadow-lg">
            <CopyListButton getText={buildCopyText} />
            <ExportCsvButton groupBy={groupBy} />
          </div>
        </details>
      </div>

      <div className="p-4">
        {isLoading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : isEmpty ? (
          <p className="text-sm text-gray-500">
            Nothing missing.{" "}
            {stillSorting === 0 &&
              "Every sorted set and minifigure is accounted for."}
          </p>
        ) : filteredEverythingOut ? (
          <p className="text-sm text-gray-500">
            Nothing missing matches{" "}
            {search && (
              <span className="font-semibold">&quot;{search}&quot;</span>
            )}
            {search && selectedColorName && " in "}
            {selectedColorName && (
              <span className="font-semibold">{selectedColorName}</span>
            )}
            .
          </p>
        ) : groupBy === "part" ? (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 md:grid-cols-7 lg:grid-cols-9 xl:grid-cols-10">
            {byPart.map((aggregate) => (
              <MissingPartCard
                key={`${aggregate.part_num}-${aggregate.color_id}`}
                aggregate={aggregate}
                pendingKey={pendingKey}
                onZoom={() =>
                  aggregate.image_url &&
                  setZoom({
                    src: aggregate.image_url,
                    alt: aggregate.part_name,
                  })
                }
                onMarkFound={(contributor) =>
                  markContributorFound(aggregate, contributor)
                }
              />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {bySource.map((aggregate) => {
              const key = `${aggregate.source_type}-${aggregate.source_id}`;
              return (
                <MissingSourceSection
                  key={key}
                  aggregate={aggregate}
                  pendingKey={pendingKey}
                  isOpen={expanded.includes(key)}
                  onToggle={() => toggleExpanded(key)}
                  onZoom={(item) =>
                    item.image_url &&
                    setZoom({ src: item.image_url, alt: item.part_name })
                  }
                  onZoomSource={() =>
                    aggregate.image_url &&
                    setZoom({ src: aggregate.image_url, alt: aggregate.name })
                  }
                  onMarkFound={(item) => markItemFound(aggregate, item)}
                />
              );
            })}
          </div>
        )}
      </div>

      {zoom && (
        <ImageLightbox
          src={zoom.src}
          alt={zoom.alt}
          onClose={() => setZoom(null)}
        />
      )}
    </div>
  );
}
