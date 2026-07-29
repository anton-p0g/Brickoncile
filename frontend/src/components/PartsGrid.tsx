import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PartFoundTarget, PartOut, SortingStatus } from "../api/types";
import { clampFound, currentFoundTargets, partKey, pendingConfirmTargets } from "../lib/parts";
import { ConfirmDialog } from "./ConfirmDialog";
import { PartCard, type GridMode } from "./PartCard";
import { PartQuantityStepper } from "./PartQuantityStepper";
import { UndoToast } from "./UndoToast";

const UNDO_TIMEOUT_MS = 5000;
/** A bulk confirm rewrites a lot at once, so its undo offer stays up longer than a single tap's. */
const BULK_UNDO_TIMEOUT_MS = 15000;

interface PartsGridProps {
  parts: PartOut[];
  status: SortingStatus;
  onMark: (partNum: string, colorId: number, foundDelta: number) => void;
  /** Writes many parts' found counts in one request. Absent on read-only usages. */
  onSetPartsFound?: (targets: PartFoundTarget[]) => Promise<unknown>;
  isBulkPending?: boolean;
}

interface LastChange {
  /** Restores the exact previous state, whether that was one tap or a whole bulk confirm. */
  undo: () => void;
  message: string;
  timeoutMs: number;
}

/**
 * A set already declared sorted opens in missing mode, since the work there is correcting counts
 * rather than working through a pile. Anything unfinished opens in find mode.
 */
function defaultModeFor(status: SortingStatus): GridMode {
  return status === "sorted" ? "missing" : "find";
}

