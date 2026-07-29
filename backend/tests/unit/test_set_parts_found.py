from app.application.use_cases.set_parts_found import SetPartsFoundUseCase
from app.domain.entities import LegoSet, Part
from app.domain.repositories.dtos import PartFoundUpdate
from tests.unit.fakes import (
    FakeMinifigInstanceRepository,
    FakeMissingHistoryRepository,
    FakeSetRepository,
)


def part(part_num: str, color_id: int = 0, required: int = 4, found: int = 0, is_spare: bool = False) -> Part:
    return Part(
        part_num=part_num,
        color_id=color_id,
        color_name="Black",
        name=f"Brick {part_num}",
        element_id=None,
        quantity_required=required,
        quantity_found=found,
        is_spare=is_spare,
    )


def seed(repo: FakeSetRepository, parts: list[Part]) -> None:
    repo.save(
        LegoSet(
            set_num="75192-1",
            name="Falcon",
            num_parts=len(parts),
            image_path=None,
            last_synced_at="2024-01-01T00:00:00Z",
            parts=parts,
        )
    )


def make_use_case(set_repo, history):
    return SetPartsFoundUseCase(set_repo, FakeMinifigInstanceRepository(), history)


def test_confirms_every_requested_part_in_one_call():
    set_repo = FakeSetRepository()
    seed(set_repo, [part("3001", required=4), part("3020", color_id=15, required=2)])
    history = FakeMissingHistoryRepository()

    written, lego_set = make_use_case(set_repo, history).execute(
        "set",
        "75192-1",
        [
            PartFoundUpdate(part_num="3001", color_id=0, quantity_found=4),
            PartFoundUpdate(part_num="3020", color_id=15, quantity_found=2),
        ],
    )

    assert len(written) == 2
    assert all(p.is_fully_found for p in written)
    assert lego_set.total_found == 6
    assert len(history.records) == 2
    assert {r.action for r in history.records} == {"marked_found"}


def test_absolute_counts_let_the_same_call_undo_a_confirm():
    """Undo sends the previous counts back, which is why targets are absolute rather than deltas."""
    set_repo = FakeSetRepository()
    seed(set_repo, [part("3001", required=4, found=1)])
    use_case = make_use_case(set_repo, FakeMissingHistoryRepository())

    use_case.execute("set", "75192-1", [PartFoundUpdate(part_num="3001", color_id=0, quantity_found=4)])
    _, lego_set = use_case.execute(
        "set", "75192-1", [PartFoundUpdate(part_num="3001", color_id=0, quantity_found=1)]
    )

    assert lego_set.total_found == 1


def test_parts_already_at_the_target_are_not_rewritten_or_logged():
    """Confirming a screen where most parts are already done should not flood the audit log."""
    set_repo = FakeSetRepository()
    seed(set_repo, [part("3001", required=4, found=4), part("3020", color_id=15, required=2)])
    history = FakeMissingHistoryRepository()

    written, _ = make_use_case(set_repo, history).execute(
        "set",
        "75192-1",
        [
            PartFoundUpdate(part_num="3001", color_id=0, quantity_found=4),
            PartFoundUpdate(part_num="3020", color_id=15, quantity_found=2),
        ],
    )

    assert [p.part_num for p in written] == ["3020"]
    assert len(history.records) == 1


def test_clamps_to_quantity_required():
    set_repo = FakeSetRepository()
    seed(set_repo, [part("3001", required=4)])

    written, _ = make_use_case(set_repo, FakeMissingHistoryRepository()).execute(
        "set", "75192-1", [PartFoundUpdate(part_num="3001", color_id=0, quantity_found=99)]
    )

    assert written[0].quantity_found == 4


def test_unknown_parts_are_skipped_rather_than_failing_the_batch():
    """A stale client should not be able to abort an otherwise valid bulk confirm."""
    set_repo = FakeSetRepository()
    seed(set_repo, [part("3001", required=4)])

    written, lego_set = make_use_case(set_repo, FakeMissingHistoryRepository()).execute(
        "set",
        "75192-1",
        [
            PartFoundUpdate(part_num="gone", color_id=0, quantity_found=1),
            PartFoundUpdate(part_num="3001", color_id=0, quantity_found=4),
        ],
    )

    assert [p.part_num for p in written] == ["3001"]
    assert lego_set.total_found == 4


def test_a_spare_is_never_confirmed_by_the_bulk_call():
    """Same identity rule as a single tap: only the tracked build part is addressable."""
    set_repo = FakeSetRepository()
    seed(set_repo, [part("53451", required=1, is_spare=True), part("53451", required=6)])

    written, lego_set = make_use_case(set_repo, FakeMissingHistoryRepository()).execute(
        "set", "75192-1", [PartFoundUpdate(part_num="53451", color_id=0, quantity_found=6)]
    )

    assert len(written) == 1
    assert written[0].is_spare is False
    assert next(p for p in lego_set.parts if p.is_spare).quantity_found == 0
