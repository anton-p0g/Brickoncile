import type { ReactNode } from "react";

interface StatsBarProps {
  stats: { label: string; value: string | number }[];
  sortControl?: ReactNode;
  isLoading?: boolean;
}

export function StatsBar({ stats, sortControl, isLoading = false }: StatsBarProps) {
  return (
    <div
      aria-busy={isLoading}
      className="flex flex-wrap items-center gap-x-6 gap-y-1 bg-gray-50 px-4 pt-2.5 pb-1.5 font-mono text-sm text-gray-700"
    >
      {stats.map((s) => (
        <span key={s.label}>
          {isLoading ? "—" : s.value} {s.label}
        </span>
      ))}
      {sortControl && <span className="ml-auto">{sortControl}</span>}
    </div>
  );
}
