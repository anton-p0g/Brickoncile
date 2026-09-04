from datetime import UTC, datetime

from app.domain.entities import (
    EntityType,
    LegoSet,
    MinifigInstance,
    MissingPartRecord,
    Part,
)
from app.domain.errors import EntityNotFoundError
from app.domain.repositories import (
    MinifigInstanceRepository,
    MissingHistoryRepository,
    SetRepository,
)
from app.domain.repositories.dtos import PartFoundUpdate


class SetPartsFoundUseCase:
    """Set the confirmed-present count on many parts at once.

    This is what "confirm everything still showing" runs on: finishing a set otherwise means tapping
    every remaining card, which for a 500-part set with four pieces missing is hundreds of taps to
    record four. Targets are explicit rather than "everything in the set", so the client's active
    filters decide the scope and nothing hidden is confirmed by surprise.

    Each part that actually changes is logged individually, so a bulk confirm stays as auditable as
    the taps it replaces, and can be undone by sending the previous counts back.
    """

    def __init__(
        self,
        set_repo: SetRepository,
        instance_repo: MinifigInstanceRepository,
        history_repo: MissingHistoryRepository,
    ):
        self.set_repo = set_repo
        self.instance_repo = instance_repo
        self.history_repo = history_repo

    def execute(
        self, entity_type: EntityType, entity_id: str, updates: list[PartFoundUpdate]
    ) -> tuple[list[Part], LegoSet | MinifigInstance]:
        inventory = self._get_inventory(entity_type, entity_id)
        current = {(p.part_num, p.color_id): p for p in inventory.parts if not p.is_spare}

        changed: list[PartFoundUpdate] = []
        for update in updates:
            part = current.get((update.part_num, update.color_id))
            if part is None:
                continue
            clamped = max(0, min(part.quantity_required, update.quantity_found))
            if clamped == part.quantity_found:
                continue
            changed.append(
                PartFoundUpdate(part_num=part.part_num, color_id=part.color_id, quantity_found=clamped)
            )
            if clamped < part.quantity_broken:
                self.history_repo.append(
                    MissingPartRecord(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        part_num=part.part_num,
                        color_id=part.color_id,
                        action="unmarked_broken",
                        quantity_before=part.quantity_broken,
                        quantity_after=clamped,
                        timestamp=datetime.now(UTC),
                    )
                )
            self.history_repo.append(
                MissingPartRecord(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    part_num=part.part_num,
                    color_id=part.color_id,
                    action="marked_found" if clamped > part.quantity_found else "marked_missing",
                    quantity_before=part.quantity_found,
                    quantity_after=clamped,
                    timestamp=datetime.now(UTC),
                )
            )

        written = self._write(entity_type, entity_id, changed) if changed else []
        return written, self._get_inventory(entity_type, entity_id)

    def _get_inventory(self, entity_type: EntityType, entity_id: str) -> LegoSet | MinifigInstance:
        inventory = (
            self.set_repo.get(entity_id) if entity_type == "set" else self.instance_repo.get(entity_id)
        )
        if inventory is None:
            raise EntityNotFoundError(f"{entity_type} {entity_id} not found in local cache")
        return inventory

    def _write(self, entity_type: EntityType, entity_id: str, updates: list[PartFoundUpdate]) -> list[Part]:
        if entity_type == "set":
            return self.set_repo.update_parts_found(entity_id, updates)
        return self.instance_repo.update_parts_found(entity_id, updates)
