import pytest

from app.application.use_cases.mark_minifig_instance_found import (
    MarkMinifigInstanceFoundUseCase,
)
from app.application.use_cases.set_parts_found import SetPartsFoundUseCase
from app.domain.entities import Part
from app.domain.errors import EntityNotFoundError
from tests.unit.fakes import (
    FakeMinifigInstanceRepository,
    FakeMissingHistoryRepository,
    FakeSetRepository,
)


def make_part(part_num: str, color_id: int, required: int = 1, is_spare: bool = False) -> Part:
    return Part(
        part_num=part_num,
        color_id=color_id,
        color_name="Black",
        name="Piece",
        quantity_required=required,
        is_spare=is_spare,
    )


@pytest.fixture
def repos():
    instances = FakeMinifigInstanceRepository()
    history = FakeMissingHistoryRepository()
    use_case = MarkMinifigInstanceFoundUseCase(
        instances, SetPartsFoundUseCase(FakeSetRepository(), instances, history)
    )
    return instances, history, use_case


def test_marking_found_completes_the_instance(repos):
    instances, _, use_case = repos
    instance = instances.create(
        "fig-003769", "Sebulba", None, "75320-1", [make_part("3626", 14), make_part("973", 0)]
    )

    updated = use_case.execute(instance.id)

    assert updated.is_complete
    assert updated.total_found == updated.total_required
    assert updated.status == "complete"


def test_marking_found_confirms_every_required_piece(repos):
    """An assembled figure means all of its pieces are present, including repeated ones."""
    instances, _, use_case = repos
    instance = instances.create("fig-003769", "Sebulba", None, "75320-1", [make_part("3005", 4, required=2)])

    updated = use_case.execute(instance.id)

    assert [p.quantity_found for p in updated.parts] == [2]


def test_marking_found_logs_each_piece_so_it_can_be_undone(repos):
    instances, history, use_case = repos
    instance = instances.create("fig-003769", "Sebulba", None, "75320-1", [make_part("3626", 14), make_part("973", 0)])

    use_case.execute(instance.id)

    logged = [(r.entity_id, r.part_num, r.action) for r in history.records]
    assert logged == [(instance.id, "3626", "marked_found"), (instance.id, "973", "marked_found")]


def test_marking_found_twice_records_nothing_the_second_time(repos):
    instances, history, use_case = repos
    instance = instances.create("fig-003769", "Sebulba", None, "75320-1", [make_part("3626", 14)])
    use_case.execute(instance.id)

    updated = use_case.execute(instance.id)

    assert updated.is_complete
    assert len(history.records) == 1


def test_marking_found_leaves_spare_pieces_alone(repos):
    """Spares are not part of what the figure needs, so confirming the figure says nothing of them."""
    instances, _, use_case = repos
    instance = instances.create(
        "fig-003769", "Sebulba", None, "75320-1", [make_part("3626", 14), make_part("3005", 4, is_spare=True)]
    )

    updated = use_case.execute(instance.id)

    spare = next(p for p in updated.parts if p.is_spare)
    assert spare.quantity_found == 0
    assert updated.is_complete


def test_marking_found_touches_only_the_copy_named(repos):
    """A set can list the same fig twice; confirming one copy must leave the other still expected."""
    instances, _, use_case = repos
    first = instances.create("fig-003769", "Sebulba", None, "75320-1", [make_part("3626", 14)])
    second = instances.create("fig-003769", "Sebulba", None, "75320-1", [make_part("3626", 14)])

    use_case.execute(first.id)

    assert instances.get(first.id).is_complete
    assert not instances.get(second.id).is_complete


def test_marking_an_unknown_instance_raises(repos):
    _, _, use_case = repos

    with pytest.raises(EntityNotFoundError):
        use_case.execute("no-such-instance")
