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
          className={`ui-control ui-control-sm ${
            value === filter
              ? "border-gray-900 bg-gray-900 text-white hover:border-gray-700 hover:bg-gray-700"
              : "ui-control-secondary"
          }`}
        >
          {STATUS_FILTER_LABELS[filter]}
          <span className={value === filter ? "ml-1 text-gray-300" : "ml-1 text-gray-400"}>{counts[filter]}</span>
        </button>
      ))}
    </span>
  );
}
