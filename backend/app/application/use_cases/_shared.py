import asyncio

from app.domain.entities import Part
from app.domain.repositories import ImageCache
from app.domain.repositories.dtos import PartDTO

IMAGE_DOWNLOAD_CONCURRENCY = 12


def drop_spares(part_dtos: list[PartDTO]) -> list[PartDTO]:
    """Spares are extras, never tracked. Minifig part rows carry no is_spare column, so a spare that
    duplicates a build part's part/colour would collide with it on save; dropping them up front
    keeps one row per tracked part. Sets keep their spares, which are stored as distinct rows."""
    return [dto for dto in part_dtos if not dto.is_spare]


async def build_parts_from_dtos(images: ImageCache, part_dtos: list[PartDTO]) -> list[Part]:
    """Download each part's image (bounded concurrency) and build the Part list, nothing found yet."""
    semaphore = asyncio.Semaphore(IMAGE_DOWNLOAD_CONCURRENCY)

    async def build(dto: PartDTO) -> Part:
        async with semaphore:
            image_path = await images.get_or_download(dto.image_url, "parts", f"{dto.part_num}_{dto.color_id}")
        return Part(
            part_num=dto.part_num,
            color_id=dto.color_id,
            color_name=dto.color_name,
            name=dto.part_name,
            element_id=dto.element_id,
            quantity_required=dto.quantity,
            quantity_found=0,
            image_path=image_path,
            is_spare=dto.is_spare,
        )

    return list(await asyncio.gather(*(build(dto) for dto in part_dtos)))
