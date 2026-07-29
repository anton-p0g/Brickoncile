from app.domain.errors import EntityNotFoundError
from app.domain.repositories import (
    ImageCache,
    MinifigInstanceRepository,
    MinifigRepository,
    MissingHistoryRepository,
    SetRepository,
)


def _image_paths(*values: str | None) -> set[str]:
    """Collect image paths, dropping the entries that were never cached."""
    return {value for value in values if value}


class DeleteSetUseCase:
    """Remove a set from the collection along with everything that belonged only to it: its parts,
    the minifig instances it introduced, the audit trail for both, any minifig catalog entry left
    without instances, and every cached image that nothing else still references.

    Image cleanup is reference-counted rather than blind. A part image is keyed by part number and
    colour, so `parts/3001_0.jpg` is shared by every set and minifig using that brick in black:
    deleting it because one set went away would blank out thumbnails everywhere else.
    """

    def __init__(
        self,
        set_repo: SetRepository,
        instance_repo: MinifigInstanceRepository,
        minifig_repo: MinifigRepository,
        history_repo: MissingHistoryRepository,
        images: ImageCache,
    ):
        self.set_repo = set_repo
        self.instance_repo = instance_repo
        self.minifig_repo = minifig_repo
        self.history_repo = history_repo
        self.images = images

    def execute(self, set_num: str) -> None:
        lego_set = self.set_repo.get(set_num)
        if lego_set is None:
            raise EntityNotFoundError(f"set {set_num} not found in local cache")

        instances = self.instance_repo.list_by_source_set(set_num)

        # Gather deletion candidates while the rows still exist.
        candidates = _image_paths(lego_set.image_path, *(p.image_path for p in lego_set.parts))
        for instance in instances:
            candidates |= _image_paths(instance.image_path, *(p.image_path for p in instance.parts))

        for instance in instances:
            self.history_repo.delete_for_entity("minifig_instance", instance.id)
            self.instance_repo.delete(instance.id)

        self.history_repo.delete_for_entity("set", set_num)
        self.set_repo.delete(set_num)

        candidates |= self._prune_orphaned_minifigs({i.fig_num for i in instances})
        self._delete_unreferenced_images(candidates)

    def _prune_orphaned_minifigs(self, fig_nums: set[str]) -> set[str]:
        """Drop catalog entries whose last owned instance just went away, returning the image paths
        they held. A fig still owned through another set is left alone."""
        freed: set[str] = set()
        for fig_num in fig_nums:
            if self.instance_repo.list_by_fig_num(fig_num):
                continue
            minifig = self.minifig_repo.get(fig_num)
            if minifig is not None:
                freed |= _image_paths(minifig.image_path, *(p.image_path for p in minifig.parts))
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
