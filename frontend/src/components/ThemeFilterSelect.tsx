import type { ThemeFilter, ThemeOption } from "../lib/themes";

interface ThemeFilterSelectProps {
  value: ThemeFilter;
  onChange: (value: ThemeFilter) => void;
  options: ThemeOption[];
}

export function ThemeFilterSelect({ value, onChange, options }: ThemeFilterSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Filter by theme"
      className="rounded border border-gray-300 bg-white px-2 py-0.5 text-xs"
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label} ({option.count})
        </option>
      ))}
    </select>
  );
}
