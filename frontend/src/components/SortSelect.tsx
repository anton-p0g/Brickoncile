import { SORT_LABELS, SORT_OPTIONS, type SortOption } from "../lib/sorting";

interface SortSelectProps {
  value: SortOption;
  onChange: (value: SortOption) => void;
}

export function SortSelect({ value, onChange }: SortSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as SortOption)}
      aria-label="Sort by"
      className="rounded border border-gray-300 bg-white px-2 py-1 text-sm"
    >
      {SORT_OPTIONS.map((option) => (
        <option key={option} value={option}>
          {SORT_LABELS[option]}
        </option>
      ))}
    </select>
  );
}
