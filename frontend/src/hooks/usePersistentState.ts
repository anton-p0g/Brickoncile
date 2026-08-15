import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

/**
 * useState that survives leaving the page and coming back.
 *
 * Opening a set from the Sets page unmounts it, so a plain useState drops whatever
 * sort and filters were chosen — going back lands on a differently-ordered grid than the one
 * just left. Kept in sessionStorage, so it holds for the working session (and across a reload)
 * without a filter set days ago silently hiding sets on a fresh start.
 *
 * `isValid` guards against a stored value that no longer makes sense — an option that has since
 * been renamed, or storage edited by hand — which would otherwise reach the comparators.
 */
export function usePersistentState<T>(
  key: string,
  fallback: T,
  isValid?: (value: unknown) => value is T,
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = sessionStorage.getItem(key);
      if (stored === null) return fallback;
      const parsed: unknown = JSON.parse(stored);
      if (isValid && !isValid(parsed)) return fallback;
      return parsed as T;
    } catch {
      // Unreadable or unparseable storage is not worth failing a render over.
      return fallback;
    }
  });

  // Checked on every render, not only on the first: a value can also stop being valid while the
  // component is mounted, which is what a renamed option does to a page already open. Rejecting it
  // only at mount leaves that page filtering by an option that no longer exists, and showing nothing.
  const effective = isValid && !isValid(value) ? fallback : value;

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(effective));
    } catch {
      // Storage can be full or blocked; the page works fine without persistence.
    }
  }, [key, effective]);

  return [effective, setValue];
}

export function isString(value: unknown): value is string {
  return typeof value === "string";
}

export function isBoolean(value: unknown): value is boolean {
  return typeof value === "boolean";
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString);
}
