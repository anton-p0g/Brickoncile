from datetime import UTC, datetime

from app.domain.entities import EntityType
from app.domain.errors import EntityNotFoundError
from app.domain.repositories import MinifigInstanceRepository, SetRepository


class UpdateSortingStateUseCase:
    """Finish or resume sorting an inventory.

    Finishing is what gives "missing" its meaning: until then, pieces that have not turned up are
    only unchecked, and the set contributes nothing to the shopping list. Resuming clears the marker
    so a set can be worked through again without discarding the found counts already recorded.
    """

    def __init__(self, set_repo: SetRepository, instance_repo: MinifigInstanceRepository):
        self.set_repo = set_repo
        self.instance_repo = instance_repo

    def execute(self, entity_type: EntityType, entity_id: str, finished: bool) -> None:
        finished_at = datetime.now(UTC) if finished else None
        if entity_type == "set":
            if self.set_repo.get(entity_id) is None:
                raise EntityNotFoundError(f"set {entity_id} not found in local cache")
            self.set_repo.set_sorting_finished(entity_id, finished_at)
        else:
            if self.instance_repo.get(entity_id) is None:
                raise EntityNotFoundError(f"minifig instance {entity_id} not found")
            self.instance_repo.set_sorting_finished(entity_id, finished_at)
