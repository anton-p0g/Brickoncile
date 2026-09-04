import { createContext, useContext } from "react";
import type { CollectionOut } from "../api/types";

export interface CollectionContextValue {
  collections: CollectionOut[];
  activeCollection: CollectionOut;
  selectCollection: (collectionId: string) => void;
  addCollection: (name: string) => Promise<CollectionOut>;
  renameCollection: (collectionId: string, name: string) => Promise<CollectionOut>;
  duplicateCollection: (collectionId: string, name: string) => Promise<CollectionOut>;
  removeCollection: (collectionId: string) => Promise<void>;
}

export const CollectionContext = createContext<CollectionContextValue | null>(null);

export function useCollection(): CollectionContextValue {
  const value = useContext(CollectionContext);
  if (!value) throw new Error("useCollection must be used inside CollectionProvider");
  return value;
}
