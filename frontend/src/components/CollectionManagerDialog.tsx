import { Copy, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import type { CollectionOut } from "../api/types";
import { useCollection } from "../contexts/useCollection";
import { ConfirmDialog } from "./ConfirmDialog";

type CollectionAction =
  | { type: "create" }
  | { type: "rename"; collection: CollectionOut }
  | { type: "duplicate"; collection: CollectionOut };

interface CollectionManagerDialogProps {
  initialView: "create" | "manage";
  onClose: () => void;
  onCollectionCreated: (collectionId: string) => void;
  onActiveCollectionRemoved: () => void;
}

function normaliseName(name: string): string {
  return name.trim().normalize("NFKC").toLocaleLowerCase();
}

function availableCopyName(source: CollectionOut, collections: CollectionOut[]): string {
  const existing = new Set(collections.map((collection) => normaliseName(collection.name)));
  for (let copyNumber = 1; ; copyNumber += 1) {
    const suffix = copyNumber === 1 ? " copy" : ` copy ${copyNumber}`;
    const candidate = `${source.name.slice(0, 50 - suffix.length).trimEnd()}${suffix}`;
    if (!existing.has(normaliseName(candidate))) return candidate;
  }
}

export function CollectionManagerDialog({
  initialView,
  onClose,
  onCollectionCreated,
  onActiveCollectionRemoved,
}: CollectionManagerDialogProps) {
  const {
    collections,
    activeCollection,
    addCollection,
    renameCollection,
    duplicateCollection,
    removeCollection,
  } = useCollection();
  const [action, setAction] = useState<CollectionAction | null>(
    initialView === "create" ? { type: "create" } : null,
  );
  const [name, setName] = useState("");
  const [pendingDelete, setPendingDelete] = useState<CollectionOut | null>(null);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (action) inputRef.current?.focus();
    else closeRef.current?.focus();
  }, [action, pendingDelete]);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== "Escape" || isPending) return;
      if (action && initialView === "manage") {
        setAction(null);
        setError(null);
      } else {
        onClose();
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [action, initialView, isPending, onClose]);

  function startAction(nextAction: CollectionAction) {
    setAction(nextAction);
    setError(null);
    setNotice(null);
    if (nextAction.type === "create") setName("");
    if (nextAction.type === "rename") setName(nextAction.collection.name);
    if (nextAction.type === "duplicate") {
      setName(availableCopyName(nextAction.collection, collections));
    }
  }

  async function submitName(event: FormEvent) {
    event.preventDefault();
    if (!action) return;
    setError(null);
    setNotice(null);
    setIsPending(true);
    try {
      if (action.type === "create") {
        const created = await addCollection(name);
        onCollectionCreated(created.id);
        onClose();
        return;
      }
      if (action.type === "rename") {
        const renamed = await renameCollection(action.collection.id, name);
        setNotice(`Renamed collection to “${renamed.name}”.`);
      } else {
        const duplicate = await duplicateCollection(action.collection.id, name);
        setNotice(`Created “${duplicate.name}” from “${action.collection.name}”.`);
      }
      setAction(null);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Could not update the collection");
    } finally {
      setIsPending(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const deleted = pendingDelete;
    const removedActiveCollection = deleted.id === activeCollection.id;
    setIsPending(true);
    try {
      await removeCollection(deleted.id);
      if (removedActiveCollection) onActiveCollectionRemoved();
      setPendingDelete(null);
      setNotice(`Deleted “${deleted.name}”.`);
      setError(null);
    } catch (caught: unknown) {
      setPendingDelete(null);
      setError(caught instanceof Error ? caught.message : "Could not delete the collection");
    } finally {
      setIsPending(false);
    }
  }

  if (pendingDelete) {
    return (
      <ConfirmDialog
        title={`Delete “${pendingDelete.name}”?`}
        confirmLabel="Delete collection"
        requiredConfirmationText={pendingDelete.name}
        isPending={isPending}
        onCancel={() => !isPending && setPendingDelete(null)}
        onConfirm={confirmDelete}
        body={
          <p>
            Its sets, minifigures, progress, and history will be permanently deleted. This cannot be undone.
          </p>
        }
      />
    );
  }

  const actionTitle =
    action?.type === "create"
      ? "Create collection"
      : action?.type === "rename"
        ? `Rename “${action.collection.name}”`
        : action?.type === "duplicate"
          ? `Duplicate “${action.collection.name}”`
          : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close collection manager"
        onClick={() => !isPending && onClose()}
        className="absolute inset-0 bg-gray-900/40"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="collection-manager-title"
        className="relative max-h-[calc(100vh-2rem)] w-full max-w-xl overflow-y-auto rounded border border-gray-300 bg-white p-4 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="collection-manager-title" className="text-base font-bold">
              Manage collections
            </h2>
            <p className="mt-1 text-sm text-gray-600">Keep separate inventories for different people or projects.</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Close collection manager"
            className="ui-control ui-control-secondary shrink-0 p-1.5"
          >
            <X aria-hidden="true" size={16} />
          </button>
        </div>

        {action && (
          <form onSubmit={submitName} className="mt-4 rounded border border-gray-200 bg-gray-50 p-3">
            <h3 className="text-sm font-semibold text-gray-900">{actionTitle}</h3>
            {action.type === "duplicate" && (
              <p className="mt-1 text-xs text-gray-500">Everything in the collection will be copied.</p>
            )}
            <label className="mt-3 block text-sm font-medium text-gray-700">
              Name
              <input
                ref={inputRef}
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength={50}
                disabled={isPending}
                placeholder="For example, Castle project"
                className="ui-field mt-1 w-full px-3 py-2 text-sm font-normal"
              />
            </label>
            {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  if (initialView === "create") {
                    onClose();
                    return;
                  }
                  setAction(null);
                  setError(null);
                }}
                disabled={isPending}
                className="ui-control ui-control-secondary ui-control-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isPending || !name.trim()}
                className="ui-control ui-control-primary ui-control-md font-semibold"
              >
                {isPending
                  ? "Working..."
                  : action.type === "create"
                    ? "Create"
                    : action.type === "rename"
                      ? "Save"
                      : "Duplicate"}
              </button>
            </div>
          </form>
        )}

        {!action && error && <p className="mt-4 rounded bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
        {!action && notice && <p className="mt-4 rounded bg-green-50 p-2.5 text-sm text-green-800">{notice}</p>}

        <div className="mt-4 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-gray-900">
            {collections.length} {collections.length === 1 ? "collection" : "collections"}
          </h3>
          <button
            type="button"
            onClick={() => startAction({ type: "create" })}
            disabled={isPending || action?.type === "create"}
            className="ui-control ui-control-secondary ui-control-md gap-1.5"
          >
            <Plus aria-hidden="true" size={15} />
            New collection
          </button>
        </div>

        <ul className="mt-2 divide-y divide-gray-200 rounded border border-gray-200">
          {collections.map((collection) => (
            <li key={collection.id} className="flex items-center gap-2 p-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-gray-900">{collection.name}</p>
                <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-gray-500">
                  {collection.id === activeCollection.id && (
                    <span className="rounded-full bg-gray-900 px-2 py-0.5 text-white">Current</span>
                  )}
                  {collection.is_default && (
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">Default</span>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={() => startAction({ type: "rename", collection })}
                  disabled={isPending}
                  aria-label={`Rename ${collection.name}`}
                  title="Rename"
                  className="ui-control ui-control-secondary p-2"
                >
                  <Pencil aria-hidden="true" size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => startAction({ type: "duplicate", collection })}
                  disabled={isPending}
                  aria-label={`Duplicate ${collection.name}`}
                  title="Duplicate"
                  className="ui-control ui-control-secondary p-2"
                >
                  <Copy aria-hidden="true" size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => setPendingDelete(collection)}
                  disabled={isPending || collections.length === 1}
                  aria-label={`Delete ${collection.name}`}
                  title={collections.length === 1 ? "The only collection cannot be deleted" : "Delete"}
                  className="ui-control ui-control-danger p-2 disabled:text-gray-300"
                >
                  <Trash2 aria-hidden="true" size={15} />
                </button>
              </div>
            </li>
          ))}
        </ul>
        {collections.length === 1 && (
          <p className="mt-2 text-xs text-gray-500">Create another collection before deleting this one.</p>
        )}
      </div>
    </div>
  );
}
