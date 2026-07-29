from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.domain.entities.part import Part
from app.domain.entities.sorting_status import SortingStatus, derive_status


def _now() -> datetime:
    return datetime.now(UTC)


class LegoSet(BaseModel):
    set_num: str
    name: str
    year: int | None = None
    theme_id: int | None = None
    num_parts: int
    image_path: str | None = None
    last_synced_at: datetime
    """When this set entered the collection. Set on first save and preserved across resyncs."""
    added_at: datetime = Field(default_factory=_now)
    """Set when the owner declares the sort finished, which is what turns unfound pieces into
    confirmed missing ones. Cleared again if they resume sorting."""
    sorting_finished_at: datetime | None = None
    parts: list[Part] = Field(default_factory=list)

    @property
    def _tracked_parts(self) -> list[Part]:
        """Spares are excluded from every total: they are extras, not part of the build."""
        return [p for p in self.parts if not p.is_spare]

    @property
    def total_required(self) -> int:
        """Pieces this set needs, per the cached parts list. This is the denominator for completion
        percentage; `num_parts` is Rebrickable metadata that counts differently."""
        return sum(p.quantity_required for p in self._tracked_parts)

    @property
    def total_found(self) -> int:
        return sum(p.quantity_found for p in self._tracked_parts)

    @property
    def is_sorted(self) -> bool:
        return self.sorting_finished_at is not None

    @property
    def total_missing(self) -> int:
        """Confirmed missing pieces. Zero while sorting is still in progress: unfound pieces are
        only "not checked yet" until the owner finishes, so a half-sorted set never inflates the
        shopping list with pieces that are sitting in the pile."""
        if not self.is_sorted:
            return 0
        return sum(p.quantity_unaccounted for p in self._tracked_parts)

    @property
    def status(self) -> SortingStatus:
        return derive_status(self.total_required, self.total_found, self.sorting_finished_at)

    @property
    def is_complete(self) -> bool:
        return self.total_found >= self.total_required
