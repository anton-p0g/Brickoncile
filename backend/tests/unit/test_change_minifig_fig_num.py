from datetime import UTC, datetime

import pytest

from app.application.use_cases.add_loose_minifig import AddLooseMinifigUseCase
from app.application.use_cases.change_minifig_fig_num import ChangeMinifigFigNumUseCase
from app.application.use_cases.delete_minifig_instance import (
    DeleteMinifigInstanceUseCase,
)
from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.application.use_cases.mark_minifig_instance_found import (
    MarkMinifigInstanceFoundUseCase,
)
from app.application.use_cases.set_parts_found import SetPartsFoundUseCase
from app.domain.entities import Part
from app.domain.errors import (
    EntityNotFoundError,
    EntityOwnedBySetError,
    PartsCatalogNotFoundError,
)
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigInstanceRepository,
    FakeMinifigRepository,
    FakeMissingHistoryRepository,
    FakePartsCatalogClient,
    FakeSetRepository,
    make_minifig_metadata_dto,
    make_part_dto,
)

WRONG_FIG = "fig-000001"
RIGHT_FIG = "fig-000002"


def make_part(part_num: str = "3626", color_id: int = 14, required: int = 1) -> Part:
    return Part(
        part_num=part_num,
        color_id=color_id,
        color_name="Black",
        name="Piece",
        quantity_required=required,
    )


def build_catalog() -> FakePartsCatalogClient:
    return FakePartsCatalogClient(
        minifigs={
            WRONG_FIG: make_minifig_metadata_dto(WRONG_FIG, name="Not This One"),
            RIGHT_FIG: make_minifig_metadata_dto(RIGHT_FIG, name="Sebulba"),
        },
        minifig_parts={
            WRONG_FIG: [make_part_dto("3626", 14, part_name="Head")],
            RIGHT_FIG: [make_part_dto("973", 0, part_name="Torso"), make_part_dto("3815", 0, part_name="Hips")],
        },
    )


@pytest.fixture
def world():
    instances = FakeMinifigInstanceRepository()
    minifigs = FakeMinifigRepository()
    history = FakeMissingHistoryRepository()
    sets = FakeSetRepository()
    images = FakeImageCache()
    catalog = build_catalog()

    fetch_minifig = FetchMinifigUseCase(minifigs, catalog, images)
    use_case = ChangeMinifigFigNumUseCase(
        instances,
        fetch_minifig,
        AddLooseMinifigUseCase(instances, fetch_minifig),
        DeleteMinifigInstanceUseCase(instances, minifigs, history, sets, images),
        MarkMinifigInstanceFoundUseCase(instances, SetPartsFoundUseCase(sets, instances, history)),
    )
    return instances, history, images, use_case


async def test_correcting_the_id_refiles_the_figure_under_the_new_catalog_entry(world):
    instances, _, _, use_case = world
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])

    result = await use_case.execute(loose.id, RIGHT_FIG)

    assert result.outcome == "replaced"
    assert result.instance.fig_num == RIGHT_FIG
    assert result.instance.fig_name == "Sebulba"
    assert result.instance.source_set_num is None
    assert result.previous_instance_id == loose.id


async def test_the_corrected_figure_carries_the_new_parts_list_not_the_old_one(world):
    instances, _, _, use_case = world
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])

    result = await use_case.execute(loose.id, RIGHT_FIG)

    assert sorted(p.part_num for p in result.instance.parts) == ["3815", "973"]
    assert all(p.quantity_found == 0 for p in result.instance.parts)


async def test_the_wrongly_filed_instance_is_gone_afterwards(world):
    """The figure is one object; a correction must not leave the collection holding two."""
    instances, _, _, use_case = world
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])

    result = await use_case.execute(loose.id, RIGHT_FIG)

    assert instances.get(loose.id) is None
    assert [i.id for i in instances.list_all()] == [result.instance.id]


async def test_a_set_still_waiting_for_this_figure_takes_it_over(world):
    instances, _, _, use_case = world
    expected = instances.create(RIGHT_FIG, "Sebulba", None, "75320-1", [make_part("973", 0), make_part("3815", 0)])
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])

    result = await use_case.execute(loose.id, RIGHT_FIG)

    assert result.outcome == "claimed_by_set"
    assert result.claimed_set_num == "75320-1"
    assert result.instance.id == expected.id
    assert result.instance.is_complete
    assert instances.get(loose.id) is None
    assert len(instances.list_all()) == 1


