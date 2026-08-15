/**
 * Drawing primitives shared by the dashboard charts.
 *
 * The charts are hand-drawn SVG rather than a charting library: the app carries no plotting
 * dependency, and every figure here is a bar, a line or a rectangle over a few dozen points.
 */

/** Chart chrome, kept recessive so the marks carry the eye. Tailwind's grays, as everywhere else. */
export const INK = {
  grid: "#e5e7eb", // gray-200
  axis: "#d1d5db", // gray-300
  label: "#9ca3af", // gray-400
  text: "#4b5563", // gray-600
} as const;

/**
 * Single-hue blue for one-series charts. Sequential magnitude uses the ramp below, which is the
 * same hue stepped light to dark, so the whole dashboard reads as one family.
 */
export const SERIES_BLUE = "#2a78d6";

/**
 * Sequential ramp for completion, light (nothing found) to dark (complete). One hue only — a
 * rainbow would imply categories where there is a single continuous magnitude.
 */
const COMPLETION_RAMP = [
  "#e8f1fd",
  "#cde2fb",
  "#9ec5f4",
  "#6da7ec",
  "#3987e5",
  "#256abf",
  "#184f95",
  "#0d366b",
] as const;

/** Ramp step for a ratio in [0, 1]. Exact zero keeps the lightest step, so "untouched" reads as empty. */
export function completionFill(ratio: number): string {
  const clamped = Math.min(1, Math.max(0, ratio));
  if (clamped === 0) return COMPLETION_RAMP[0];
  const index = Math.ceil(clamped * (COMPLETION_RAMP.length - 1));
  return COMPLETION_RAMP[index];
}

/** Ink that stays legible on top of `completionFill`, which darkens as completion rises. */
export function completionInk(ratio: number): string {
  return ratio > 0.45 ? "#ffffff" : "#1f2937";
}

/** The ramp's steps, for the legend that explains what the shading means. */
export const COMPLETION_STEPS: readonly string[] = COMPLETION_RAMP;

function niceStep(rough: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const normalized = rough / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

/**
 * A rounded axis maximum and its tick values, so gridlines land on numbers worth reading rather
 * than on whatever the data happened to peak at.
 */
export function axisScale(max: number, tickCount = 4): { max: number; ticks: number[] } {
  if (!Number.isFinite(max) || max <= 0) return { max: 1, ticks: [0, 1] };
  const step = niceStep(max / tickCount);
  const niceMax = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let value = 0; value <= niceMax + step / 1000; value += step) {
    ticks.push(Math.round(value * 1000) / 1000);
  }
  return { max: niceMax, ticks };
}

export function formatCount(value: number): string {
  return value.toLocaleString();
}

/**
 * Compact form for axis ticks and tight labels, where the exact digits are not the point. Whole
 * thousands drop the decimal, so a run of ticks reads 5k, 10k, 15k rather than 5.0k beside 10k.
 */
export function formatCompact(value: number): string {
  if (Math.abs(value) < 1_000) return String(Math.round(value));
  const thousands = value / 1000;
  const rounded = Math.abs(thousands) >= 10 ? Math.round(thousands) : Math.round(thousands * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)}k`;
}

/** Minutes as a reading duration: "45m", "3h 15m". */
export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const hours = Math.floor(minutes / 60);
  const rest = Math.round(minutes % 60);
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}

export interface Point {
  x: number;
  y: number;
}

export function linePath(points: Point[]): string {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" ");
}

/** The line closed down to a baseline, for the wash under a burn-up curve. */
export function areaPath(points: Point[], baselineY: number): string {
  if (points.length === 0) return "";
  const first = points[0];
  const last = points[points.length - 1];
  return `${linePath(points)} L${last.x.toFixed(2)} ${baselineY.toFixed(2)} L${first.x.toFixed(2)} ${baselineY.toFixed(2)} Z`;
}

export interface TreemapTile<T> {
  item: T;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface Weighted<T> {
  item: T;
  area: number;
}

/** Aspect ratio of the worst tile a row would produce — the quantity squarify minimises. */
function worstRatio<T>(row: Weighted<T>[], side: number): number {
  const sum = row.reduce((total, r) => total + r.area, 0);
  if (sum <= 0) return Infinity;
  const max = Math.max(...row.map((r) => r.area));
  const min = Math.min(...row.map((r) => r.area));
  const sumSquared = sum * sum;
  const sideSquared = side * side;
  return Math.max((sideSquared * max) / sumSquared, sumSquared / (sideSquared * min));
}

function placeRow<T>(row: Weighted<T>[], rect: Rect, tiles: TreemapTile<T>[]): Rect {
  const sum = row.reduce((total, r) => total + r.area, 0);
  if (sum <= 0) return rect;

  // The row runs along the rectangle's shorter side, which is what keeps tiles near-square.
  const alongHeight = rect.height <= rect.width;
  const side = alongHeight ? rect.height : rect.width;
  const thickness = sum / side;

  let offset = 0;
  for (const entry of row) {
    const length = entry.area / thickness;
    tiles.push({
      item: entry.item,
      x: alongHeight ? rect.x : rect.x + offset,
      y: alongHeight ? rect.y + offset : rect.y,
      width: alongHeight ? thickness : length,
      height: alongHeight ? length : thickness,
    });
    offset += length;
  }

  return alongHeight
    ? { x: rect.x + thickness, y: rect.y, width: rect.width - thickness, height: rect.height }
    : { x: rect.x, y: rect.y + thickness, width: rect.width, height: rect.height - thickness };
}

/**
 * Squarified treemap: areas proportional to `valueOf`, tiles kept as close to square as the data
 * allows so that a big value and a small one stay comparable by eye.
 *
 * Chosen over a bar chart because collection sizes span three orders of magnitude — a theme with
 * 3,200 pieces beside one with 10 leaves the small bars invisible, while a treemap still gives
 * every theme a tile you can point at.
 */
export function treemap<T>(
  items: T[],
  valueOf: (item: T) => number,
  width: number,
  height: number,
): TreemapTile<T>[] {
  if (width <= 0 || height <= 0) return [];

  const weighted = items.filter((item) => valueOf(item) > 0);
  const total = weighted.reduce((sum, item) => sum + valueOf(item), 0);
  if (total <= 0) return [];

  const scale = (width * height) / total;
  const queue: Weighted<T>[] = weighted
    .map((item) => ({ item, area: valueOf(item) * scale }))
    .sort((a, b) => b.area - a.area);

  const tiles: TreemapTile<T>[] = [];
  let rect: Rect = { x: 0, y: 0, width, height };
  let row: Weighted<T>[] = [];
  let index = 0;

  while (index < queue.length) {
    const side = Math.min(rect.width, rect.height);
    if (side <= 0) break;

    const candidate = [...row, queue[index]];
    // Adding this tile made the row worse, so close the row and re-test against the new rectangle.
    if (row.length > 0 && worstRatio(candidate, side) > worstRatio(row, side)) {
      rect = placeRow(row, rect, tiles);
      row = [];
      continue;
    }
    row = candidate;
    index += 1;
  }
  if (row.length > 0) placeRow(row, rect, tiles);

  return tiles;
}
