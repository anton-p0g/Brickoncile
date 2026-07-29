from datetime import UTC, datetime

from app.domain.entities import LegoSet, MissingPartRecord, Part
from app.domain.errors import EntityNotFoundError
from app.domain.repositories import MissingHistoryRepository, SetRepository


class AdjustSetPartFoundUseCase:
    """Change how many of a set part's pieces are confirmed present, clamped to
    [0, quantity_required], and record the transition in the audit log.

    A positive delta is the sorting case: pieces turned up in the pile. A negative delta walks it
    back, either a correction or an explicit "this one is missing after all".
    """

    def __init__(self, set_repo: SetRepository, history_repo: MissingHistoryRepository):
        self.set_repo = set_repo
        self.history_repo = history_repo

    def execute(self, set_num: str, part_num: str, color_id: int, found_delta: int) -> tuple[Part, LegoSet]:
        part = self.set_repo.get_part(set_num, part_num, color_id)
        if part is None:
            raise EntityNotFoundError(f"part {part_num}/{color_id} not found on set {set_num}")

        new_quantity = max(0, min(part.quantity_required, part.quantity_found + found_delta))

        if new_quantity != part.quantity_found:
            self.history_repo.append(
                MissingPartRecord(
                    entity_type="set",
                    entity_id=set_num,
                    part_num=part_num,
                    color_id=color_id,
                    # Quantities here are found counts: rising means pieces turned up.
                    action="marked_found" if new_quantity > part.quantity_found else "marked_missing",
                    quantity_before=part.quantity_found,
                    quantity_after=new_quantity,
                    timestamp=datetime.now(UTC),
                )
            )
            updated_part = self.set_repo.update_part_found(set_num, part_num, color_id, new_quantity)
        else:
            updated_part = part

        updated_set = self.set_repo.get(set_num)
        assert updated_set is not None
        return updated_part, updated_set
