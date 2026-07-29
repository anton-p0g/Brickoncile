from datetime import UTC, datetime

from app.application.use_cases._shared import build_parts_from_dtos, drop_spares
from app.domain.entities import Minifig
from app.domain.repositories import ImageCache, MinifigRepository, PartsCatalogClient


class FetchMinifigUseCase:
    """Cache-once-fetch-forever for a minifig catalog entry (fig_num -> name/image/parts template)."""

    def __init__(self, minifig_repo: MinifigRepository, catalog: PartsCatalogClient, images: ImageCache):
        self.minifig_repo = minifig_repo
        self.catalog = catalog
        self.images = images

    async def execute(self, fig_num: str) -> Minifig:
        cached = self.minifig_repo.get(fig_num)
        if cached is not None:
            return cached

        metadata = await self.catalog.fetch_minifig_metadata(fig_num)
        part_dtos = await self.catalog.fetch_minifig_parts(fig_num)

        image_path = await self.images.get_or_download(metadata.image_url, "minifigs", fig_num)
        parts = await build_parts_from_dtos(self.images, drop_spares(part_dtos))

        minifig = Minifig(
            fig_num=metadata.fig_num,
            name=metadata.name,
            num_parts=metadata.num_parts,
            image_path=image_path,
            last_synced_at=datetime.now(UTC),
            parts=parts,
        )
        self.minifig_repo.save(minifig)
        return minifig
