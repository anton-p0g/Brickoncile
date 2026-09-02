from app.domain.errors import EntityNotFoundError
from app.domain.repositories import (
    MinifigInstanceRepository,
    MinifigRepository,
    MissingHistoryRepository,
    SetRepository,
)


class DeleteSetUseCase:
    """Remove a set from the collection along with everything that belonged only to it: its parts,
    the minifig instances it introduced, the audit trail for both, any minifig catalog entry left
    without instances.

    Images live in a cache shared by every collection. They deliberately outlive collection rows;
    only the global maintenance command can determine that no registered database references one.
    """

    def __init__(
        self,
        set_repo: SetRepository,
        instance_repo: MinifigInstanceRepository,
        minifig_repo: MinifigRepository,
        history_repo: MissingHistoryRepository,
    ):
        self.set_repo = set_repo
        self.instance_repo = instance_repo
        self.minifig_repo = minifig_repo
        self.history_repo = history_repo

    def execute(self, set_num: str) -> None:
        lego_set = self.set_repo.get(set_num)
        if lego_set is None:
            raise EntityNotFoundError(f"set {set_num} not found in local cache")

        instances = self.instance_repo.list_by_source_set(set_num)

        for instance in instances:
            self.history_repo.delete_for_entity("minifig_instance", instance.id)
            self.instance_repo.delete(instance.id)

        self.history_repo.delete_for_entity("set", set_num)
        self.set_repo.delete(set_num)

        self._prune_orphaned_minifigs({i.fig_num for i in instances})

    def _prune_orphaned_minifigs(self, fig_nums: set[str]) -> None:
        """Drop catalog entries whose last owned instance just went away."""
        for fig_num in fig_nums:
            if self.instance_repo.list_by_fig_num(fig_num):
                continue
            self.minifig_repo.delete(fig_num)
