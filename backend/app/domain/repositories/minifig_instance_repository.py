from datetime import datetime
from typing import Protocol

from app.domain.entities import MinifigInstance, Part
from app.domain.repositories.dtos import PartFoundUpdate


class MinifigInstanceRepository(Protocol):
    def get(self, instance_id: str) -> MinifigInstance | None: ...

    def list_all(self) -> list[MinifigInstance]: ...

    def list_by_source_set(self, set_num: str) -> list[MinifigInstance]: ...

    def list_by_fig_num(self, fig_num: str) -> list[MinifigInstance]: ...

    def count_by_fig_and_set(self, fig_num: str, source_set_num: str) -> int: ...

    def create(self, fig_num: str, fig_name: str, image_path: str | None, source_set_num: str | None, parts_template: list[Part]) -> MinifigInstance:
        """A null `source_set_num` records a loose minifig, owned without a set to attribute it to."""
        ...

    def delete(self, instance_id: str) -> None:
        """Remove one physical instance and its part rows, leaving the shared minifig catalog."""
        ...

    def list_referenced_image_paths(self) -> set[str]:
        """Every cached image path still in use by an instance or instance part."""
        ...

    def get_part(self, instance_id: str, part_num: str, color_id: int) -> Part | None: ...

    def update_part_found(self, instance_id: str, part_num: str, color_id: int, quantity_found: int) -> Part: ...

    def update_part_condition(
        self,
        instance_id: str,
        part_num: str,
        color_id: int,
        quantity_found: int,
        quantity_broken: int,
    ) -> Part:
        """Set found and broken together, keeping broken within the found count."""
        ...

    def update_parts_found(self, instance_id: str, updates: list[PartFoundUpdate]) -> list[Part]:
        """Apply many found counts in one transaction. See SetRepository.update_parts_found."""
        ...

    def set_sorting_finished(self, instance_id: str, finished_at: datetime | None) -> None:
        """Mark this instance as done being sorted, or clear the marker to resume."""
        ...

    def sync_parts_template(self, fig_num: str, template_parts: list[Part]) -> None:
        """Propagate a refreshed catalog part template (from a minifig resync) to every existing
        instance of this fig_num, updating quantity_required only and preserving quantity_found."""
        ...
