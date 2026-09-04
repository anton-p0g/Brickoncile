import pytest

from app.application.use_cases.update_part_condition import UpdatePartConditionUseCase
from app.domain.entities import LegoSet, Part
from app.domain.errors import EntityNotFoundError
from tests.unit.fakes import (
    FakeMinifigInstanceRepository,
    FakeMissingHistoryRepository,
    FakeSetRepository,
)


def make_use_case(set_repo, instance_repo, history):
    return UpdatePartConditionUseCase(set_repo, instance_repo, history)


def seed_set(repo: FakeSetRepository) -> None:
    repo.save(
        LegoSet(
            set_num="75192-1",
            name="Falcon",
            num_parts=4,
            image_path=None,
            last_synced_at="2024-01-01T00:00:00Z",
            parts=[
                Part(
                    part_num="3001",
                    color_id=0,
                    color_name="Black",
                    name="Brick 2x4",
                    quantity_required=4,
                )
            ],
        )
    )


def test_records_broken_as_a_subset_of_found_without_creating_missing_pieces():
    set_repo = FakeSetRepository()
    seed_set(set_repo)
    history = FakeMissingHistoryRepository()

    part, lego_set = make_use_case(
        set_repo, FakeMinifigInstanceRepository(), history
    ).execute("set", "75192-1", "3001", 0, quantity_found=3, quantity_broken=1)

    assert (part.quantity_found, part.quantity_broken, part.quantity_unaccounted) == (3, 1, 1)
    assert lego_set.total_found == 3
    assert [record.action for record in history.records] == ["marked_found", "marked_broken"]


def test_clamps_broken_to_found():
    set_repo = FakeSetRepository()
    seed_set(set_repo)

    part, _ = make_use_case(
        set_repo, FakeMinifigInstanceRepository(), FakeMissingHistoryRepository()
    ).execute("set", "75192-1", "3001", 0, quantity_found=1, quantity_broken=99)

    assert (part.quantity_found, part.quantity_broken) == (1, 1)


def test_removing_a_broken_condition_keeps_the_piece_found():
    set_repo = FakeSetRepository()
    seed_set(set_repo)
    history = FakeMissingHistoryRepository()
    use_case = make_use_case(set_repo, FakeMinifigInstanceRepository(), history)
    use_case.execute("set", "75192-1", "3001", 0, quantity_found=2, quantity_broken=1)

    part, _ = use_case.execute(
        "set", "75192-1", "3001", 0, quantity_found=2, quantity_broken=0
    )

    assert (part.quantity_found, part.quantity_broken) == (2, 0)
    assert history.records[-1].action == "unmarked_broken"


def test_updates_a_minifig_instance_independently():
    instance_repo = FakeMinifigInstanceRepository()
    instance = instance_repo.create(
        fig_num="sw0001",
        fig_name="Luke",
        image_path=None,
        source_set_num="75192-1",
        parts_template=[
            Part(
                part_num="3624",
                color_id=14,
                color_name="Yellow",
                name="Head",
                quantity_required=1,
            )
        ],
    )

    part, updated = make_use_case(
        FakeSetRepository(), instance_repo, FakeMissingHistoryRepository()
    ).execute(
        "minifig_instance",
        instance.id,
        "3624",
        14,
        quantity_found=1,
        quantity_broken=1,
    )

    assert (part.quantity_found, part.quantity_broken) == (1, 1)
    assert updated.is_complete


def test_raises_for_an_unknown_part():
    with pytest.raises(EntityNotFoundError):
        make_use_case(
            FakeSetRepository(),
            FakeMinifigInstanceRepository(),
            FakeMissingHistoryRepository(),
        ).execute("set", "missing", "3001", 0, quantity_found=1, quantity_broken=1)
