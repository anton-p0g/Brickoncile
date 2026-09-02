import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { createCollection, listCollections, setApiCollectionId } from "../api/client";
import type { CollectionOut } from "../api/types";
import { CollectionContext } from "./useCollection";

const STORAGE_KEY = "brickoncile.activeCollectionId";

export function CollectionProvider({ children }: { children: ReactNode }) {
  const [collections, setCollections] = useState<CollectionOut[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [queryClient, setQueryClient] = useState(() => new QueryClient());

  const activate = useCallback((collectionId: string) => {
    // Update the request client before React mounts queries for the newly selected collection.
    setApiCollectionId(collectionId);
    sessionStorage.setItem(STORAGE_KEY, collectionId);
    // A fresh cache guarantees that returning to a collection reflects changes made elsewhere and
    // that no in-flight result from the previous collection can appear under shared query keys.
    setQueryClient(new QueryClient());
    setActiveId(collectionId);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    listCollections()
      .then((loaded) => {
        if (cancelled) return;
        const savedId = sessionStorage.getItem(STORAGE_KEY);
        const selected =
          loaded.find((collection) => collection.id === savedId) ??
          loaded.find((collection) => collection.is_default) ??
          loaded[0];
        if (!selected) throw new Error("No collection is available");
        setCollections(loaded);
        activate(selected.id);
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : "Could not load collections");
      });
    return () => {
      cancelled = true;
    };
  }, [activate, loadAttempt]);

  const addCollection = useCallback(
    async (name: string) => {
      const created = await createCollection(name);
      setCollections((current) => [...current, created]);
      return created;
    },
    [],
  );

  const activeCollection = collections.find((collection) => collection.id === activeId);
  if (loadError) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50 p-4 text-gray-900">
        <div className="max-w-sm rounded border border-red-200 bg-white p-4 text-center shadow-sm">
          <p className="text-sm text-red-700">{loadError}</p>
          <button
            type="button"
            onClick={() => setLoadAttempt((attempt) => attempt + 1)}
            className="mt-3 rounded border border-gray-300 px-3 py-1.5 text-sm hover:border-gray-500"
          >
            Try again
          </button>
        </div>
      </main>
    );
  }
  if (!activeCollection) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50 text-sm text-gray-500">
        Loading collection...
      </main>
    );
  }

  const value = { collections, activeCollection, selectCollection: activate, addCollection };

  return (
    <CollectionContext.Provider value={value}>
      <QueryClientProvider key={activeCollection.id} client={queryClient}>
        {children}
      </QueryClientProvider>
    </CollectionContext.Provider>
  );
}
