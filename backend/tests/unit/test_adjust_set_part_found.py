import pytest

from app.application.use_cases.adjust_set_part_found import AdjustSetPartFoundUseCase
from app.domain.entities import LegoSet, Part
from app.domain.errors import EntityNotFoundError
from tests.unit.fakes import FakeMissingHistoryRepository, FakeSetRepository


def seed_set(repo: FakeSetRepository, quantity_required=4, quantity_found=0) -> None:
    repo.save(
        LegoSet(
            set_num="75192-1",
            name="Falcon",
            year=2017,
            theme_id=1,
            num_parts=4,
            image_path=None,
            last_synced_at="2024-01-01T00:00:00Z",
            parts=[
                Part(
                    part_num="3001",
                    color_id=0,
                    color_name="Black",
                    name="Brick 2x4",
                    element_id=None,
                    quantity_required=quantity_required,
                    quantity_found=quantity_found,
                )
            ],
        )
    )


def test_finding_a_piece_increments_and_records_history():
    set_repo = FakeSetRepository()
    seed_set(set_repo)
    history = FakeMissingHistoryRepository()

    part, _ = AdjustSetPartFoundUseCase(set_repo, history).execute("75192-1", "3001", 0, found_delta=1)

    assert part.quantity_found == 1
    assert part.quantity_unaccounted == 3
    assert len(history.records) == 1
    assert history.records[0].action == "marked_found"
    assert (history.records[0].quantity_before, history.records[0].quantity_after) == (0, 1)


def test_walking_a_find_back_records_it_as_missing():
    set_repo = FakeSetRepository()
    seed_set(set_repo, quantity_found=2)
    history = FakeMissingHistoryRepository()

    part, _ = AdjustSetPartFoundUseCase(set_repo, history).execute("75192-1", "3001", 0, found_delta=-1)

    assert part.quantity_found == 1
    assert history.records[-1].action == "marked_missing"


def test_confirming_a_whole_line_in_one_call():
    """The grid's single tap sends the full required quantity."""
    set_repo = FakeSetRepository()
    seed_set(set_repo, quantity_required=4)

    part, _ = AdjustSetPartFoundUseCase(set_repo, FakeMissingHistoryRepository()).execute(
        "75192-1", "3001", 0, found_delta=4
    )

    assert part.quantity_found == 4
    assert part.is_fully_found


def test_clamps_at_zero():
    set_repo = FakeSetRepository()
    seed_set(set_repo, quantity_found=0)

    part, _ = AdjustSetPartFoundUseCase(set_repo, FakeMissingHistoryRepository()).execute(
        "75192-1", "3001", 0, found_delta=-1
    )

    assert part.quantity_found == 0


def test_clamps_at_quantity_required():
    set_repo = FakeSetRepository()
    seed_set(set_repo, quantity_required=4, quantity_found=4)

    part, _ = AdjustSetPartFoundUseCase(set_repo, FakeMissingHistoryRepository()).execute(
        "75192-1", "3001", 0, found_delta=99
    )

    assert part.quantity_found == 4


def test_no_op_delta_does_not_write_history():
    set_repo = FakeSetRepository()
    seed_set(set_repo, quantity_required=4, quantity_found=4)
    history = FakeMissingHistoryRepository()

    AdjustSetPartFoundUseCase(set_repo, history).execute("75192-1", "3001", 0, found_delta=1)

    assert history.records == []


def test_unfound_pieces_are_not_missing_until_sorting_is_finished():
    """The core rule: a half-sorted set reports nothing missing, because the pieces may still be
    sitting in the pile."""
    set_repo = FakeSetRepository()
    seed_set(set_repo, quantity_required=4, quantity_found=1)

    _, lego_set = AdjustSetPartFoundUseCase(set_repo, FakeMissingHistoryRepository()).execute(
        "75192-1", "3001", 0, found_delta=0
    )
    assert lego_set.status == "sorting"
    assert lego_set.total_missing == 0

    set_repo.set_sorting_finished("75192-1", "2024-01-02T00:00:00Z")
    updated = set_repo.get("75192-1")
    assert updated.status == "sorted"
    assert updated.total_missing == 3


def test_a_spare_of_the_same_part_is_never_the_one_adjusted():
    """Rebrickable lists a spare as its own inventory row, so a set can hold the same part/colour
    twice. Only the build part is tracked; a lookup that picked the spare would write the found
    count onto a row excluded from every total, and hand the UI a part flagged as a spare."""
    set_repo = FakeSetRepository()
    set_repo.save(
        LegoSet(
            set_num="2260-1",
            name="Ice Dragon Attack",
            year=2011,
            theme_id=435,
            num_parts=6,
            image_path=None,
            last_synced_at="2024-01-01T00:00:00Z",
            parts=[
                # Spare first, which is the order the upstream inventory can arrive in.
                Part(
                    part_num="53451",
                    color_id=0,
                    color_name="Black",
                    name="Shell",
                    element_id=None,
                    quantity_required=1,
                    quantity_found=0,
                    is_spare=True,
                ),
                Part(
                    part_num="53451",
                    color_id=0,
                    color_name="Black",
                    name="Shell",
                    element_id=None,
                    quantity_required=6,
                    quantity_found=0,
                    is_spare=False,
                ),
            ],
        )
    )

    part, lego_set = AdjustSetPartFoundUseCase(set_repo, FakeMissingHistoryRepository()).execute(
        "2260-1", "53451", 0, found_delta=6
    )

    assert not part.is_spare
    assert (part.quantity_required, part.quantity_found) == (6, 6)
    assert lego_set.total_found == 6

    spare = next(p for p in lego_set.parts if p.is_spare)
    assert spare.quantity_found == 0


def test_raises_for_unknown_part():
    set_repo = FakeSetRepository()
    seed_set(set_repo)

    with pytest.raises(EntityNotFoundError):
        AdjustSetPartFoundUseCase(set_repo, FakeMissingHistoryRepository()).execute(
            "75192-1", "unknown", 0, found_delta=1
        )
