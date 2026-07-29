from datetime import UTC, datetime
from typing import Literal

from app.application.use_cases._shared import build_parts_from_dtos, drop_spares
from app.application.use_cases.sync_minifig_roster import SyncMinifigRosterUseCase
from app.domain.entities import LegoSet, Minifig
from app.domain.errors import EntityNotFoundError
from app.domain.repositories import (
    ImageCache,
    MinifigInstanceRepository,
    MinifigRepository,
    PartsCatalogClient,
    SetRepository,
)


class ResyncFromSourceUseCase:
    """Manual refresh: re-pulls metadata/quantity_required from the catalog, but never touches
    quantity_found (physically-verified inventory state) and never deletes a part row."""

    def __init__(
        self,
        set_repo: SetRepository,
        minifig_repo: MinifigRepository,
        instance_repo: MinifigInstanceRepository,
        catalog: PartsCatalogClient,
        images: ImageCache,
        sync_roster: SyncMinifigRosterUseCase,
    ):
        self.set_repo = set_repo
        self.minifig_repo = minifig_repo
        self.instance_repo = instance_repo
        self.catalog = catalog
        self.images = images
        self.sync_roster = sync_roster

    async def execute(self, entity_type: Literal["set", "minifig"], entity_id: str) -> LegoSet | Minifig:
        if entity_type == "set":
            return await self._resync_set(entity_id)
        return await self._resync_minifig(entity_id)

    async def _resync_set(self, set_num: str) -> LegoSet:
        existing = self.set_repo.get(set_num)
        if existing is None:
            raise EntityNotFoundError(f"set {set_num} is not cached, nothing to resync")

        metadata = await self.catalog.fetch_set_metadata(set_num)
        part_dtos = await self.catalog.fetch_set_parts(set_num)

        image_path = await self.images.get_or_download(metadata.image_url, "sets", set_num)
        parts = await build_parts_from_dtos(self.images, part_dtos)

        refreshed = LegoSet(
            set_num=metadata.set_num,
            name=metadata.name,
            year=metadata.year,
            theme_id=metadata.theme_id,
            num_parts=metadata.num_parts,
            image_path=image_path,
            last_synced_at=datetime.now(UTC),
            parts=parts,
        )
        self.set_repo.save(refreshed)
        self.set_repo.prune_parts_not_in(set_num, {(p.part_num, p.color_id, p.is_spare) for p in parts})

        # Also the repair path for a set whose roster failed at add time: the sync only creates
        # the instances that are missing, so a complete roster is left untouched.
        await self.sync_roster.execute(set_num)

        updated = self.set_repo.get(set_num)
        assert updated is not None
        return updated

    async def _resync_minifig(self, fig_num: str) -> Minifig:
        existing = self.minifig_repo.get(fig_num)
        if existing is None:
            raise EntityNotFoundError(f"minifig {fig_num} is not cached, nothing to resync")

        metadata = await self.catalog.fetch_minifig_metadata(fig_num)
        part_dtos = await self.catalog.fetch_minifig_parts(fig_num)

        image_path = await self.images.get_or_download(metadata.image_url, "minifigs", fig_num)
        parts = await build_parts_from_dtos(self.images, drop_spares(part_dtos))

        refreshed = Minifig(
            fig_num=metadata.fig_num,
            name=metadata.name,
            num_parts=metadata.num_parts,
            image_path=image_path,
            last_synced_at=datetime.now(UTC),
            parts=parts,
        )
        self.minifig_repo.save(refreshed)
        # Refreshes quantity_required on every existing instance of this fig, preserving quantity_found.
        self.instance_repo.sync_parts_template(fig_num, parts)

        updated = self.minifig_repo.get(fig_num)
        assert updated is not None
        return updated
