import type { SetSummary } from "../api/types";

/**
 * Sets are grouped by their *root* theme, not their own `theme_id`. Rebrickable files a set under
 * the narrowest theme it fits ("Constraction", "Episode I"), while a shelf is organised by the line
 * it belongs to ("Legends of Chima", "Star Wars"), which is that theme's root.
 */
export const ALL_THEMES = "all";

/** Bucket for sets with no theme upstream, or whose theme is not in the cached tree yet. */
export const NO_THEME = "none";

export type ThemeFilter = typeof ALL_THEMES | typeof NO_THEME | string;

export const NO_THEME_LABEL = "No theme";

/** Any theme name is a valid filter, so this only rules out a stored value of the wrong shape.
 *  A theme that is no longer owned simply matches nothing, which the empty state already covers. */
export function isThemeFilter(value: unknown): value is ThemeFilter {
  return typeof value === "string";
}

export function themeOf(set: SetSummary): string {
  return set.root_theme_name ?? NO_THEME;
}

export function themeLabel(theme: string): string {
  return theme === NO_THEME ? NO_THEME_LABEL : theme;
}

export interface ThemeOption {
  value: ThemeFilter;
  label: string;
  count: number;
}

/**
 * The themes actually present in the collection, most-owned first so the big lines sit at the top
 * of the dropdown, with "No theme" pinned last since it is a fallback rather than a real line.
 */
export function themeOptions(sets: SetSummary[]): ThemeOption[] {
  const counts = new Map<string, number>();
  for (const set of sets) {
    const theme = themeOf(set);
    counts.set(theme, (counts.get(theme) ?? 0) + 1);
  }

  const options: ThemeOption[] = Array.from(counts, ([value, count]) => ({
    value,
    label: themeLabel(value),
    count,
  }));
  options.sort((a, b) => {
    if (a.value === NO_THEME) return 1;
    if (b.value === NO_THEME) return -1;
    return b.count - a.count || a.label.localeCompare(b.label);
  });

  return [{ value: ALL_THEMES, label: "All themes", count: sets.length }, ...options];
}

export function matchesThemeFilter(set: SetSummary, filter: ThemeFilter): boolean {
  return filter === ALL_THEMES || themeOf(set) === filter;
}

export interface ThemeGroup {
  theme: string;
  label: string;
  sets: SetSummary[];
}

/**
 * Split an already-filtered, already-sorted list into theme sections, biggest first. Each section
 * keeps the incoming order, so the active sort still applies inside a theme.
 */
export function groupByTheme(sets: SetSummary[]): ThemeGroup[] {
  const groups = new Map<string, SetSummary[]>();
  for (const set of sets) {
    const theme = themeOf(set);
    const existing = groups.get(theme);
    if (existing) existing.push(set);
    else groups.set(theme, [set]);
  }

  return Array.from(groups, ([theme, themeSets]) => ({
    theme,
    label: themeLabel(theme),
    sets: themeSets,
  })).sort((a, b) => {
    if (a.theme === NO_THEME) return 1;
    if (b.theme === NO_THEME) return -1;
    return b.sets.length - a.sets.length || a.label.localeCompare(b.label);
  });
}
