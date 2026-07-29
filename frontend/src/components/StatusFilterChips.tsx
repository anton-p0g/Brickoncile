import { STATUS_FILTERS, STATUS_FILTER_LABELS, type StatusFilter } from "../lib/sorting";

interface StatusFilterChipsProps {
  value: StatusFilter;
  onChange: (value: StatusFilter) => void;
  counts: Record<StatusFilter, number>;
}

export function StatusFilterChips({ value, onChange, counts }: StatusFilterChipsProps) {
  return (
    <span className="flex flex-wrap items-center gap-1" role="group" aria-label="Filter by status">
      {STATUS_FILTERS.map((filter) => (
        <button
          key={filter}
          type="button"
          aria-pressed={value === filter}
          onClick={() => onChange(filter)}
          className={`rounded-full border px-2 py-0.5 text-xs ${
            value === filter ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 bg-white"
          }`}
        >
          {STATUS_FILTER_LABELS[filter]}
          <span className={value === filter ? "ml-1 text-gray-300" : "ml-1 text-gray-400"}>{counts[filter]}</span>
        </button>
      ))}
    </span>
  );
}
