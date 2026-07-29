from datetime import datetime
from typing import Protocol

from app.domain.entities import LegoSet, Part
from app.domain.repositories.dtos import PartFoundUpdate


class SetRepository(Protocol):
    def get(self, set_num: str) -> LegoSet | None: ...

    def list_all(self) -> list[LegoSet]: ...

    def save(self, set_: LegoSet) -> None:
        """Upsert the set and its parts. Existing parts keep their quantity_found;
        only catalog fields (name, quantity_required, image, ...) are refreshed."""
        ...

    def delete(self, set_num: str) -> None:
        """Remove the set and its parts. Minifig instances and history rows belong to other
        repositories and must be cleaned up by the caller."""
        ...

    def list_referenced_image_paths(self) -> set[str]:
        """Every cached image path still in use by a set or set part, for cache cleanup."""
        ...

    def get_part(self, set_num: str, part_num: str, color_id: int) -> Part | None:
        """The tracked (non-spare) part for this part/colour, or None. A set can carry the same
        part/colour as both a build part and a spare; only the build part is tracked, so
        part_num + color_id identifies it unambiguously."""
        ...

    def update_part_found(self, set_num: str, part_num: str, color_id: int, quantity_found: int) -> Part:
        """Set the confirmed-present count on the tracked (non-spare) part. See `get_part`."""
        ...

    def update_parts_found(self, set_num: str, updates: list[PartFoundUpdate]) -> list[Part]:
        """Apply many found counts in one transaction, for confirming a whole screen of parts at
        once. Unknown parts are skipped rather than failing the batch, so a stale client cannot
        abort an otherwise valid bulk confirm. Returns the parts actually written."""
        ...

    def set_sorting_finished(self, set_num: str, finished_at: datetime | None) -> None:
        """Mark this set as done being sorted, or clear the marker to resume."""
        ...

    def prune_parts_not_in(self, set_num: str, keep_keys: set[tuple[str, int, bool]]) -> None:
        """On resync: zero out quantity_required for parts no longer in the upstream list,
        without deleting the row, to preserve missing_history referential integrity."""
        ...
