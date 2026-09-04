from datetime import UTC, datetime

from app.domain.entities import MinifigInstance, MissingPartRecord, Part
from app.domain.errors import EntityNotFoundError
from app.domain.repositories import MinifigInstanceRepository, MissingHistoryRepository


class AdjustMinifigPartFoundUseCase:
    """Same clamped found-count semantics as AdjustSetPartFoundUseCase, scoped to one physically
    owned minifig instance."""

    def __init__(self, instance_repo: MinifigInstanceRepository, history_repo: MissingHistoryRepository):
        self.instance_repo = instance_repo
        self.history_repo = history_repo

    def execute(
        self, instance_id: str, part_num: str, color_id: int, found_delta: int
    ) -> tuple[Part, MinifigInstance]:
        part = self.instance_repo.get_part(instance_id, part_num, color_id)
        if part is None:
            raise EntityNotFoundError(f"part {part_num}/{color_id} not found on minifig instance {instance_id}")

        new_quantity = max(0, min(part.quantity_required, part.quantity_found + found_delta))

        if new_quantity != part.quantity_found:
            if new_quantity < part.quantity_broken:
                self.history_repo.append(
                    MissingPartRecord(
                        entity_type="minifig_instance",
                        entity_id=instance_id,
                        part_num=part_num,
                        color_id=color_id,
                        action="unmarked_broken",
                        quantity_before=part.quantity_broken,
                        quantity_after=new_quantity,
                        timestamp=datetime.now(UTC),
                    )
                )
            self.history_repo.append(
                MissingPartRecord(
                    entity_type="minifig_instance",
                    entity_id=instance_id,
                    part_num=part_num,
                    color_id=color_id,
                    action="marked_found" if new_quantity > part.quantity_found else "marked_missing",
                    quantity_before=part.quantity_found,
                    quantity_after=new_quantity,
                    timestamp=datetime.now(UTC),
                )
            )
            updated_part = self.instance_repo.update_part_found(instance_id, part_num, color_id, new_quantity)
        else:
            updated_part = part

        updated_instance = self.instance_repo.get(instance_id)
        assert updated_instance is not None
        return updated_part, updated_instance
