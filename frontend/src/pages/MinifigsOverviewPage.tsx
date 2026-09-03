import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import type {
  BulkAddMinifigResultItem,
  MinifigInstanceSummary,
  SortingStatus,
} from "../api/types";
import { AddMinifigsResultDialog } from "../components/AddMinifigsResultDialog";
import { CompletionBar } from "../components/CompletionBar";
import { MinifigInstanceCard } from "../components/MinifigInstanceCard";
import { SortSelect } from "../components/SortSelect";
import { StatsBar } from "../components/StatsBar";
import { StatusFilterChips } from "../components/StatusFilterChips";
import { Toast, type ToastMessage, type ToastTone } from "../components/Toast";
import {
  useAddMinifigByReference,
  useBulkAddMinifigsByReference,
  useMinifigInstances,
} from "../hooks/useMinifigs";
import {
  isBoolean,
  isString,
  usePersistentState,
} from "../hooks/usePersistentState";
import { completionPercent } from "../lib/completion";
import {
  compareBySort,
  isSortOption,
  isStatusFilter,
  matchesStatusFilter,
  SORT_LABELS,
  SORT_OPTIONS,
  STATUS_FILTERS,
  type SortOption,
  type StatusFilter,
} from "../lib/sorting";

/** Splits a pasted block into references. Links contain neither spaces nor commas, so the same
 *  separators the bulk set add uses work here too. */
function parseReferences(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((line) => line.trim())
    .filter(Boolean);
}

/** Map key for minifigs with no source set; null cannot key a Map distinctly from the string "null".
 *  A colon keeps it clear of every real set number without putting an invisible character in the
 *  source — this was a literal NUL byte, which made git treat the whole file as binary. */
const LOOSE_GROUP_KEY = "loose:no-set";

interface SetGroup {
  /** Null for the group of loose minifigs, which has no set to link to. */
  setNum: string | null;
  setName: string | null;
  instances: MinifigInstanceSummary[];
  quantity_required_total: number;
  quantity_found_total: number;
  quantity_missing_total: number;
  added_at: string;
  status: SortingStatus;
}

/** A group is as far along as its least-progressed member: one unstarted minifig means work left. */
function groupStatus(instances: MinifigInstanceSummary[]): SortingStatus {
  if (instances.some((i) => i.status === "not_started")) return "not_started";
  if (instances.some((i) => i.status === "sorting")) return "sorting";
  if (instances.some((i) => i.status === "sorted")) return "sorted";
  return "complete";
}

/**
 * Minifigs are always grouped by the set that introduced them: a flat roster of every physical
 * instance is unreadable once the collection grows, and the source set is how they are stored.
 * Loose ones have no such set, so they collect into a group of their own.
 */
function groupBySourceSet(instances: MinifigInstanceSummary[]): SetGroup[] {
  const groups = new Map<string, SetGroup>();

  for (const instance of instances) {
    const key = instance.source_set_num ?? LOOSE_GROUP_KEY;
    let group = groups.get(key);
    if (!group) {
      group = {
        setNum: instance.source_set_num,
        setName: instance.source_set_name,
        instances: [],
        quantity_required_total: 0,
        quantity_found_total: 0,
        quantity_missing_total: 0,
        added_at: instance.added_at,
        status: instance.status,
      };
      groups.set(key, group);
    }
    group.instances.push(instance);
    group.quantity_required_total += instance.quantity_required_total;
    group.quantity_found_total += instance.quantity_found_total;
    group.quantity_missing_total += instance.quantity_missing_total;
    // The group is as old as the earliest minifig the set contributed.
    if (instance.added_at < group.added_at) group.added_at = instance.added_at;
  }

  for (const group of groups.values())
    group.status = groupStatus(group.instances);
  return Array.from(groups.values());
}

