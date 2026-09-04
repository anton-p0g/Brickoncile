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


class UpdatePartConditionUseCase:
    """Set a part line's found and broken counts as one consistent state.

    Broken is a subset of found: a broken piece is physically present, so it must never increase
    the missing count. Absolute targets suit the condition editor, whose two steppers can affect
    one another when their invariant would otherwise be violated.
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
        self,
        entity_type: EntityType,
        entity_id: str,
        part_num: str,
        color_id: int,
        quantity_found: int,
        quantity_broken: int,
    ) -> tuple[Part, LegoSet | MinifigInstance]:
        part = self._get_part(entity_type, entity_id, part_num, color_id)
        if part is None:
            raise EntityNotFoundError(
                f"part {part_num}/{color_id} not found on {entity_type} {entity_id}"
            )

        found = max(0, min(part.quantity_required, quantity_found))
        broken = max(0, min(found, quantity_broken))
        timestamp = datetime.now(UTC)

        if found != part.quantity_found:
            self._append_history(
                entity_type,
                entity_id,
                part,
                "marked_found" if found > part.quantity_found else "marked_missing",
                part.quantity_found,
                found,
                timestamp,
            )
        if broken != part.quantity_broken:
            self._append_history(
                entity_type,
                entity_id,
                part,
                "marked_broken" if broken > part.quantity_broken else "unmarked_broken",
                part.quantity_broken,
                broken,
                timestamp,
            )

        if found == part.quantity_found and broken == part.quantity_broken:
            updated = part
        elif entity_type == "set":
            updated = self.set_repo.update_part_condition(
                entity_id, part_num, color_id, found, broken
            )
        else:
            updated = self.instance_repo.update_part_condition(
                entity_id, part_num, color_id, found, broken
            )

        inventory = (
            self.set_repo.get(entity_id)
            if entity_type == "set"
            else self.instance_repo.get(entity_id)
        )
        assert inventory is not None
        return updated, inventory

    def _get_part(
        self, entity_type: EntityType, entity_id: str, part_num: str, color_id: int
    ) -> Part | None:
        if entity_type == "set":
            return self.set_repo.get_part(entity_id, part_num, color_id)
        return self.instance_repo.get_part(entity_id, part_num, color_id)

    def _append_history(
        self,
        entity_type: EntityType,
        entity_id: str,
        part: Part,
        action: str,
        before: int,
        after: int,
        timestamp: datetime,
    ) -> None:
        self.history_repo.append(
            MissingPartRecord(
                entity_type=entity_type,
                entity_id=entity_id,
                part_num=part.part_num,
                color_id=part.color_id,
                action=action,
                quantity_before=before,
                quantity_after=after,
                timestamp=timestamp,
            )
        )
