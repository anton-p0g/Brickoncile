import type { SortingStatus, StatusCount } from "../../api/types";
import { STATUS_HEX, STATUS_LABELS } from "../../lib/completion";
import { ChartEmpty } from "./ChartCard";

interface StatusFunnelProps {
  breakdown: StatusCount[];
  /** Which side of the collection to count — the two move through the same workflow. */
  of: "sets" | "minifig_instances";
  unit: string;
}

/**
 * Where the collection sits in the sorting workflow, as one bar split by stage.
 *
 * A stacked bar rather than four separate bars: the question is what share of the collection is at
 * each stage, and shares are read from one length divided up, not from lengths compared across a
 * gap. Segments are directly labelled, so the colours reinforce rather than carry the meaning.
 */
export function StatusFunnel({ breakdown, of, unit }: StatusFunnelProps) {
  const counts = breakdown.map((entry) => ({ status: entry.status, count: entry[of] }));
  const total = counts.reduce((sum, entry) => sum + entry.count, 0);

  if (total === 0) return <ChartEmpty>No {unit} yet.</ChartEmpty>;

  const present = counts.filter((entry) => entry.count > 0);

  return (
    <div>
      <div className="flex h-7 w-full gap-0.5 overflow-hidden rounded" role="img" aria-label={describe(counts, unit)}>
        {present.map((entry) => (
          <div
            key={entry.status}
            className="flex items-center justify-center"
            style={{ width: `${(entry.count / total) * 100}%`, backgroundColor: STATUS_HEX[entry.status] }}
            title={`${entry.count} ${unit} ${STATUS_LABELS[entry.status]}`}
          >
            {/* Only wide enough segments get an inline number; the legend carries the rest. */}
            {entry.count / total > 0.08 && (
              <span className={`font-mono text-xs font-bold ${inkFor(entry.status)}`}>{entry.count}</span>
            )}
          </div>
        ))}
      </div>

      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {counts.map((entry) => (
          <li key={entry.status} className="flex items-center gap-1.5 text-xs text-gray-600">
            <span
              aria-hidden
              className="inline-block size-2.5 rounded-[2px]"
              style={{ backgroundColor: STATUS_HEX[entry.status] }}
            />
            {STATUS_LABELS[entry.status]}
            <span className="font-mono text-gray-900">{entry.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** not_started is a pale gray that white text disappears into. */
function inkFor(status: SortingStatus): string {
  return status === "not_started" ? "text-gray-700" : "text-white";
}

function describe(counts: { status: SortingStatus; count: number }[], unit: string): string {
  return counts.map((entry) => `${entry.count} ${unit} ${STATUS_LABELS[entry.status]}`).join(", ");
}
