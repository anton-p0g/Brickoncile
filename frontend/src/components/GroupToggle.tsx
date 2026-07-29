import type { GroupBy } from "../api/types";

interface GroupToggleProps {
  value: GroupBy;
  onChange: (value: GroupBy) => void;
}

export function GroupToggle({ value, onChange }: GroupToggleProps) {
  return (
    <div className="flex gap-1">
      <button
        type="button"
        onClick={() => onChange("part")}
        className={`rounded-full border px-3 py-1 text-xs ${value === "part" ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 bg-white"}`}
      >
        Group: by part
      </button>
      <button
        type="button"
        onClick={() => onChange("set")}
        className={`rounded-full border px-3 py-1 text-xs ${value === "set" ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 bg-white"}`}
      >
        Group: by set
      </button>
    </div>
  );
}
