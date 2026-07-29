import pytest

from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.domain.errors import PartsCatalogNotFoundError
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigRepository,
    FakePartsCatalogClient,
    make_minifig_metadata_dto,
    make_part_dto,
)


async def test_fetch_minifig_cache_miss_fetches_and_saves():
    repo = FakeMinifigRepository()
    catalog = FakePartsCatalogClient(
        minifigs={"sw0001": make_minifig_metadata_dto()},
        minifig_parts={"sw0001": [make_part_dto("3624", 14, part_name="Head"), make_part_dto("973", 1, part_name="Torso")]},
    )
    use_case = FetchMinifigUseCase(repo, catalog, FakeImageCache())

    minifig = await use_case.execute("sw0001")

    assert minifig.fig_num == "sw0001"
    assert minifig.name == "Luke Skywalker"
    assert minifig.image_path == "minifigs/sw0001.jpg"
    assert len(minifig.parts) == 2
    assert all(p.quantity_found == 0 for p in minifig.parts)
    assert repo.get("sw0001") is not None


async def test_fetch_minifig_cache_hit_does_not_call_catalog():
    repo = FakeMinifigRepository()
    catalog = FakePartsCatalogClient(minifigs={"sw0001": make_minifig_metadata_dto()}, minifig_parts={"sw0001": []})
    use_case = FetchMinifigUseCase(repo, catalog, FakeImageCache())
    await use_case.execute("sw0001")

    catalog.minifigs.clear()  # cache-hit path must not touch the catalog again
    minifig = await use_case.execute("sw0001")

    assert minifig.fig_num == "sw0001"


async def test_fetch_minifig_raises_when_unknown_upstream():
    use_case = FetchMinifigUseCase(FakeMinifigRepository(), FakePartsCatalogClient(), FakeImageCache())

    with pytest.raises(PartsCatalogNotFoundError):
        await use_case.execute("unknown")
