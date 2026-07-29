interface SortSelectProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: readonly T[];
  labels: Record<T, string>;
}

/**
 * The sort control every grid screen uses, so they stay one control rather than three that drifted.
 *
 * Generic over the option set: the dashboard and the minifig roster sort by completion, while the
 * missing parts grid sorts by what is missing, and those lists have nothing in common but the look.
 */
export function SortSelect<T extends string>({ value, onChange, options, labels }: SortSelectProps<T>) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      aria-label="Sort by"
      className="rounded border border-gray-300 bg-white px-2 py-1 text-sm"
    >
      {options.map((option) => (
        <option key={option} value={option}>
          {labels[option]}
        </option>
      ))}
    </select>
  );
}
