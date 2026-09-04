import { useMemo, useState } from "react";
import type { HistoryEntryOut, PartOut } from "../api/types";
import { formatAbsoluteTime, formatRelativeTime } from "../lib/time";

interface HistoryLogProps {
  entries: HistoryEntryOut[] | undefined;
  /** The entity's current parts, used to label each log group with a name, colour and thumbnail. */
  parts: PartOut[];
  isLoading: boolean;
  isOpen: boolean;
  onToggle: () => void;
}

interface PartGroup {
  key: string;
  partNum: string;
  colorId: number;
  part: PartOut | undefined;
  entries: HistoryEntryOut[];
  lastTimestamp: string;
}

const partKey = (partNum: string, colorId: number) => `${partNum}-${colorId}`;

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      className={`h-3 w-3 flex-shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 3l5 5-5 5" />
    </svg>
  );
}

/** Quantities are found counts, so a rise means pieces turned up. */
function actionLabel(entry: HistoryEntryOut): string {
  const delta = entry.quantity_after - entry.quantity_before;
  const magnitude = Math.abs(delta);
  const pieces = magnitude === 1 ? "piece" : "pieces";
  if (entry.action === "marked_broken") return `marked ${magnitude} ${pieces} broken`;
  if (entry.action === "unmarked_broken") return `unmarked ${magnitude} broken ${pieces}`;
  return delta > 0 ? `found ${magnitude} ${pieces}` : `unmarked ${magnitude} ${pieces}`;
}

function actionTone(entry: HistoryEntryOut): string {
  if (entry.action === "marked_broken" || entry.action === "unmarked_broken") {
    return "text-violet-700";
  }
  return entry.quantity_after > entry.quantity_before
    ? "text-green-600"
    : "text-red-600";
}

function PartGroupRow({ group }: { group: PartGroup }) {
  const [expanded, setExpanded] = useState(false);
  const { part, entries } = group;

  return (
    <li className="border-b border-gray-200 last:border-b-0">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-gray-50"
      >
        <ChevronIcon open={expanded} />
        <div className="h-7 w-7 flex-shrink-0 overflow-hidden rounded bg-gray-100">
          {part?.image_url && (
            <img src={part.image_url} alt="" loading="lazy" className="h-full w-full object-contain" />
          )}
        </div>
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-gray-700">
          {group.partNum} {part?.color_name ?? `color ${group.colorId}`}
          {part?.part_name && <span className="text-gray-400"> {part.part_name}</span>}
        </span>
        {part?.is_fully_found ? (
          <span className="flex-shrink-0 font-mono text-[11px] font-semibold text-green-600">
            all found
            {part.quantity_broken > 0 && (
              <span className="text-violet-700"> &middot; {part.quantity_broken} broken</span>
            )}
          </span>
        ) : (
          <span className="flex-shrink-0 font-mono text-[11px] font-bold text-amber-700">
            {part ? `${part.quantity_found} of ${part.quantity_required}` : "unknown part"}
            {part && part.quantity_broken > 0 && (
              <span className="text-violet-700"> &middot; {part.quantity_broken} broken</span>
            )}
          </span>
        )}
        <span className="flex-shrink-0 font-mono text-[11px] text-gray-400">
          {entries.length} change{entries.length === 1 ? "" : "s"}
        </span>
        <span
          title={formatAbsoluteTime(group.lastTimestamp)}
          className="hidden flex-shrink-0 font-mono text-[11px] text-gray-400 sm:inline"
        >
          {formatRelativeTime(group.lastTimestamp)}
        </span>
      </button>

      {expanded && (
        <ol className="border-t border-gray-100 bg-gray-50 px-3 py-1.5 pl-12">
          {entries.map((entry, index) => (
            <li
              key={`${entry.timestamp}-${index}`}
              className="flex flex-wrap items-baseline gap-x-2 py-0.5 font-mono text-[11px]"
            >
              <span className={actionTone(entry)}>
                {actionLabel(entry)}
              </span>
              <span className="text-gray-400">
                {entry.quantity_before} &rarr; {entry.quantity_after}{" "}
                {entry.action === "marked_broken" || entry.action === "unmarked_broken"
                  ? "broken"
                  : "found"}
              </span>
              <span title={formatAbsoluteTime(entry.timestamp)} className="text-gray-400">
                {formatRelativeTime(entry.timestamp)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </li>
  );
}

export function HistoryLog({ entries, parts, isLoading, isOpen, onToggle }: HistoryLogProps) {
  const partsByKey = useMemo(() => {
    const map = new Map<string, PartOut>();
    // History only ever records tracked parts, and a spare can share a build part's part/colour,
    // so spares are skipped rather than overwriting the row the log is actually about.
    for (const part of parts) {
      if (!part.is_spare) map.set(partKey(part.part_num, part.color_id), part);
    }
    return map;
  }, [parts]);

  // One expandable log entry per part, most recently touched first, each holding its own
  // transitions newest-first.
  const groups = useMemo<PartGroup[]>(() => {
    if (!entries) return [];
    const map = new Map<string, PartGroup>();
    for (const entry of entries) {
      const key = partKey(entry.part_num, entry.color_id);
      let group = map.get(key);
      if (!group) {
        group = {
          key,
          partNum: entry.part_num,
          colorId: entry.color_id,
          part: partsByKey.get(key),
          entries: [],
          lastTimestamp: entry.timestamp,
        };
        map.set(key, group);
      }
      group.entries.unshift(entry);
      if (entry.timestamp > group.lastTimestamp) group.lastTimestamp = entry.timestamp;
    }
    return Array.from(map.values()).sort((a, b) => b.lastTimestamp.localeCompare(a.lastTimestamp));
  }, [entries, partsByKey]);

  return (
    <section className="border-t border-gray-200">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-gray-600 hover:bg-gray-50"
      >
        <ChevronIcon open={isOpen} />
        <span className="font-semibold">History</span>
        {isOpen && !isLoading && (
          <span className="font-mono text-xs text-gray-400">
            {groups.length} part{groups.length === 1 ? "" : "s"} touched, {entries?.length ?? 0} change
            {(entries?.length ?? 0) === 1 ? "" : "s"}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="border-t border-gray-200 bg-white">
          {isLoading ? (
            <p className="px-4 py-3 text-sm text-gray-500">Loading history...</p>
          ) : groups.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-400">
              Nothing logged yet. Marking a piece missing, found, or broken records an entry here.
            </p>
          ) : (
            <ul>
              {groups.map((group) => (
                <PartGroupRow key={group.key} group={group} />
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
