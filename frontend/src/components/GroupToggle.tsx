import type { GroupBy } from "../api/types";

interface GroupToggleProps {
  value: GroupBy;
  onChange: (value: GroupBy) => void;
}

const LABELS: Record<GroupBy, string> = {
  part: "By part",
  set: "By set",
};

const OPTIONS = Object.keys(LABELS) as GroupBy[];

/**
 * Styled as the status chips are, since it sits in the same filter row and does the same job.
 * The group's own label carries the "group by" part, so the buttons do not each repeat it.
 */
export function GroupToggle({ value, onChange }: GroupToggleProps) {
  return (
    <span className="flex flex-wrap items-center gap-1" role="group" aria-label="Group by">
      {OPTIONS.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={value === option}
          onClick={() => onChange(option)}
          className={`ui-control ui-control-sm ${
            value === option
              ? "border-gray-900 bg-gray-900 text-white hover:border-gray-700 hover:bg-gray-700"
              : "ui-control-secondary"
          }`}
        >
          {LABELS[option]}
        </button>
      ))}
    </span>
  );
}
