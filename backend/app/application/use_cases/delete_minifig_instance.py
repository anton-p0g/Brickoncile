from app.domain.errors import EntityNotFoundError, EntityOwnedBySetError
from app.domain.repositories import (
    MinifigInstanceRepository,
    MinifigRepository,
    MissingHistoryRepository,
    SetRepository,
)


class DeleteMinifigInstanceUseCase:
    """Remove one loose minifig along with its part rows, its audit trail, the catalog entry once no
    instance is left holding it.

    Only loose instances can go this way. One that came from a set is the set's to account for:
    `SyncMinifigRosterUseCase` recreates whatever its roster says is missing, so deleting it here
    would last until the next resync and then silently come back.

    Cached images are retained because the same files can be referenced by another collection.
    """

    def __init__(
        self,
        instance_repo: MinifigInstanceRepository,
        minifig_repo: MinifigRepository,
        history_repo: MissingHistoryRepository,
        set_repo: SetRepository,
    ):
        self.instance_repo = instance_repo
        self.minifig_repo = minifig_repo
        self.history_repo = history_repo
        self.set_repo = set_repo

    def execute(self, instance_id: str) -> None:
        instance = self.instance_repo.get(instance_id)
        if instance is None:
            raise EntityNotFoundError(f"minifig instance {instance_id} not found")
        if instance.source_set_num is not None:
            raise EntityOwnedBySetError(
                f"minifig instance {instance_id} came from set {instance.source_set_num}; "
                "remove the set instead"
            )

        self.history_repo.delete_for_entity("minifig_instance", instance_id)
        self.instance_repo.delete(instance_id)

        self._prune_orphaned_minifig(instance.fig_num)

    def _prune_orphaned_minifig(self, fig_num: str) -> None:
        """Drop the catalog entry once its last owned instance is gone."""
        if self.instance_repo.list_by_fig_num(fig_num):
            return
        self.minifig_repo.delete(fig_num)
