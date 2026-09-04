import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useCollection } from "../contexts/useCollection";
import { CollectionManagerDialog } from "./CollectionManagerDialog";

const CREATE_VALUE = "__create_collection__";
const MANAGE_VALUE = "__manage_collections__";

export function CollectionSelector() {
  const { collections, activeCollection, selectCollection } = useCollection();
  const [dialogView, setDialogView] = useState<"create" | "manage" | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  function leaveCollectionDetail() {
    if (location.pathname.startsWith("/sets/")) navigate("/sets");
    if (location.pathname.startsWith("/minifigs/")) navigate("/minifigs");
  }

  function switchCollection(collectionId: string) {
    leaveCollectionDetail();
    selectCollection(collectionId);
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
              setDialogView("create");
            } else if (event.target.value === MANAGE_VALUE) {
              setDialogView("manage");
            } else {
              switchCollection(event.target.value);
            }
          }}
          className="ui-field max-w-44 px-2 py-1 text-sm font-medium"
        >
          {collections.map((collection) => (
            <option key={collection.id} value={collection.id}>
              {collection.name}
            </option>
          ))}
          <option disabled>──────────</option>
          <option value={CREATE_VALUE}>Create new collection...</option>
          <option value={MANAGE_VALUE}>Manage collections...</option>
        </select>
      </label>

      {dialogView && (
        <CollectionManagerDialog
          initialView={dialogView}
          onClose={() => setDialogView(null)}
          onCollectionCreated={switchCollection}
          onActiveCollectionRemoved={leaveCollectionDetail}
        />
      )}
    </>
  );
}
