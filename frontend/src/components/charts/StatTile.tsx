import type { ReactNode } from "react";

interface StatTileProps {
  label: string;
  value: string | number;
  /** Smaller line under the value, for the denominator or a rate. */
  detail?: ReactNode;
}

/**
 * A single number, given room to be read. Used where there is one figure to report and a chart
 * would be an axis and a gridline wrapped around a value the eye takes in immediately.
 */
export function StatTile({ label, value, detail }: StatTileProps) {
  return (
    <div className="ui-hover-surface rounded-lg border border-gray-200 bg-white px-3 py-2">
      <div className="text-xl leading-tight font-semibold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
      {detail && <div className="mt-0.5 text-[11px] text-gray-400">{detail}</div>}
    </div>
  );
}
