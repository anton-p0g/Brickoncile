import { useCallback, useMemo, useState, type FormEvent } from "react";
import type { BulkAddResultItem, SetSummary } from "../api/types";
import { AddSetsResultDialog } from "../components/AddSetsResultDialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { SetCard } from "../components/SetCard";
import { Toast, type ToastMessage, type ToastTone } from "../components/Toast";
import { SortSelect } from "../components/SortSelect";
import { StatsBar } from "../components/StatsBar";
import { StatusFilterChips } from "../components/StatusFilterChips";
import { ThemeFilterSelect } from "../components/ThemeFilterSelect";
import { isBoolean, isString, usePersistentState } from "../hooks/usePersistentState";
import { useAddSet, useBulkAddSets, useDeleteSet, useSets } from "../hooks/useSets";
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
import {
  ALL_THEMES,
  groupByTheme,
  isThemeFilter,
  matchesThemeFilter,
  themeOptions,
  type ThemeFilter,
} from "../lib/themes";

function parseSetNums(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function SetsPage() {
  const { data: sets = [], isLoading } = useSets();
  const addSet = useAddSet();
  const bulkAddSets = useBulkAddSets();
  const deleteSet = useDeleteSet();
  const [setNumInput, setSetNumInput] = useState("");
  const [bulkInput, setBulkInput] = useState("");
  const [showBulk, setShowBulk] = useState(false);
  const [bulkResults, setBulkResults] = useState<BulkAddResultItem[] | null>(null);
  // Sort and filters persist: opening a set unmounts this page, and coming back to a re-sorted
  // grid loses your place in a collection you are working through one set at a time.
  const [sort, setSort] = usePersistentState<SortOption>("sets.sort", "most-complete", isSortOption);
  const [statusFilter, setStatusFilter] = usePersistentState<StatusFilter>(
    "sets.statusFilter",
    "all",
    isStatusFilter,
  );
  const [themeFilter, setThemeFilter] = usePersistentState<ThemeFilter>(
    "sets.themeFilter",
    ALL_THEMES,
    isThemeFilter,
  );
  const [ownedSearch, setOwnedSearch] = usePersistentState("sets.search", "", isString);
  const [groupByThemeEnabled, setGroupByThemeEnabled] = usePersistentState(
    "sets.groupByTheme",
    false,
    isBoolean,
  );
  const [pendingDelete, setPendingDelete] = useState<SetSummary | null>(null);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // A new id per toast so the same message twice in a row still restarts the auto-dismiss timer.
  const showToast = useCallback((tone: ToastTone, text: string) => {
    setToast({ tone, text, id: Date.now() });
  }, []);
  const dismissToast = useCallback(() => setToast(null), []);

  const totalMissing = sets.reduce((sum, s) => sum + s.quantity_missing_total, 0);
  const notStartedCount = sets.filter((s) => s.status === "not_started").length;
  const overallPercent = completionPercent({
    quantity_required_total: sets.reduce((sum, s) => sum + s.quantity_required_total, 0),
    quantity_found_total: sets.reduce((sum, s) => sum + s.quantity_found_total, 0),
  });

  // Status counts narrow to the chosen theme, so they describe what a chip would actually show.
  // The theme dropdown stays a count of the whole collection: it answers "how many Ninjago sets do
  // I own", and keeping it independent means the chosen theme never vanishes from its own list.
  const statusCounts = useMemo(() => {
    const inTheme = sets.filter((s) => matchesThemeFilter(s, themeFilter));
    return Object.fromEntries(
      STATUS_FILTERS.map((filter) => [filter, inTheme.filter((s) => matchesStatusFilter(s.status, filter)).length]),
    ) as Record<StatusFilter, number>;
  }, [sets, themeFilter]);

  const themeChoices = useMemo(() => themeOptions(sets), [sets]);

  const visibleSets = useMemo(() => {
    const needle = ownedSearch.trim().toLowerCase();
    return sets
      .filter(
        (s) =>
          matchesStatusFilter(s.status, statusFilter) &&
          matchesThemeFilter(s, themeFilter) &&
          (!needle ||
            s.set_num.toLowerCase().includes(needle) ||
            s.name.toLowerCase().includes(needle) ||
            (s.root_theme_name ?? "").toLowerCase().includes(needle)),
      )
      .sort(compareBySort<SetSummary>(sort, (s) => s.name));
  }, [sets, sort, statusFilter, themeFilter, ownedSearch]);

  const themeGroups = useMemo(() => groupByTheme(visibleSets), [visibleSets]);

  async function handleAddSet(e: FormEvent) {
    e.preventDefault();
    const typed = setNumInput.trim();
    if (!typed) return;
    try {
      const { status, set, warning } = await addSet.mutateAsync(typed);
      setSetNumInput("");
      // One set is small enough to report in a toast; the dialog is reserved for bulk runs.
      if (status === "exists") {
        showToast("info", `${set.set_num} ${set.name} is already in your collection.`);
      } else if (warning) {
        // The set did land — the warning says what is incomplete about it, not that it failed.
        showToast("warning", `Added ${set.set_num} ${set.name}, but ${warning}.`);
      } else {
        showToast("success", `Added ${set.set_num} ${set.name}.`);
      }
    } catch (err) {
      showToast("error", `Could not add "${typed}": ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  async function handleBulkAdd() {
    const setNums = parseSetNums(bulkInput);
    if (setNums.length === 0) {
      showToast("error", "Paste at least one set number first.");
      return;
    }
    setBulkResults(null);
    try {
      const response = await bulkAddSets.mutateAsync(setNums);
      setBulkResults(response.results);
      // Only clear on a clean run; anything that failed stays in the box to be corrected and retried.
      const failed = response.results.filter((r) => r.status === "error");
      if (failed.length === 0) {
        setBulkInput("");
        setShowBulk(false);
      } else {
        setBulkInput(failed.map((r) => r.input_set_num).join("\n"));
      }
    } catch (err) {
      // The request itself failed, so there is no per-set report to show.
      showToast("error", `Bulk add failed: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  async function handleConfirmDelete() {
    if (!pendingDelete) return;
    const deleted = pendingDelete;
    setPendingDelete(null);
    try {
      await deleteSet.mutateAsync(deleted.set_num);
      showToast("success", `Deleted ${deleted.set_num} ${deleted.name}.`);
    } catch (err) {
      showToast("error", `Could not delete ${deleted.set_num}: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  return (
    <div>
      <StatsBar
        isLoading={isLoading}
        stats={[
          { label: "sets", value: sets.length },
          { label: "not started", value: notStartedCount },
          { label: "pieces missing", value: totalMissing },
          { label: "found overall", value: `${overallPercent}%` },
        ]}
        sortControl={
          <SortSelect value={sort} onChange={setSort} options={SORT_OPTIONS} labels={SORT_LABELS} />
        }
      />
      <div className="flex flex-wrap items-center gap-2 border-b border-gray-200 bg-gray-50 px-4 py-1.5">
        <StatusFilterChips value={statusFilter} onChange={setStatusFilter} counts={statusCounts} />
        <span className="ml-auto flex flex-wrap items-center gap-2">
          {/* Filters the collection. Distinct from the box below, which adds new sets. */}
          <input
            value={ownedSearch}
            onChange={(e) => setOwnedSearch(e.target.value)}
            placeholder="Filter your sets"
            aria-label="Filter your sets by number, name or theme"
            className="w-44 rounded border border-gray-300 px-2 py-0.5 text-xs"
          />
          <ThemeFilterSelect value={themeFilter} onChange={setThemeFilter} options={themeChoices} />
          <button
            type="button"
            aria-pressed={groupByThemeEnabled}
            onClick={() => setGroupByThemeEnabled((v) => !v)}
            className={`rounded-full border px-2 py-0.5 text-xs ${
              groupByThemeEnabled ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 bg-white"
            }`}
          >
            Group by theme
          </button>
        </span>
      </div>
      <div className="p-4">
        <form onSubmit={handleAddSet} className="flex flex-wrap gap-2">
          <input
            value={setNumInput}
            onChange={(e) => setSetNumInput(e.target.value)}
            placeholder="Set # or name..."
            className="min-w-48 flex-1 rounded border border-gray-300 px-3 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={addSet.isPending}
            className="rounded border border-gray-900 bg-gray-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {addSet.isPending ? "Adding..." : "+ Add Set"}
          </button>
          <button
            type="button"
            onClick={() => setShowBulk((v) => !v)}
            className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm"
          >
            + Bulk Add
          </button>
        </form>

        {showBulk && (
          <div className="mt-2 flex flex-col gap-2">
            <textarea
              value={bulkInput}
              onChange={(e) => setBulkInput(e.target.value)}
              placeholder="Paste set numbers, one per line or comma-separated"
              className="h-24 rounded border border-gray-300 p-2 text-sm"
            />
            <p className="text-xs text-gray-400">
              A bare number gets the <span className="font-mono">-1</span> variant suffix added
              automatically, so <span className="font-mono">70202</span> resolves to{" "}
              <span className="font-mono">70202-1</span>. Sets you already own are skipped.
            </p>
            <button
              type="button"
              onClick={handleBulkAdd}
              disabled={bulkAddSets.isPending}
              className="w-fit rounded border border-gray-900 bg-gray-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {bulkAddSets.isPending ? "Adding..." : "Add all"}
            </button>
          </div>
        )}

        {isLoading ? (
          <p className="mt-4 text-sm text-gray-500">Loading...</p>
        ) : sets.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">No sets yet. Add one above to get started.</p>
        ) : visibleSets.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">No sets match these filters.</p>
        ) : groupByThemeEnabled ? (
          <div className="mt-4 flex flex-col gap-4">
            {themeGroups.map((group) => (
              <section key={group.theme}>
                <h2 className="mb-1.5 flex items-baseline gap-2 border-b border-gray-200 pb-1 text-sm font-semibold">
                  {group.label}
                  <span className="font-mono text-xs font-normal text-gray-400">
                    {group.sets.length} set{group.sets.length === 1 ? "" : "s"}
                  </span>
                </h2>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
                  {group.sets.map((set) => (
                    <SetCard key={set.set_num} set={set} onRequestDelete={() => setPendingDelete(set)} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
            {visibleSets.map((set) => (
              <SetCard key={set.set_num} set={set} onRequestDelete={() => setPendingDelete(set)} />
            ))}
          </div>
        )}
      </div>

      {bulkResults && <AddSetsResultDialog results={bulkResults} onClose={() => setBulkResults(null)} />}

      {toast && <Toast toast={toast} onDismiss={dismissToast} />}

      {pendingDelete && (
        <ConfirmDialog
          title="Delete this set?"
          confirmLabel="Delete set"
          isPending={deleteSet.isPending}
          onCancel={() => setPendingDelete(null)}
          onConfirm={handleConfirmDelete}
          body={
            <>
              <p>
                <span className="font-mono font-semibold">{pendingDelete.set_num}</span> {pendingDelete.name} will be
                removed from your collection, along with its parts list, its minifigures, the history of pieces you
                checked off, and every cached image only this set used.
              </p>
              <p className="mt-1.5">
                Re-adding it later will refetch from Rebrickable. Your progress cannot be recovered.
              </p>
            </>
          }
        />
      )}
    </div>
  );
}
