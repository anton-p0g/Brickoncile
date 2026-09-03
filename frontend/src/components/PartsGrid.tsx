import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { EyeOff } from "lucide-react";
import type { PartFoundTarget, PartOut, SortingStatus } from "../api/types";
import { colorHex, needsSwatchOutline } from "../lib/colors";
import {
  clampFound,
  currentFoundTargets,
  partKey,
  pendingConfirmTargets,
} from "../lib/parts";
import { ConfirmDialog } from "./ConfirmDialog";
import { PartCard, type GridMode } from "./PartCard";
import { PartQuantityStepper } from "./PartQuantityStepper";
import { UndoToast } from "./UndoToast";

const UNDO_TIMEOUT_MS = 5000;
const BULK_UNDO_TIMEOUT_MS = 15000;
const NO_COLOR_ID = 9999;

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

/** A finished inventory exposes missing-count corrections; active sorting confirms found pieces. */
function modeFor(status: SortingStatus): GridMode {
  return status === "sorted" ? "missing" : "find";
}

/** A whisper of the real LEGO colour: enough to connect label and pile without turning the
 *  toolbar into a rainbow at rest. Pale colours mix toward gray so White still has a hover. */
function colorFilterStyle(colorId: number): CSSProperties {
  const hex = colorHex(colorId);
  if (!hex) return {};
  const paleBase = needsSwatchOutline(hex) ? "#e5e7eb" : "#ffffff";
  return {
    "--part-color-hover": `color-mix(in srgb, ${hex} 14%, ${paleBase})`,
    "--part-color-hover-border": `color-mix(in srgb, ${hex} 36%, #9ca3af)`,
  } as CSSProperties;
}

export function PartsGrid({
  parts,
  status,
  onMark,
  onSetPartsFound,
  isBulkPending,
}: PartsGridProps) {
  const [search, setSearch] = useState("");
  const [activeColors, setActiveColors] = useState<Set<number>>(new Set());
  const [hideFound, setHideFound] = useState(false);
  const [stepperKey, setStepperKey] = useState<string | null>(null);
  const [lastChange, setLastChange] = useState<LastChange | null>(null);
  const [confirmingAll, setConfirmingAll] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const mode = modeFor(status);

  const colors = useMemo(() => {
    const namesById = new Map<number, string>();
    for (const part of parts) namesById.set(part.color_id, part.color_name);
    return Array.from(namesById, ([id, name]) => ({ id, name })).sort(
      (a, b) => Number(a.id === NO_COLOR_ID) - Number(b.id === NO_COLOR_ID) || a.name.localeCompare(b.name),
    );
  }, [parts]);
  const stepperPart = parts.find((p) => partKey(p) === stepperKey) ?? null;

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      )
        return;
      const key = e.key.toLowerCase();
      if (e.key === "/") {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (key === "h") {
        setHideFound((v) => !v);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Auto-dismiss the undo offer, keyed on the change so each new one gets a fresh window.
  useEffect(() => {
    if (!lastChange) return;
    const timer = window.setTimeout(
      () => setLastChange(null),
      lastChange.timeoutMs,
    );
    return () => window.clearTimeout(timer);
  }, [lastChange]);

  function toggleColor(colorId: number) {
    setActiveColors((prev) => {
      const next = new Set(prev);
      if (next.has(colorId)) next.delete(colorId);
      else next.add(colorId);
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
    if (activeColors.size > 0 && !activeColors.has(p.color_id)) return false;
    if (search) {
      const q = search.toLowerCase();
      if (
        !p.part_num.toLowerCase().includes(q) &&
        !p.part_name.toLowerCase().includes(q)
      )
        return false;
    }
    return true;
  });

  const confirmTargets = pendingConfirmTargets(filtered);
  const piecesToConfirm = filtered.reduce(
    (sum, part) =>
      part.is_spare || part.is_fully_found
        ? sum
        : sum + part.quantity_unaccounted,
    0,
  );
  const canConfirmAll =
    onSetPartsFound !== undefined && confirmTargets.length > 0;

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

  return (
    <div>
      <div className="sticky top-2 z-30 mx-2 mt-2 flex flex-wrap items-center gap-2 rounded-lg bg-white/95 p-2 shadow-sm ring-1 ring-black/5 backdrop-blur">
        <input
          ref={searchRef}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search part # or name"
          className="ui-field h-7 w-48 flex-none px-3 text-xs"
        />
        <button
          type="button"
          aria-pressed={hideFound}
          onClick={() => setHideFound((v) => !v)}
          title="Hide part lines whose required pieces are all confirmed present"
          className={`ui-control mr-1 h-7 gap-1.5 px-3 text-xs font-semibold ${
            hideFound
              ? "border-blue-700 bg-blue-700 text-white hover:border-blue-800 hover:bg-blue-800"
              : "border-blue-300 bg-blue-50 text-blue-800 hover:border-blue-500 hover:bg-blue-100"
          }`}
        >
          <EyeOff aria-hidden="true" className="h-3.5 w-3.5" strokeWidth={1.8} />
          Hide found
        </button>
        {colors.map((color) => (
          <button
            key={color.id}
            type="button"
            aria-pressed={activeColors.has(color.id)}
            onClick={() => toggleColor(color.id)}
            style={colorFilterStyle(color.id)}
            className={`part-color-filter ui-control h-7 px-3 text-xs ${
              activeColors.has(color.id)
                ? "border-gray-900 bg-gray-900 text-white hover:border-gray-700 hover:bg-gray-700"
                : "ui-control-secondary"
            }`}
          >
            {color.name}
          </button>
        ))}
        {canConfirmAll && (
          <button
            type="button"
            onClick={() => setConfirmingAll(true)}
            disabled={isBulkPending}
            className="ui-control ui-control-success h-7 px-3 text-xs"
          >
            {isBulkPending
              ? "Confirming..."
              : `Confirm all shown (${confirmTargets.length})`}
          </button>
        )}
        <span className="ml-auto hidden text-xs text-gray-400 sm:inline">
          <kbd className="rounded bg-gray-900 px-1 py-0.5 text-white">/</kbd>{" "}
          search{" "}
          <kbd className="rounded bg-gray-900 px-1 py-0.5 text-white">H</kbd>{" "}
          hide found
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
          <p className="col-span-full py-6 text-center text-sm text-gray-400">
            No parts match the current filters.
          </p>
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
                <span className="font-mono font-semibold">
                  {confirmTargets.length}
                </span>{" "}
                part {confirmTargets.length === 1 ? "line" : "lines"} still
                showing in the grid (
                <span className="font-mono font-semibold">
                  {piecesToConfirm}
                </span>{" "}
                pieces) will be marked fully present.
              </p>
              <p className="mt-1.5">
                Only what the current filters show is affected. Every change is
                logged, and you can undo this from the toast afterwards.
              </p>
            </>
          }
        />
      )}

      {lastChange && (
        <UndoToast
          message={lastChange.message}
          onUndo={undoLastChange}
          onDismiss={() => setLastChange(null)}
        />
      )}
    </div>
  );
}
