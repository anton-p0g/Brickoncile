import pytest

from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.application.use_cases.fetch_set import FetchSetUseCase
from app.application.use_cases.resync_from_source import ResyncFromSourceUseCase
from app.application.use_cases.sync_minifig_roster import SyncMinifigRosterUseCase
from app.application.use_cases.sync_themes import SyncThemesUseCase
from app.domain.errors import EntityNotFoundError
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


class Fixture:
    """The repos and use cases for one test, wired the way the API wires them: the fetch and the
    resync share a set repo and a roster sync, which is what makes resync a repair path."""

    def __init__(self, catalog: FakePartsCatalogClient):
        self.catalog = catalog
        self.set_repo = FakeSetRepository()
        self.minifig_repo = FakeMinifigRepository()
        self.instance_repo = FakeMinifigInstanceRepository()
        self.images = FakeImageCache()
        fetch_minifig = FetchMinifigUseCase(self.minifig_repo, catalog, self.images)
        sync_roster = SyncMinifigRosterUseCase(self.instance_repo, catalog, fetch_minifig)
        self.fetch_set = FetchSetUseCase(
            self.set_repo, catalog, self.images, sync_roster, SyncThemesUseCase(FakeThemeRepository(), catalog)
        )
        self.resync = ResyncFromSourceUseCase(
            self.set_repo, self.minifig_repo, self.instance_repo, catalog, self.images, sync_roster
        )


async def test_resync_set_updates_required_quantity_but_preserves_found():
    f = Fixture(
        FakePartsCatalogClient(
            sets={"75192-1": make_set_metadata_dto()},
            set_parts={"75192-1": [make_part_dto("3001", 0, quantity=4)]},
        )
    )
    await f.fetch_set.execute("75192-1")

    # Simulate 3 of the 4 pieces physically confirmed present before resyncing.
    f.set_repo.update_part_found("75192-1", "3001", 0, quantity_found=3)

    # Upstream catalog now requires 6 instead of 4.
    f.catalog.set_parts["75192-1"] = [make_part_dto("3001", 0, quantity=6)]

    updated = await f.resync.execute("set", "75192-1")

    part = next(p for p in updated.parts if p.part_num == "3001")
    assert part.quantity_required == 6
    # The verified found count survives a catalog change to quantity_required.
    assert part.quantity_found == 3


async def test_resync_set_zeroes_out_removed_parts_without_deleting():
    f = Fixture(
        FakePartsCatalogClient(
            sets={"75192-1": make_set_metadata_dto()},
            set_parts={"75192-1": [make_part_dto("3001", 0, quantity=4), make_part_dto("3020", 15, quantity=2)]},
        )
    )
    await f.fetch_set.execute("75192-1")

    # "3020" no longer appears in the upstream parts list.
    f.catalog.set_parts["75192-1"] = [make_part_dto("3001", 0, quantity=4)]

    updated = await f.resync.execute("set", "75192-1")

    removed = next(p for p in updated.parts if p.part_num == "3020")
    assert removed.quantity_required == 0
    assert any(p.part_num == "3020" for p in updated.parts)  # row kept, not deleted


async def test_resync_set_completes_a_minifig_roster_that_failed_at_add_time():
    """A set whose roster could not be fetched is otherwise stuck: re-adding says "already owned"
    and does nothing, so the resync has to be what finishes the job."""
    f = Fixture(
        FakePartsCatalogClient(
            sets={"75192-1": make_set_metadata_dto()},
            set_parts={"75192-1": []},
            set_minifigs={"75192-1": [MinifigRosterEntryDTO(fig_num="sw0001", quantity=1, image_url=None)]},
            # "sw0001" absent from `minifigs`, so the roster sync fails during the add.
        )
    )
    outcome = await f.fetch_set.execute_with_outcome("75192-1")
    assert any("minifigures could not be fetched" in w for w in outcome.warnings)
    assert f.instance_repo.count_by_fig_and_set("sw0001", "75192-1") == 0

    f.catalog.minifigs["sw0001"] = make_minifig_metadata_dto()
    await f.resync.execute("set", "75192-1")

    assert f.instance_repo.count_by_fig_and_set("sw0001", "75192-1") == 1


async def test_resync_set_raises_if_not_cached():
    f = Fixture(FakePartsCatalogClient())

    with pytest.raises(EntityNotFoundError):
        await f.resync.execute("set", "unknown")


async def test_resync_minifig_propagates_required_quantity_preserving_found():
    f = Fixture(
        FakePartsCatalogClient(
            minifigs={"sw0001": make_minifig_metadata_dto()},
            minifig_parts={"sw0001": [make_part_dto("3624", 14, quantity=1)]},
        )
    )
    minifig = await FetchMinifigUseCase(f.minifig_repo, f.catalog, f.images).execute("sw0001")
    instance = f.instance_repo.create(
        fig_num="sw0001",
        fig_name=minifig.name,
        image_path=minifig.image_path,
        source_set_num="75192-1",
        parts_template=minifig.parts,
    )
    f.instance_repo.update_part_found(instance.id, "3624", 14, quantity_found=1)

    # Upstream now requires 2 heads instead of 1 (unrealistic for a head, but exercises the propagation path).
    f.catalog.minifig_parts["sw0001"] = [make_part_dto("3624", 14, quantity=2)]

    await f.resync.execute("minifig", "sw0001")

    updated_instance = f.instance_repo.get(instance.id)
    part = next(p for p in updated_instance.parts if p.part_num == "3624")
    assert part.quantity_required == 2
    assert part.quantity_found == 1