async def test_the_claimed_set_copy_is_confirmed_piece_by_piece_so_it_can_be_undone(world):
    instances, history, _, use_case = world
    expected = instances.create(RIGHT_FIG, "Sebulba", None, "75320-1", [make_part("973", 0), make_part("3815", 0)])
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])

    await use_case.execute(loose.id, RIGHT_FIG)

    logged = [(r.entity_id, r.part_num, r.action) for r in history.records]
    assert logged == [(expected.id, "973", "marked_found"), (expected.id, "3815", "marked_found")]


async def test_a_set_copy_already_accounted_for_leaves_the_figure_loose(world):
    """Two of the same figure is ordinary; the set is only owed one, and it already has it."""
    instances, _, _, use_case = world
    accounted_for = instances.create(RIGHT_FIG, "Sebulba", None, "75320-1", [make_part("973", 0)])
    instances.update_part_found(accounted_for.id, "973", 0, 1)
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])

    result = await use_case.execute(loose.id, RIGHT_FIG)

    assert result.outcome == "replaced"
    assert result.instance.source_set_num is None
    assert len(instances.list_all()) == 2


async def test_the_longest_waiting_set_copy_wins_when_several_expect_the_figure(world):
    instances, _, _, use_case = world
    newer = instances.create(RIGHT_FIG, "Sebulba", None, "75320-1", [make_part("973", 0)])
    older = instances.create(RIGHT_FIG, "Sebulba", None, "75290-1", [make_part("973", 0)])
    # Set explicitly rather than relying on creation order, so this asserts the ordering rule and
    # not the resolution of the clock behind added_at's default.
    instances._instances[newer.id].added_at = datetime(2024, 6, 1, tzinfo=UTC)
    instances._instances[older.id].added_at = datetime(2023, 6, 1, tzinfo=UTC)
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])

    result = await use_case.execute(loose.id, RIGHT_FIG)

    assert result.instance.id == older.id
    assert not instances.get(newer.id).is_complete


async def test_resubmitting_the_same_id_leaves_the_record_and_its_progress_alone(world):
    instances, _, _, use_case = world
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])
    instances.update_part_found(loose.id, "3626", 14, 1)

    result = await use_case.execute(loose.id, WRONG_FIG)

    assert result.outcome == "unchanged"
    assert result.instance.id == loose.id
    assert result.instance.total_found == 1


async def test_a_minifig_belonging_to_a_set_cannot_be_refiled(world):
    """Its roster is the set's to state, and a resync would restore whatever this changed."""
    instances, _, _, use_case = world
    owned = instances.create(WRONG_FIG, "Not This One", None, "75320-1", [make_part()])

    with pytest.raises(EntityOwnedBySetError):
        await use_case.execute(owned.id, RIGHT_FIG)

    assert instances.get(owned.id).fig_num == WRONG_FIG


async def test_an_id_the_catalog_does_not_know_changes_nothing(world):
    instances, _, _, use_case = world
    loose = instances.create(WRONG_FIG, "Not This One", None, None, [make_part()])

    with pytest.raises(PartsCatalogNotFoundError):
        await use_case.execute(loose.id, "fig-nope")

    assert instances.get(loose.id) is not None
    assert len(instances.list_all()) == 1


async def test_an_unknown_instance_raises(world):
    _, _, _, use_case = world

    with pytest.raises(EntityNotFoundError):
        await use_case.execute("no-such-instance", RIGHT_FIG)


async def test_an_image_the_replacement_also_uses_survives_the_swap(world):
    """The old record is only removed once the new one exists, so shared images stay referenced."""
    instances, _, images, use_case = world
    loose = instances.create(WRONG_FIG, "Not This One", "minifigs/fig-000001.jpg", None, [make_part()])

    result = await use_case.execute(loose.id, RIGHT_FIG)

    assert result.instance.image_path == "minifigs/fig-000002.jpg"
    assert "minifigs/fig-000002.jpg" not in images.deleted
