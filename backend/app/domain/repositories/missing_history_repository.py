from typing import Protocol

from app.domain.entities import EntityType, MissingPartRecord


class MissingHistoryRepository(Protocol):
    def append(self, record: MissingPartRecord) -> None: ...

    def list_for_entity(
        self, entity_type: EntityType, entity_id: str, part_num: str | None = None, color_id: int | None = None
    ) -> list[MissingPartRecord]: ...

    def delete_for_entity(self, entity_type: EntityType, entity_id: str) -> None:
        """Drop the audit trail for an entity being removed from the collection entirely."""
        ...

    def exists_for_part(self, entity_type: EntityType, entity_id: str, part_num: str, color_id: int) -> bool: ...