export function MinifigsOverviewPage() {
  const { data: allInstances = [], isLoading } = useMinifigInstances();
  const [searchParams, setSearchParams] = useSearchParams();
  // Kept across navigation for the same reason as the Sets page's: opening a minifig and coming
  // back should land on the list you left, not a re-sorted one.
  const [search, setSearch] = usePersistentState(
    "minifigs.search",
    "",
    isString,
  );
  const [statusFilter, setStatusFilter] = usePersistentState<StatusFilter>(
    "minifigs.statusFilter",
    "all",
    isStatusFilter,
  );
  const [sort, setSort] = usePersistentState<SortOption>(
    "minifigs.sort",
    "least-complete",
    isSortOption,
  );
  const [looseOnly, setLooseOnly] = usePersistentState(
    "minifigs.looseOnly",
    false,
    isBoolean,
  );
  const [referenceInput, setReferenceInput] = useState("");
  const [bulkInput, setBulkInput] = useState("");
  const [showBulk, setShowBulk] = useState(false);
  const [bulkResults, setBulkResults] = useState<
    BulkAddMinifigResultItem[] | null
  >(null);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const addMinifig = useAddMinifigByReference();
  const bulkAddMinifigs = useBulkAddMinifigsByReference();

  // A new id per toast so the same message twice in a row still restarts the auto-dismiss timer.
  const showToast = useCallback((tone: ToastTone, text: string) => {
    setToast({ tone, text, id: Date.now() });
  }, []);

  // "?set=" is how a set's own page links here. It narrows the whole view — stats and status
  // counts included — so everything on screen describes that one set rather than the collection.
  const sourceSetFilter = searchParams.get("set");
  // The two scopes are opposites — one set's minifigs against the ones no set accounts for — so a
  // set link wins outright rather than intersecting to nothing.
  const showLooseOnly = looseOnly && !sourceSetFilter;
  const instances = useMemo(() => {
    if (sourceSetFilter)
      return allInstances.filter((i) => i.source_set_num === sourceSetFilter);
    return showLooseOnly
      ? allInstances.filter((i) => i.source_set_num === null)
      : allInstances;
  }, [allInstances, sourceSetFilter, showLooseOnly]);
  const filteredSetName = instances[0]?.source_set_name ?? null;

  // A set's page says how many minifigs it has and links here to show them, so that link has to
  // land on all of them — a status filter left over from earlier browsing would otherwise answer
  // "no minifigs match" to a claim of four. Only when the set changes: choosing a filter while
  // already looking at a set is a deliberate narrowing and stays.
  useEffect(() => {
    if (sourceSetFilter) setStatusFilter("all");
  }, [sourceSetFilter, setStatusFilter]);
  const looseCount = useMemo(
    () => allInstances.filter((i) => i.source_set_num === null).length,
    [allInstances],
  );

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    const typed = referenceInput.trim();
    if (!typed) return;
    try {
      const { instance, already_owned_count } =
        await addMinifig.mutateAsync(typed);
      setReferenceInput("");
      // One figure is small enough to report in a toast; the dialog is reserved for bulk runs.
      showToast(
        already_owned_count > 0 ? "warning" : "success",
        already_owned_count > 0
          ? `Added ${instance.fig_name} (${instance.fig_num}) — you now own ${already_owned_count + 1}.`
          : `Added ${instance.fig_name} (${instance.fig_num}).`,
      );
    } catch (err) {
      // The message says which part could not be read, so the typed text stays put to be corrected.
      showToast(
        "error",
        err instanceof Error ? err.message : "Could not add that minifigure.",
      );
    }
  }

  async function handleBulkAdd() {
    const references = parseReferences(bulkInput);
    if (references.length === 0) {
      showToast("error", "Paste at least one link or fig ID first.");
      return;
    }
    setBulkResults(null);
    try {
      const response = await bulkAddMinifigs.mutateAsync(references);
      setBulkResults(response.results);
      // Only clear on a clean run; anything that failed stays in the box to be corrected and retried.
      const failed = response.results.filter((r) => r.status === "error");
      if (failed.length === 0) {
        setBulkInput("");
        setShowBulk(false);
      } else {
        setBulkInput(failed.map((r) => r.input_reference).join("\n"));
      }
    } catch (err) {
      // The request itself failed, so there is no per-line report to show.
      showToast(
        "error",
        `Bulk add failed: ${err instanceof Error ? err.message : "unknown error"}`,
      );
    }
  }

  const statusCounts = useMemo(
    () =>
      Object.fromEntries(
        STATUS_FILTERS.map((filter) => [
          filter,
          instances.filter((i) => matchesStatusFilter(i.status, filter)).length,
        ]),
      ) as Record<StatusFilter, number>,
    [instances],
  );

  const groups = useMemo(() => {
    const matching = instances.filter((i) => {
      if (!matchesStatusFilter(i.status, statusFilter)) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          i.fig_name.toLowerCase().includes(q) ||
          i.fig_num.toLowerCase().includes(q) ||
          (i.source_set_num?.toLowerCase().includes(q) ?? false) ||
          (i.source_set_name?.toLowerCase().includes(q) ?? false) ||
          // "loose" is what the heading calls them, so it should find them too.
          (i.source_set_num === null && "loose".includes(q))
        );
      }
      return true;
    });

    // The same ordering applies to the groups and to the cards inside each one.
    const compareInstances = compareBySort<MinifigInstanceSummary>(
      sort,
      (i) => i.fig_name,
    );
    const compareGroups = compareBySort<SetGroup>(
      sort,
      (g) => g.setName ?? g.setNum ?? "loose minifigures",
    );

    const grouped = groupBySourceSet(matching);
    for (const group of grouped) group.instances.sort(compareInstances);
    return grouped.sort(compareGroups);
  }, [instances, statusFilter, search, sort]);

  const notStartedCount = instances.filter(
    (i) => i.status === "not_started",
  ).length;
  const totals = {
    quantity_required_total: instances.reduce(
      (sum, i) => sum + i.quantity_required_total,
      0,
    ),
    quantity_found_total: instances.reduce(
      (sum, i) => sum + i.quantity_found_total,
      0,
    ),
  };

  return (
    <div>
      <StatsBar
        isLoading={isLoading}
        stats={[
          { label: "minifigs owned", value: instances.length },
          { label: "not started", value: notStartedCount },
          { label: "found overall", value: `${completionPercent(totals)}%` },
        ]}
        sortControl={
          <SortSelect
            value={sort}
            onChange={setSort}
            options={SORT_OPTIONS}
            labels={SORT_LABELS}
          />
        }
      />
      <div className="flex flex-wrap items-center gap-2 bg-gray-50 px-4 pt-1.5 pb-2.5">
        <StatusFilterChips
          value={statusFilter}
          onChange={setStatusFilter}
          counts={statusCounts}
        />
        {/* Hidden while a set is being shown: that view is by definition minifigs a set accounts
            for, so narrowing it to the ones no set accounts for could only empty it. */}
        {!sourceSetFilter && (
          <button
            type="button"
            aria-pressed={showLooseOnly}
            onClick={() => setLooseOnly((v) => !v)}
            title="Show only minifigures no owned set accounts for"
            className={`ui-control ui-control-sm ${
              showLooseOnly
                ? "border-gray-900 bg-gray-900 text-white hover:border-gray-700 hover:bg-gray-700"
                : "ui-control-secondary"
            }`}
          >
            Loose only
            <span
              className={
                showLooseOnly ? "ml-1 text-gray-300" : "ml-1 text-gray-400"
              }
            >
              {looseCount}
            </span>
          </button>
        )}
        {/* Filters what is already here. Distinct from the box below, which adds new minifigures. */}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter your minifigures"
          aria-label="Filter your minifigures by name, fig ID or set"
          className="ui-field ml-auto w-44 px-2 py-0.5 text-xs"
        />
      </div>
      {sourceSetFilter && (
        <div className="mx-4 mt-2 flex flex-wrap items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm ring-1 ring-amber-100">
          <span>
            Showing minifigures from set{" "}
            <span className="font-mono font-semibold">{sourceSetFilter}</span>
            {filteredSetName ? ` — ${filteredSetName}` : ""}
          </span>
          <button
            type="button"
            onClick={() => setSearchParams({})}
            className="ui-control ui-control-secondary ui-control-sm"
          >
            Show all minifigures
          </button>
        </div>
      )}
      <div className="p-4">
        {/* Adds to the collection. Distinct from the filter box in the row above. */}
        <form onSubmit={handleAdd} className="flex flex-wrap gap-2">
          <input
            value={referenceInput}
            onChange={(e) => setReferenceInput(e.target.value)}
            placeholder="Paste a Rebrickable link or fig ID..."
            aria-label="Rebrickable minifigure link or fig ID to add"
            className="ui-field min-w-48 flex-1 px-3 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={addMinifig.isPending}
            className="ui-control ui-control-primary ui-control-md"
          >
            {addMinifig.isPending ? "Adding..." : "+ Add Minifigure"}
          </button>
          <button
            type="button"
            onClick={() => setShowBulk((v) => !v)}
            className="ui-control ui-control-secondary ui-control-md"
          >
            + Bulk Add
          </button>
        </form>

        {showBulk && (
          <div className="mt-2 flex flex-col gap-2">
            <textarea
              value={bulkInput}
              onChange={(e) => setBulkInput(e.target.value)}
              placeholder="Paste Rebrickable links or fig IDs, one per line"
              className="ui-field h-24 p-2 text-sm"
            />
            <button
              type="button"
              onClick={handleBulkAdd}
              disabled={bulkAddMinifigs.isPending}
              className="ui-control ui-control-primary ui-control-md w-fit"
            >
              {bulkAddMinifigs.isPending ? "Adding..." : "Add all"}
            </button>
          </div>
        )}
      </div>

      {isLoading ? (
        <p className="px-4 text-sm text-gray-500">Loading...</p>
      ) : instances.length === 0 ? (
        <p className="px-4 text-sm text-gray-500">
          {sourceSetFilter
            ? `No minifigures are tracked for set ${sourceSetFilter}. If it should have some, resync the set.`
            : showLooseOnly
              ? "No loose minifigures — every one you own came from a set. Identify one from a photo to add it."
              : "No minifigs yet — add a set that includes some."}
        </p>
      ) : groups.length === 0 ? (
        <p className="px-4 text-sm text-gray-500">
          No minifigs match the current filters.
        </p>
      ) : (
        <div className="flex flex-col gap-5 px-4 pb-4">
          {groups.map((group) => (
            <section key={group.setNum ?? LOOSE_GROUP_KEY}>
              <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 px-0.5">
                {group.setNum === null ? (
                  <span className="font-mono text-sm font-bold text-gray-700">
                    loose minifigures — no set
                  </span>
                ) : (
                  <Link
                    to={`/sets/${encodeURIComponent(group.setNum)}`}
                    className="font-mono text-sm font-bold text-gray-700 hover:text-gray-900 hover:underline"
                  >
                    set {group.setNum}
                    {group.setName ? ` — ${group.setName}` : ""}
                  </Link>
                )}
                <span className="font-mono text-xs text-gray-400">
                  {group.instances.length} minifig
                  {group.instances.length === 1 ? "" : "s"}
                </span>
                <span className="font-mono text-xs text-gray-500">
                  {completionPercent(group)}% found
                </span>
                {group.quantity_missing_total > 0 && (
                  <span className="rounded bg-red-600 px-1.5 py-0.5 font-mono text-[11px] font-bold text-white">
                    {group.quantity_missing_total} missing
                  </span>
                )}
                <CompletionBar
                  entity={group}
                  status={group.status}
                  className="w-full max-w-[14rem]"
                />
              </div>
              <div className="flex flex-wrap gap-3">
                {group.instances.map((instance) => (
                  <MinifigInstanceCard
                    key={instance.instance_id}
                    instance={instance}
                    onError={(message) => showToast("error", message)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {bulkResults && (
        <AddMinifigsResultDialog
          results={bulkResults}
          onClose={() => setBulkResults(null)}
        />
      )}
      {toast && <Toast toast={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
