from app.application.use_cases.set_parts_found import SetPartsFoundUseCase
from app.domain.entities import MinifigInstance
from app.domain.errors import EntityNotFoundError
from app.domain.repositories import MinifigInstanceRepository
from app.domain.repositories.dtos import PartFoundUpdate


class MarkMinifigInstanceFoundUseCase:
    """Account for a minifig the owner is physically holding, assembled.

    This is what identifying a photograph resolves to when the figure is one an owned set already
    lists. The set expects it, so the copy in hand is that expected copy rather than a new
    possession: recording it as a loose minifig would leave the set still looking for one and the
    collection holding two.

    An assembled figure means every one of its pieces is present, so this confirms them all at
    once. It delegates to `SetPartsFoundUseCase` rather than writing counts itself, which keeps the
    clamping and the per-part audit trail identical to checking the same pieces off by hand — and
    just as reversible.
    """

    def __init__(
        self,
        instance_repo: MinifigInstanceRepository,
        set_parts_found: SetPartsFoundUseCase,
    ):
        self.instance_repo = instance_repo
        self.set_parts_found = set_parts_found

    def execute(self, instance_id: str) -> MinifigInstance:
        instance = self.instance_repo.get(instance_id)
        if instance is None:
            raise EntityNotFoundError(f"minifig instance {instance_id} not found")

        updates = [
            PartFoundUpdate(
                part_num=part.part_num,
                color_id=part.color_id,
                quantity_found=part.quantity_required,
            )
            for part in instance.parts
            if not part.is_spare
        ]
        # Already-found parts are filtered out downstream, so re-running this is a no-op rather
        # than a second page of history saying the same thing.
        _, updated = self.set_parts_found.execute("minifig_instance", instance_id, updates)
        assert isinstance(updated, MinifigInstance)
        return updated