export function PartsGrid({ parts, status, onMark, onSetPartsFound, isBulkPending }: PartsGridProps) {
  const [search, setSearch] = useState("");
  const [activeColors, setActiveColors] = useState<Set<string>>(new Set());
  const [hideFound, setHideFound] = useState(false);
  const [mode, setMode] = useState<GridMode>(() => defaultModeFor(status));
  const [stepperKey, setStepperKey] = useState<string | null>(null);
  const [lastChange, setLastChange] = useState<LastChange | null>(null);
  const [confirmingAll, setConfirmingAll] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const colors = useMemo(() => Array.from(new Set(parts.map((p) => p.color_name))).sort(), [parts]);
  const stepperPart = parts.find((p) => partKey(p) === stepperKey) ?? null;

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const key = e.key.toLowerCase();
      if (e.key === "/") {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (key === "h") {
        setHideFound((v) => !v);
      } else if (key === "f") {
        setMode((m) => (m === "find" ? "missing" : "find"));
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Auto-dismiss the undo offer, keyed on the change so each new one gets a fresh window.
  useEffect(() => {
    if (!lastChange) return;
    const timer = window.setTimeout(() => setLastChange(null), lastChange.timeoutMs);
    return () => window.clearTimeout(timer);
  }, [lastChange]);

  function toggleColor(color: string) {
    setActiveColors((prev) => {
      const next = new Set(prev);
      if (next.has(color)) next.delete(color);
      else next.add(color);
      return next;
    });
  }

  const handleMark = useCallback(
    (part: PartOut, requestedDelta: number) => {
      // Clamp the same way the server does, so a no-op tap costs no request and an undo of a
      // clamped change restores the right count.
      const foundDelta = clampFound(part, requestedDelta) - part.quantity_found;
      if (foundDelta === 0) return;

      onMark(part.part_num, part.color_id, foundDelta);

      const magnitude = Math.abs(foundDelta);
      const pieces = magnitude === 1 ? "piece" : "pieces";
      const label = `${part.part_num} ${part.color_name}`;
      setLastChange({
        undo: () => onMark(part.part_num, part.color_id, -foundDelta),
        timeoutMs: UNDO_TIMEOUT_MS,
        message:
          foundDelta > 0
            ? `${label}: ${magnitude} ${pieces} confirmed present`
            : `${label}: ${magnitude} ${pieces} no longer accounted for`,
      });
    },
    [onMark],
  );

  function undoLastChange() {
    if (!lastChange) return;
    lastChange.undo();
    setLastChange(null);
  }

  const filtered = parts.filter((p) => {
    if (p.is_spare) return false;
    if (hideFound && p.is_fully_found) return false;
    if (activeColors.size > 0 && !activeColors.has(p.color_name)) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!p.part_num.toLowerCase().includes(q) && !p.part_name.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  // Scoped to what is on screen, not to the whole set: the filters above are the selection, so
  // nothing hidden behind a search or colour chip gets confirmed by surprise.
  const confirmTargets = pendingConfirmTargets(filtered);
  const piecesToConfirm = filtered.reduce(
    (sum, part) => (part.is_spare || part.is_fully_found ? sum : sum + part.quantity_unaccounted),
    0,
  );
  const canConfirmAll = onSetPartsFound !== undefined && confirmTargets.length > 0;

  async function confirmAllShown() {
    if (!onSetPartsFound) return;
    const restore = currentFoundTargets(filtered);
    const lineCount = confirmTargets.length;
    setConfirmingAll(false);
    await onSetPartsFound(confirmTargets);
    setLastChange({
      undo: () => void onSetPartsFound(restore),
      timeoutMs: BULK_UNDO_TIMEOUT_MS,
      message: `${lineCount} part ${lineCount === 1 ? "line" : "lines"} confirmed present (${piecesToConfirm} pieces)`,
    });
  }

  const modeButtonClass = (active: boolean) =>
    `px-2 py-1 text-xs font-semibold transition ${
      active ? "bg-gray-900 text-white" : "bg-white text-gray-600 hover:text-gray-900"
    }`;

  return (
    <div>
      <div className="sticky top-0 z-30 flex flex-wrap items-center gap-2 border-b border-gray-200 bg-gray-50 p-2">
        <span className="flex overflow-hidden rounded border border-gray-300" role="group" aria-label="Tap mode">
          <button type="button" onClick={() => setMode("find")} className={modeButtonClass(mode === "find")}>
            Find pieces
          </button>
          <button
            type="button"
            onClick={() => setMode("missing")}
            className={`border-l border-gray-300 ${modeButtonClass(mode === "missing")}`}
          >
            Mark missing
          </button>
        </span>

        <input
          ref={searchRef}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search part # or name"
          className="w-40 rounded border border-gray-300 px-2 py-1 text-sm"
        />
        {colors.map((color) => (
          <button
            key={color}
            type="button"
            onClick={() => toggleColor(color)}
            className={`rounded-full border px-2 py-0.5 text-xs ${
              activeColors.has(color) ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 bg-white"
            }`}
          >
            {color}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setHideFound((v) => !v)}
          className={`rounded-full border px-2 py-0.5 text-xs ${
            hideFound ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 bg-white"
          }`}
        >
          Hide found
        </button>
        {canConfirmAll && (
          <button
            type="button"
            onClick={() => setConfirmingAll(true)}
            disabled={isBulkPending}
            className="rounded border border-green-600 bg-white px-2 py-0.5 text-xs font-semibold text-green-700 hover:bg-green-50 disabled:opacity-50"
          >
            {isBulkPending ? "Confirming..." : `Confirm all shown (${confirmTargets.length})`}
          </button>
        )}
        <span className="ml-auto hidden text-xs text-gray-400 sm:inline">
          <kbd className="rounded bg-gray-900 px-1 py-0.5 text-white">/</kbd> search{" "}
          <kbd className="rounded bg-gray-900 px-1 py-0.5 text-white">F</kbd> mode{" "}
          <kbd className="rounded bg-gray-900 px-1 py-0.5 text-white">H</kbd> hide found
        </span>
      </div>

      <p className="px-2 pt-2 text-xs text-gray-400">
        {mode === "find"
          ? "Tap a card to confirm every copy of that piece is present, long-press for a partial count"
          : "Tap a card to mark one more piece missing, tap the red count to give one back"}
      </p>

      <div className="grid grid-cols-3 gap-2 p-2 sm:grid-cols-5 md:grid-cols-7 lg:grid-cols-9">
        {filtered.map((part) => (
          <PartCard
            key={partKey(part)}
            part={part}
            mode={mode}
            onMark={(foundDelta) => handleMark(part, foundDelta)}
            onRequestStepper={() => setStepperKey(partKey(part))}
          />
        ))}
        {filtered.length === 0 && (
          <p className="col-span-full py-6 text-center text-sm text-gray-400">No parts match the current filters.</p>
        )}
      </div>

      {stepperPart && (
        <PartQuantityStepper
          part={stepperPart}
          onMark={(foundDelta) => handleMark(stepperPart, foundDelta)}
          onClose={() => setStepperKey(null)}
        />
      )}

      {confirmingAll && (
        <ConfirmDialog
          title="Confirm every part still showing?"
          confirmLabel={`Confirm ${confirmTargets.length} part ${confirmTargets.length === 1 ? "line" : "lines"}`}
          isPending={isBulkPending}
          onCancel={() => setConfirmingAll(false)}
          onConfirm={confirmAllShown}
          body={
            <>
              <p>
                <span className="font-mono font-semibold">{confirmTargets.length}</span> part{" "}
                {confirmTargets.length === 1 ? "line" : "lines"} still showing in the grid (
                <span className="font-mono font-semibold">{piecesToConfirm}</span> pieces) will be marked
                fully present.
              </p>
              <p className="mt-1.5">
                Only what the current filters show is affected. Every change is logged, and you can undo
                this from the toast afterwards.
              </p>
            </>
          }
        />
      )}

      {lastChange && (
        <UndoToast message={lastChange.message} onUndo={undoLastChange} onDismiss={() => setLastChange(null)} />
      )}
    </div>
  );
}
