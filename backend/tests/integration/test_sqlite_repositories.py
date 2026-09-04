from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.entities import LegoSet, Minifig, MissingPartRecord, Part
from app.infrastructure.db.sqlite_minifig_instance_repository import (
    SqliteMinifigInstanceRepository,
)
from app.infrastructure.db.sqlite_minifig_repository import SqliteMinifigRepository
from app.infrastructure.db.sqlite_missing_history_repository import (
    SqliteMissingHistoryRepository,
)
from app.infrastructure.db.sqlite_set_repository import SqliteSetRepository


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    from app.infrastructure.db import (
        models,  # noqa: F401 — registers tables on SQLModel.metadata
    )

    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_set_repository_round_trip(session):
    repo = SqliteSetRepository(session)
    repo.save(
        LegoSet(
            set_num="75192-1",
            name="Millennium Falcon",
            year=2017,
            theme_id=1,
            num_parts=1,
            image_path="sets/75192-1.jpg",
            last_synced_at="2024-01-01T00:00:00Z",
            parts=[
                Part(
                    part_num="3001",
                    color_id=0,
                    color_name="Black",
                    name="Brick 2x4",
                    element_id=None,
                    quantity_required=4,
                )
            ],
        )
    )

    fetched = repo.get("75192-1")
    assert fetched is not None
    assert fetched.name == "Millennium Falcon"
    assert len(fetched.parts) == 1

    updated_part = repo.update_part_found("75192-1", "3001", 0, quantity_found=2)
    assert updated_part.quantity_found == 2
    assert repo.get_part("75192-1", "3001", 0).quantity_found == 2
    assert len(repo.list_all()) == 1

    conditioned_part = repo.update_part_condition(
        "75192-1", "3001", 0, quantity_found=2, quantity_broken=1
    )
    assert conditioned_part.quantity_broken == 1
    assert repo.get_part("75192-1", "3001", 0).quantity_broken == 1

    # Broken is a subset of found, so walking found back also clears an impossible condition count.
    repo.update_part_found("75192-1", "3001", 0, quantity_found=0)
    assert repo.get_part("75192-1", "3001", 0).quantity_broken == 0
    repo.update_part_found("75192-1", "3001", 0, quantity_found=2)

    # Two of four confirmed present, and sorting is unfinished, so nothing counts as missing yet.
    assert repo.get("75192-1").status == "sorting"
    assert repo.get("75192-1").total_missing == 0

    repo.set_sorting_finished("75192-1", datetime(2024, 1, 3, tzinfo=UTC))
    assert repo.get("75192-1").status == "sorted"
    assert repo.get("75192-1").total_missing == 2

    repo.set_sorting_finished("75192-1", None)
    assert repo.get("75192-1").status == "sorting"


def test_set_repository_save_preserves_found_on_resync(session):
    repo = SqliteSetRepository(session)
    part = Part(part_num="3001", color_id=0, color_name="Black", name="Brick 2x4", element_id=None, quantity_required=4)
    repo.save(LegoSet(set_num="75192-1", name="Falcon", num_parts=1, image_path=None, last_synced_at="2024-01-01T00:00:00Z", parts=[part]))
    repo.update_part_found("75192-1", "3001", 0, quantity_found=1)

    refreshed_part = part.model_copy(update={"quantity_required": 6})
    repo.save(LegoSet(set_num="75192-1", name="Falcon", num_parts=1, image_path=None, last_synced_at="2024-01-02T00:00:00Z", parts=[refreshed_part]))

    result = repo.get_part("75192-1", "3001", 0)
    assert result.quantity_required == 6
    assert result.quantity_found == 1


def test_set_repository_part_lookup_ignores_a_spare_of_the_same_part(session):
    """A set can list the same part/colour as both a build part and a spare. The lookup has to name
    the build row: picking either one at random puts the found count on an untracked row."""
    repo = SqliteSetRepository(session)
    spare = Part(
        part_num="53451", color_id=0, color_name="Black", name="Shell", element_id=None,
        quantity_required=1, is_spare=True,
    )
    build = spare.model_copy(update={"quantity_required": 6, "is_spare": False})
    # Spare first, so a lookup that ignored is_spare would land on it.
    repo.save(LegoSet(set_num="2260-1", name="Ice Dragon Attack", num_parts=7, image_path=None, last_synced_at="2024-01-01T00:00:00Z", parts=[spare, build]))

    found = repo.get_part("2260-1", "53451", 0)
    assert found.is_spare is False
    assert found.quantity_required == 6

    repo.update_part_found("2260-1", "53451", 0, quantity_found=6)

    stored = repo.get("2260-1")
    assert stored.total_found == 6
    assert next(p for p in stored.parts if p.is_spare).quantity_found == 0


def test_minifig_and_instance_repository_round_trip(session):
    minifig_repo = SqliteMinifigRepository(session)
    instance_repo = SqliteMinifigInstanceRepository(session)

    minifig_repo.save(
        Minifig(
            fig_num="sw0001",
            name="Luke Skywalker",
            num_parts=1,
            image_path="minifigs/sw0001.jpg",
            last_synced_at="2024-01-01T00:00:00Z",
            parts=[Part(part_num="3624", color_id=14, color_name="Yellow", name="Head", element_id=None, quantity_required=1)],
        )
    )
    minifig = minifig_repo.get("sw0001")
    assert minifig is not None

    instance_a = instance_repo.create("sw0001", minifig.name, minifig.image_path, "75192-1", minifig.parts)
    instance_b = instance_repo.create("sw0001", minifig.name, minifig.image_path, "10188-1", minifig.parts)

    assert instance_a.id != instance_b.id
    assert instance_repo.count_by_fig_and_set("sw0001", "75192-1") == 1

    instance_repo.update_part_found(instance_a.id, "3624", 14, quantity_found=1)
    assert instance_repo.get(instance_a.id).total_found == 1
    assert instance_repo.get(instance_b.id).total_found == 0  # independently tracked
    assert instance_repo.get(instance_a.id).status == "complete"
    assert instance_repo.get(instance_b.id).status == "not_started"


def test_missing_history_repository_append_and_query(session):
    history = SqliteMissingHistoryRepository(session)
    history.append(
        MissingPartRecord(
            entity_type="set",
            entity_id="75192-1",
            part_num="3001",
            color_id=0,
            action="marked_missing",
            quantity_before=0,
            quantity_after=1,
            timestamp="2024-01-01T00:00:00Z",
        )
    )

    assert history.exists_for_part("set", "75192-1", "3001", 0)
    records = history.list_for_entity("set", "75192-1")
    assert len(records) == 1
    assert records[0].action == "marked_missing"
