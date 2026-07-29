import pytest

from app.application.use_cases.add_loose_minifig import AddLooseMinifigUseCase
from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.domain.errors import PartsCatalogNotFoundError
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigInstanceRepository,
    FakeMinifigRepository,
    FakePartsCatalogClient,
    make_minifig_metadata_dto,
    make_part_dto,
)


def build(instance_repo, catalog) -> AddLooseMinifigUseCase:
    fetch_minifig = FetchMinifigUseCase(FakeMinifigRepository(), catalog, FakeImageCache())
    return AddLooseMinifigUseCase(instance_repo, fetch_minifig)


async def test_creates_an_instance_with_no_source_set():
    instance_repo = FakeMinifigInstanceRepository()
    catalog = FakePartsCatalogClient(
        minifigs={"fig-000068": make_minifig_metadata_dto("fig-000068", name="Chief Wiggum")},
        minifig_parts={"fig-000068": [make_part_dto("3626", 14, part_name="Head")]},
    )

    instance = await build(instance_repo, catalog).execute("fig-000068")

    assert instance.source_set_num is None
    assert instance.fig_num == "fig-000068"
    assert instance.fig_name == "Chief Wiggum"
    assert len(instance_repo.list_all()) == 1


async def test_copies_the_catalog_parts_template_with_nothing_found_yet():
    instance_repo = FakeMinifigInstanceRepository()
    catalog = FakePartsCatalogClient(
        minifigs={"fig-000068": make_minifig_metadata_dto("fig-000068")},
        minifig_parts={
            "fig-000068": [make_part_dto("3626", 14, part_name="Head"), make_part_dto("973", 1, part_name="Torso")]
        },
    )

    instance = await build(instance_repo, catalog).execute("fig-000068")

    assert len(instance.parts) == 2
    assert all(p.quantity_found == 0 for p in instance.parts)
    assert instance.total_required > 0


async def test_adding_the_same_fig_twice_tracks_two_instances():
    """Owning two of the same minifig is ordinary, and each is sorted separately."""
    instance_repo = FakeMinifigInstanceRepository()
    catalog = FakePartsCatalogClient(
        minifigs={"fig-000068": make_minifig_metadata_dto("fig-000068")},
        minifig_parts={"fig-000068": [make_part_dto()]},
    )
    use_case = build(instance_repo, catalog)

    first = await use_case.execute("fig-000068")
    second = await use_case.execute("fig-000068")

    assert first.id != second.id
    assert len(instance_repo.list_all()) == 2


async def test_raises_when_the_catalog_has_no_such_minifig():
    with pytest.raises(PartsCatalogNotFoundError):
        await build(FakeMinifigInstanceRepository(), FakePartsCatalogClient()).execute("fig-nope")
