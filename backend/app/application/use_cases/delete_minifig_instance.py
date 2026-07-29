from app.domain.errors import EntityNotFoundError, EntityOwnedBySetError
from app.domain.repositories import (
    ImageCache,
    MinifigInstanceRepository,
    MinifigRepository,
    MissingHistoryRepository,
    SetRepository,
)


class DeleteMinifigInstanceUseCase:
    """Remove one loose minifig along with its part rows, its audit trail, the catalog entry once no
    instance is left holding it, and every cached image nothing else still references.

    Only loose instances can go this way. One that came from a set is the set's to account for:
    `SyncMinifigRosterUseCase` recreates whatever its roster says is missing, so deleting it here
    would last until the next resync and then silently come back.

    Image cleanup is reference-counted, exactly as in `DeleteSetUseCase`: `parts/3001_0.jpg` is
    shared by every set and minifig using that brick in that colour, so a path is only unlinked
    once nothing at all still points at it.
    """

    def __init__(
        self,
        instance_repo: MinifigInstanceRepository,
        minifig_repo: MinifigRepository,
        history_repo: MissingHistoryRepository,
        set_repo: SetRepository,
        images: ImageCache,
    ):
        self.instance_repo = instance_repo
        self.minifig_repo = minifig_repo
        self.history_repo = history_repo
        self.set_repo = set_repo
        self.images = images

    def execute(self, instance_id: str) -> None:
        instance = self.instance_repo.get(instance_id)
        if instance is None:
            raise EntityNotFoundError(f"minifig instance {instance_id} not found")
        if instance.source_set_num is not None:
            raise EntityOwnedBySetError(
                f"minifig instance {instance_id} came from set {instance.source_set_num}; "
                "remove the set instead"
            )

        # Collect the paths while the rows that name them still exist.
        candidates = {
            path
            for path in (instance.image_path, *(part.image_path for part in instance.parts))
            if path
        }

        self.history_repo.delete_for_entity("minifig_instance", instance_id)
        self.instance_repo.delete(instance_id)

        candidates |= self._prune_orphaned_minifig(instance.fig_num)
        self._delete_unreferenced_images(candidates)

    def _prune_orphaned_minifig(self, fig_num: str) -> set[str]:
        """Drop the catalog entry once its last owned instance is gone, returning the image paths it
        held. A fig still owned elsewhere — another loose copy, or one from a set — is left alone."""
        if self.instance_repo.list_by_fig_num(fig_num):
            return set()
        minifig = self.minifig_repo.get(fig_num)
        freed = (
            {path for path in (minifig.image_path, *(p.image_path for p in minifig.parts)) if path}
            if minifig is not None
            else set()
        )
        self.minifig_repo.delete(fig_num)
        return freed

    def _delete_unreferenced_images(self, candidates: set[str]) -> None:
        still_referenced = (
            self.set_repo.list_referenced_image_paths()
            | self.instance_repo.list_referenced_image_paths()
            | self.minifig_repo.list_referenced_image_paths()
        )
        for path in candidates - still_referenced:
            self.images.delete(path)
