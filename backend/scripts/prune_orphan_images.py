"""Delete cached images that no registered collection references any more.

Set deletion now cleans up its own images, so this is only needed for images stranded by
deletions made before that existed, or by a manual edit of the database.

Run from the backend directory (as a module, so `app` resolves):

    uv run python -m scripts.prune_orphan_images            # report only, changes nothing
    uv run python -m scripts.prune_orphan_images --delete   # actually remove them
"""

import argparse

from sqlmodel import Session

from app.infrastructure.db.collection_manager import CollectionManager
from app.infrastructure.db.sqlite_minifig_instance_repository import (
    SqliteMinifigInstanceRepository,
)
from app.infrastructure.db.sqlite_minifig_repository import SqliteMinifigRepository
from app.infrastructure.db.sqlite_set_repository import SqliteSetRepository
from app.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true", help="remove the files instead of only listing them")
    args = parser.parse_args()

    settings = get_settings()
    images_root = settings.images_dir
    if not images_root.is_dir():
        print(f"No images directory at {images_root}")
        return 0

    collection_manager = CollectionManager(settings.database_path)
    collection_manager.initialize()
    referenced: set[str] = set()
    try:
        for collection in collection_manager.list_collections():
            with Session(collection_manager.get_engine(collection.id)) as session:
                referenced |= (
                    SqliteSetRepository(session).list_referenced_image_paths()
                    | SqliteMinifigInstanceRepository(session).list_referenced_image_paths()
                    | SqliteMinifigRepository(session).list_referenced_image_paths()
                )
    finally:
        collection_manager.close()

    on_disk = {str(path.relative_to(images_root)) for path in images_root.rglob("*") if path.is_file()}
    orphans = sorted(on_disk - referenced)

    if not orphans:
        print(f"Nothing to prune: all {len(on_disk)} cached images are still referenced.")
        return 0

    freed_bytes = sum((images_root / path).stat().st_size for path in orphans)
    for path in orphans:
        print(f"  {'deleting' if args.delete else 'orphan'}  {path}")
        if args.delete:
            (images_root / path).unlink(missing_ok=True)

    verb = "Deleted" if args.delete else "Would delete"
    print(f"\n{verb} {len(orphans)} of {len(on_disk)} cached images ({freed_bytes / 1024:.0f} KB).")
    if not args.delete:
        print("Re-run with --delete to remove them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
