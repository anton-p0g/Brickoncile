from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.application.use_cases.sync_minifig_roster import SyncMinifigRosterUseCase
from app.domain.repositories.dtos import MinifigRosterEntryDTO
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigInstanceRepository,
    FakeMinifigRepository,
    FakePartsCatalogClient,
    make_minifig_metadata_dto,
    make_part_dto,
)


def make_use_case(catalog: FakePartsCatalogClient):
    instance_repo = FakeMinifigInstanceRepository()
    images = FakeImageCache()
    fetch_minifig = FetchMinifigUseCase(FakeMinifigRepository(), catalog, images)
    return SyncMinifigRosterUseCase(instance_repo, catalog, fetch_minifig), instance_repo


def make_catalog(quantity: int = 1) -> FakePartsCatalogClient:
    return FakePartsCatalogClient(
        set_minifigs={"75192-1": [MinifigRosterEntryDTO(fig_num="sw0001", quantity=quantity, image_url=None)]},
        minifigs={"sw0001": make_minifig_metadata_dto()},
        minifig_parts={"sw0001": [make_part_dto("3624", 14, quantity=1)]},
    )


async def test_creates_one_instance_per_minifig_the_set_contains():
    use_case, instance_repo = make_use_case(make_catalog(quantity=2))

    await use_case.execute("75192-1")

    assert instance_repo.count_by_fig_and_set("sw0001", "75192-1") == 2


async def test_running_again_creates_nothing_new():
    use_case, instance_repo = make_use_case(make_catalog())
    await use_case.execute("75192-1")

    await use_case.execute("75192-1")

    assert instance_repo.count_by_fig_and_set("sw0001", "75192-1") == 1


async def test_resumes_a_roster_that_only_half_landed():
    """The recovery path for an add whose roster was cut short: only the shortfall is created,
    so the set does not have to be removed and added again to get its minifigs."""
    catalog = make_catalog(quantity=3)
    use_case, instance_repo = make_use_case(catalog)

    # First run lands one of the three, as if the catalog started refusing calls after it.
    catalog.set_minifigs["75192-1"] = [MinifigRosterEntryDTO(fig_num="sw0001", quantity=1, image_url=None)]
    await use_case.execute("75192-1")
    assert instance_repo.count_by_fig_and_set("sw0001", "75192-1") == 1

    catalog.set_minifigs["75192-1"] = [MinifigRosterEntryDTO(fig_num="sw0001", quantity=3, image_url=None)]
    await use_case.execute("75192-1")

    assert instance_repo.count_by_fig_and_set("sw0001", "75192-1") == 3
