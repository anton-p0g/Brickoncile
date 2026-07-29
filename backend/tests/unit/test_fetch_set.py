from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.application.use_cases.fetch_set import FetchSetUseCase
from app.application.use_cases.sync_minifig_roster import SyncMinifigRosterUseCase
from app.application.use_cases.sync_themes import SyncThemesUseCase
from app.domain.repositories.dtos import MinifigRosterEntryDTO
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigInstanceRepository,
    FakeMinifigRepository,
    FakePartsCatalogClient,
    FakeSetRepository,
    FakeThemeRepository,
    make_minifig_metadata_dto,
    make_part_dto,
    make_set_metadata_dto,
)


def make_use_case(catalog: FakePartsCatalogClient, instance_repo=None, set_repo=None, theme_repo=None):
    instance_repo = instance_repo or FakeMinifigInstanceRepository()
    set_repo = set_repo or FakeSetRepository()
    theme_repo = theme_repo or FakeThemeRepository()
    minifig_repo = FakeMinifigRepository()
    images = FakeImageCache()
    fetch_minifig = FetchMinifigUseCase(minifig_repo, catalog, images)
    sync_roster = SyncMinifigRosterUseCase(instance_repo, catalog, fetch_minifig)
    sync_themes = SyncThemesUseCase(theme_repo, catalog)
    use_case = FetchSetUseCase(set_repo, catalog, images, sync_roster, sync_themes)
    return use_case, set_repo, instance_repo


async def test_fetch_set_cache_miss_fetches_parts_and_saves():
    catalog = FakePartsCatalogClient(
        sets={"75192-1": make_set_metadata_dto()},
        set_parts={"75192-1": [make_part_dto("3001", 0, quantity=4), make_part_dto("3020", 15, quantity=2)]},
    )
    use_case, set_repo, _ = make_use_case(catalog)

    lego_set = await use_case.execute("75192-1")

    assert lego_set.set_num == "75192-1"
    assert len(lego_set.parts) == 2
    assert lego_set.total_missing == 0
    assert set_repo.get("75192-1") is not None


async def test_fetch_set_cache_hit_returns_without_refetch():
    catalog = FakePartsCatalogClient(sets={"75192-1": make_set_metadata_dto()}, set_parts={"75192-1": []})
    use_case, _, _ = make_use_case(catalog)
    await use_case.execute("75192-1")

    catalog.sets.clear()
    lego_set = await use_case.execute("75192-1")

    assert lego_set.set_num == "75192-1"


async def test_fetch_set_syncs_minifig_roster_and_creates_instances():
    catalog = FakePartsCatalogClient(
        sets={"75192-1": make_set_metadata_dto()},
        set_parts={"75192-1": []},
        set_minifigs={"75192-1": [MinifigRosterEntryDTO(fig_num="sw0001", quantity=2, image_url="https://x/fig.jpg")]},
        minifigs={"sw0001": make_minifig_metadata_dto()},
        minifig_parts={"sw0001": [make_part_dto("3624", 14)]},
    )
    use_case, _, instance_repo = make_use_case(catalog)

    await use_case.execute("75192-1")

    instances = instance_repo.list_by_source_set("75192-1")
    assert len(instances) == 2
    assert all(i.fig_num == "sw0001" for i in instances)
    assert all(len(i.parts) == 1 for i in instances)
    assert instances[0].id != instances[1].id


async def test_fetch_set_normalizes_bare_number_to_dash_one_variant():
    catalog = FakePartsCatalogClient(
        sets={"70202-1": make_set_metadata_dto(set_num="70202-1", name="CHI Gorzan")},
        set_parts={"70202-1": []},
    )
    use_case, set_repo, _ = make_use_case(catalog)

    lego_set = await use_case.execute("70202")

    assert lego_set.set_num == "70202-1"
    assert set_repo.get("70202-1") is not None


async def test_fetch_set_leaves_existing_variant_suffix_untouched():
    catalog = FakePartsCatalogClient(
        sets={"5002887-3": make_set_metadata_dto(set_num="5002887-3", name="The LEGO Book")},
        set_parts={"5002887-3": []},
    )
    use_case, _, _ = make_use_case(catalog)

    lego_set = await use_case.execute("5002887-3")

    assert lego_set.set_num == "5002887-3"


async def test_fetch_set_keeps_the_set_when_its_minifig_roster_fails():
    """The parts are the expensive half of the fetch and they already landed, so a roster that
    fails (a throttled catalog, a fig the API has no record of) is reported, not raised."""
    catalog = FakePartsCatalogClient(
        sets={"75192-1": make_set_metadata_dto()},
        set_parts={"75192-1": [make_part_dto("3001", 0, quantity=4)]},
        set_minifigs={"75192-1": [MinifigRosterEntryDTO(fig_num="sw0001", quantity=1, image_url=None)]},
        # "sw0001" deliberately absent from `minifigs`, so fetching it raises.
    )
    use_case, set_repo, instance_repo = make_use_case(catalog)

    outcome = await use_case.execute_with_outcome("75192-1")

    assert outcome.already_owned is False
    assert any("minifigures could not be fetched" in w for w in outcome.warnings)
    # The set is in the collection with its parts; only the minifigs are missing.
    assert set_repo.get("75192-1") is not None
    assert len(outcome.lego_set.parts) == 1
    assert instance_repo.count_by_fig_and_set("sw0001", "75192-1") == 0


async def test_fetch_set_reports_no_minifig_error_on_a_clean_fetch():
    catalog = FakePartsCatalogClient(
        sets={"75192-1": make_set_metadata_dto()},
        set_parts={"75192-1": []},
        set_minifigs={"75192-1": [MinifigRosterEntryDTO(fig_num="sw0001", quantity=1, image_url=None)]},
        minifigs={"sw0001": make_minifig_metadata_dto()},
        minifig_parts={"sw0001": []},
    )
    use_case, _, _ = make_use_case(catalog)

    outcome = await use_case.execute_with_outcome("75192-1")

    assert outcome.warnings == ()
