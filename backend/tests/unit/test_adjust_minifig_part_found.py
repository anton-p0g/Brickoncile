import pytest

from app.application.use_cases.adjust_minifig_part_found import (
    AdjustMinifigPartFoundUseCase,
)
from app.domain.entities import Part
from app.domain.errors import EntityNotFoundError
from tests.unit.fakes import FakeMinifigInstanceRepository, FakeMissingHistoryRepository


def seed_instance(repo: FakeMinifigInstanceRepository, quantity_required=1) -> str:
    instance = repo.create(
        fig_num="sw0001",
        fig_name="Luke Skywalker",
        image_path=None,
        source_set_num="75192-1",
        parts_template=[
            Part(
                part_num="3624",
                color_id=14,
                color_name="Yellow",
                name="Head",
                element_id=None,
                quantity_required=quantity_required,
            )
        ],
    )
    return instance.id


def test_finding_a_piece_increments_and_records_history():
    instance_repo = FakeMinifigInstanceRepository()
    instance_id = seed_instance(instance_repo)
    history = FakeMissingHistoryRepository()

    part, instance = AdjustMinifigPartFoundUseCase(instance_repo, history).execute(
        instance_id, "3624", 14, found_delta=1
    )

    assert part.quantity_found == 1
    assert instance.status == "complete"
    assert history.records[0].entity_type == "minifig_instance"
    assert history.records[0].entity_id == instance_id
    assert history.records[0].action == "marked_found"


def test_clamps_at_zero():
    instance_repo = FakeMinifigInstanceRepository()
    instance_id = seed_instance(instance_repo)

    part, _ = AdjustMinifigPartFoundUseCase(instance_repo, FakeMissingHistoryRepository()).execute(
        instance_id, "3624", 14, found_delta=-1
    )

    assert part.quantity_found == 0


def test_a_new_instance_starts_not_started():
    instance_repo = FakeMinifigInstanceRepository()
    instance_id = seed_instance(instance_repo)

    assert instance_repo.get(instance_id).status == "not_started"


def test_two_instances_of_same_fig_track_independently():
    instance_repo = FakeMinifigInstanceRepository()
    id_a = seed_instance(instance_repo)
    id_b = seed_instance(instance_repo)

    AdjustMinifigPartFoundUseCase(instance_repo, FakeMissingHistoryRepository()).execute(
        id_a, "3624", 14, found_delta=1
    )

    assert instance_repo.get(id_a).total_found == 1
    assert instance_repo.get(id_b).total_found == 0


def test_unfound_minifig_pieces_only_count_as_missing_once_sorted():
    instance_repo = FakeMinifigInstanceRepository()
    instance_id = seed_instance(instance_repo, quantity_required=2)

    assert instance_repo.get(instance_id).total_missing == 0

    instance_repo.set_sorting_finished(instance_id, "2024-01-02T00:00:00Z")
    assert instance_repo.get(instance_id).total_missing == 2


def test_raises_for_unknown_instance():
    instance_repo = FakeMinifigInstanceRepository()

    with pytest.raises(EntityNotFoundError):
        AdjustMinifigPartFoundUseCase(instance_repo, FakeMissingHistoryRepository()).execute(
            "does-not-exist", "3624", 14, found_delta=1
        )
