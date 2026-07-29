from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.domain.entities.part import Part
from app.domain.entities.sorting_status import SortingStatus, derive_status


def _now() -> datetime:
    return datetime.now(UTC)


class MinifigInstance(BaseModel):
    """One row per physically-owned minifig, tracked independently of other instances of the same fig_num."""

    id: str
    fig_num: str
    fig_name: str
    image_path: str | None = None
    source_set_num: str | None = None
    """The set that introduced this minifig, or None for a loose one — bought on its own or
    recovered from a mixed pile, with no set in the collection to attribute it to."""
    added_at: datetime = Field(default_factory=_now)
    """Set when the owner declares this minifig's sort finished. See LegoSet.sorting_finished_at."""
    sorting_finished_at: datetime | None = None
    parts: list[Part] = Field(default_factory=list)

    @property
    def _tracked_parts(self) -> list[Part]:
        return [p for p in self.parts if not p.is_spare]

    @property
    def total_required(self) -> int:
        return sum(p.quantity_required for p in self._tracked_parts)

    @property
    def total_found(self) -> int:
        return sum(p.quantity_found for p in self._tracked_parts)

    @property
    def is_sorted(self) -> bool:
        return self.sorting_finished_at is not None

    @property
    def total_missing(self) -> int:
        """Confirmed missing pieces; zero until sorting is finished. See LegoSet.total_missing."""
        if not self.is_sorted:
            return 0
        return sum(p.quantity_unaccounted for p in self._tracked_parts)

    @property
    def status(self) -> SortingStatus:
        return derive_status(self.total_required, self.total_found, self.sorting_finished_at)

    @property
    def is_complete(self) -> bool:
        return self.total_found >= self.total_required
