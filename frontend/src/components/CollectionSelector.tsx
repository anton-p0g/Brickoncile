import { useEffect, useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useCollection } from "../contexts/useCollection";

const CREATE_VALUE = "__create_collection__";

export function CollectionSelector() {
  const { collections, activeCollection, selectCollection, addCollection } = useCollection();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (showCreate) inputRef.current?.focus();
  }, [showCreate]);

  useEffect(() => {
    if (!showCreate) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isCreating) setShowCreate(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [showCreate, isCreating]);

  function switchCollection(collectionId: string) {
    if (location.pathname.startsWith("/sets/")) navigate("/sets");
    if (location.pathname.startsWith("/minifigs/")) navigate("/minifigs");
    selectCollection(collectionId);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsCreating(true);
    try {
      const created = await addCollection(name);
      setName("");
      setShowCreate(false);
      setIsCreating(false);
      switchCollection(created.id);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Could not create the collection");
      setIsCreating(false);
    }
  }

  return (
    <>
      <label className="ml-auto flex items-center gap-1.5 py-1 pl-3 text-xs text-gray-500">
        <span className="hidden sm:inline">Collection</span>
        <select
          aria-label="Current collection"
          value={activeCollection.id}
          onChange={(event) => {
            if (event.target.value === CREATE_VALUE) {
              setError(null);
              setShowCreate(true);
            } else {
              switchCollection(event.target.value);
            }
          }}
          className="max-w-44 rounded border border-gray-300 bg-white px-2 py-1 text-sm font-normal text-gray-500"
        >
          {collections.map((collection) => (
            <option key={collection.id} value={collection.id}>
              {collection.name}
            </option>
          ))}
          <option disabled>──────────</option>
          <option value={CREATE_VALUE}>Create new collection...</option>
        </select>
      </label>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            aria-label="Cancel creating collection"
            onClick={() => !isCreating && setShowCreate(false)}
            className="absolute inset-0 bg-gray-900/40"
          />
          <form
            onSubmit={submit}
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-collection-title"
            className="relative w-full max-w-sm rounded border border-gray-300 bg-white p-4 shadow-xl"
          >
            <h2 id="create-collection-title" className="text-base font-bold">
              Create collection
            </h2>
            <label className="mt-3 block text-sm font-medium text-gray-700">
              Name
              <input
                ref={inputRef}
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength={50}
                disabled={isCreating}
                placeholder="For example, Test Collection"
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm font-normal disabled:bg-gray-100"
              />
            </label>
            {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                disabled={isCreating}
                className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm hover:border-gray-500 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isCreating || !name.trim()}
                className="rounded border border-gray-900 bg-gray-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-gray-700 disabled:opacity-50"
              >
                {isCreating ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
