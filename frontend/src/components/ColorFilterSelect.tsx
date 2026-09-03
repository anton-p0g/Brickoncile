import { useEffect, useRef, useState } from "react";
import { ColorSwatch } from "./ColorSwatch";

export interface ColorOption {
  colorId: number;
  colorName: string;
  /** Part lines in this colour, so an option says how much it would leave on screen. */
  count: number;
}

interface ColorFilterSelectProps {
  options: ColorOption[];
  /** Null for no colour filter. */
  value: number | null;
  onChange: (value: number | null) => void;
}

/**
 * Colour filter with its own search box.
 *
 * A native `<select>` cannot show a swatch, and the names alone are the problem being solved —
 * nobody recalls whether a piece is Orange, Bright Light Orange, Medium Orange or Earth Orange.
 * Typing "orange" narrows to every variant at once and the swatches settle which one it is.
 */
export function ColorFilterSelect({ options, value, onChange }: ColorFilterSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const container = useRef<HTMLDivElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);

  const selected = options.find((option) => option.colorId === value) ?? null;
  const query = search.trim().toLowerCase();
  const matching = query
    ? options.filter((option) => option.colorName.toLowerCase().includes(query))
    : options;

  useEffect(() => {
    if (open) searchInput.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function choose(colorId: number | null) {
    onChange(colorId);
    setOpen(false);
    setSearch("");
  }

  return (
    <div ref={container} className="relative">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        title="Filter by colour"
        className={`ui-control ui-control-sm gap-1.5 ${
          selected
            ? "border-gray-900 bg-white font-semibold hover:bg-gray-50"
            : "ui-control-secondary text-gray-600"
        }`}
      >
        {selected && <ColorSwatch colorId={selected.colorId} colorName={selected.colorName} />}
        <span className="max-w-40 truncate">{selected ? selected.colorName : "All colours"}</span>
        <span aria-hidden="true" className="text-gray-400">
          &#9662;
        </span>
      </button>

      {open && (
        <div className="absolute left-0 z-30 mt-1 w-60 rounded border border-gray-300 bg-white shadow-lg">
          <div className="border-b border-gray-200 p-1.5">
            <input
              ref={searchInput}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              // Typing a colour and pressing Enter should not need a second aim with the mouse.
              onKeyDown={(e) => {
                if (e.key === "Enter" && matching.length > 0) choose(matching[0].colorId);
              }}
              placeholder="Search colours, e.g. orange"
              aria-label="Search colours"
              className="ui-field w-full px-2 py-1 text-xs"
            />
          </div>

          <ul className="max-h-64 overflow-y-auto py-1">
            <li>
              <button
                type="button"
                onClick={() => choose(null)}
                className={`flex w-full items-center gap-2 px-2 py-1 text-left text-xs hover:bg-gray-100 ${
                  value === null ? "font-semibold" : ""
                }`}
              >
                <span className="flex-1">All colours</span>
                <span className="font-mono text-[10px] text-gray-400">
                  {options.reduce((sum, option) => sum + option.count, 0)}
                </span>
              </button>
            </li>
            {matching.map((option) => (
              <li key={option.colorId}>
                <button
                  type="button"
                  onClick={() => choose(option.colorId)}
                  className={`flex w-full items-center gap-2 px-2 py-1 text-left text-xs hover:bg-gray-100 ${
                    option.colorId === value ? "font-semibold" : ""
                  }`}
                >
                  <ColorSwatch colorId={option.colorId} colorName={option.colorName} />
                  <span className="min-w-0 flex-1 truncate">{option.colorName}</span>
                  <span className="font-mono text-[10px] text-gray-400">{option.count}</span>
                </button>
              </li>
            ))}
            {matching.length === 0 && (
              <li className="px-2 py-1.5 text-xs text-gray-500">No colour matches &quot;{search}&quot;.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
