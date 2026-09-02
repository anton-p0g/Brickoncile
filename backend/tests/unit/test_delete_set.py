from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.application.use_cases.delete_set import DeleteSetUseCase
from app.domain.entities import LegoSet, Minifig, MissingPartRecord, Part
from app.domain.errors import EntityNotFoundError
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigInstanceRepository,
    FakeMinifigRepository,
    FakeMissingHistoryRepository,
    FakeSetRepository,
)


@dataclass
class Repos:
    sets: FakeSetRepository
    instances: FakeMinifigInstanceRepository
    minifigs: FakeMinifigRepository
    history: FakeMissingHistoryRepository
    images: FakeImageCache

    def use_case(self) -> DeleteSetUseCase:
        return DeleteSetUseCase(self.sets, self.instances, self.minifigs, self.history)


def make_history(entity_type: str, entity_id: str) -> MissingPartRecord:
    return MissingPartRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        part_num="3001",
        color_id=0,
        action="marked_missing",
        quantity_before=0,
        quantity_after=1,
        timestamp=datetime.now(UTC),
    )


def make_part(part_num: str, color_id: int, image_path: str | None) -> Part:
    return Part(
        part_num=part_num,
        color_id=color_id,
        color_name="Black",
        name="Brick",
        quantity_required=4,
        image_path=image_path,
    )


def make_set(set_num: str, parts: list[Part], image_path: str | None) -> LegoSet:
    return LegoSet(
        set_num=set_num,
        name=f"Set {set_num}",
        num_parts=len(parts),
        image_path=image_path,
        last_synced_at=datetime.now(UTC),
        parts=parts,
    )


@pytest.fixture
def repos():
    """Two sets that share part 3001/0, so its image must survive deleting either one."""
    r = Repos(
        sets=FakeSetRepository(),
        instances=FakeMinifigInstanceRepository(),
        minifigs=FakeMinifigRepository(),
        history=FakeMissingHistoryRepository(),
        images=FakeImageCache(),
    )
    r.sets.save(
        make_set(
            "75192-1",
            [make_part("3001", 0, "parts/3001_0.jpg"), make_part("9999", 5, "parts/9999_5.jpg")],
            "sets/75192-1.jpg",
        )
    )
    r.sets.save(make_set("21034-1", [make_part("3001", 0, "parts/3001_0.jpg")], "sets/21034-1.jpg"))
    return r


def test_delete_removes_set_and_its_minifig_instances(repos):
    doomed = repos.instances.create("sw0001", "Luke", None, "75192-1", [])
    survivor = repos.instances.create("sw0002", "Han", None, "21034-1", [])

    repos.use_case().execute("75192-1")

    assert repos.sets.get("75192-1") is None
    assert repos.instances.get(doomed.id) is None
    # Another set's instances are untouched.
    assert repos.sets.get("21034-1") is not None
    assert repos.instances.get(survivor.id) is not None


def test_delete_purges_history_for_set_and_its_instances_only(repos):
    doomed = repos.instances.create("sw0001", "Luke", None, "75192-1", [])
    survivor = repos.instances.create("sw0002", "Han", None, "21034-1", [])
    for record in (
        make_history("set", "75192-1"),
        make_history("minifig_instance", doomed.id),
        make_history("set", "21034-1"),
        make_history("minifig_instance", survivor.id),
    ):
        repos.history.append(record)

    repos.use_case().execute("75192-1")

    remaining = {(r.entity_type, r.entity_id) for r in repos.history.records}
    assert remaining == {("set", "21034-1"), ("minifig_instance", survivor.id)}


def test_delete_unknown_set_raises(repos):
    with pytest.raises(EntityNotFoundError):
        repos.use_case().execute("does-not-exist-1")


def test_delete_is_idempotent_after_the_set_is_gone(repos):
    use_case = repos.use_case()
    use_case.execute("75192-1")

    with pytest.raises(EntityNotFoundError):
        use_case.execute("75192-1")


def test_delete_leaves_other_instances_of_the_same_fig_from_another_set(repos):
    """Two sets can contribute the same fig_num; deleting one set must not take the other's copy."""
    from_doomed = repos.instances.create("sw0001", "Luke", None, "75192-1", [])
    from_survivor = repos.instances.create("sw0001", "Luke", None, "21034-1", [])

    repos.use_case().execute("75192-1")

    assert [i.id for i in repos.instances.list_by_fig_num("sw0001")] == [from_survivor.id]
    assert repos.instances.get(from_doomed.id) is None


# ---- shared image cache ----


def test_delete_retains_images_for_the_shared_cross_collection_cache(repos):
    repos.use_case().execute("75192-1")

    assert repos.images.deleted == []


def test_delete_keeps_part_images_another_set_still_uses(repos):
    """part 3001/0 belongs to both sets; its image is keyed by part+colour, not by set."""
    repos.use_case().execute("75192-1")

    assert "parts/3001_0.jpg" not in repos.images.deleted
    assert "sets/21034-1.jpg" not in repos.images.deleted
    # The surviving set can still render it.
    assert "parts/3001_0.jpg" in repos.sets.list_referenced_image_paths()


def test_delete_prunes_orphaned_minifig_catalog_and_its_images(repos):
    repos.minifigs.save(
        Minifig(
            fig_num="sw0001",
            name="Luke",
            image_path="minifigs/sw0001.jpg",
            last_synced_at=datetime.now(UTC),
            parts=[make_part("3626", 14, "parts/3626_14.jpg")],
        )
    )
    repos.instances.create("sw0001", "Luke", "minifigs/sw0001.jpg", "75192-1", [])

    repos.use_case().execute("75192-1")

    assert repos.minifigs.get("sw0001") is None
    assert repos.images.deleted == []


def test_delete_keeps_minifig_catalog_still_owned_through_another_set(repos):
    repos.minifigs.save(
        Minifig(
            fig_num="sw0001",
            name="Luke",
            image_path="minifigs/sw0001.jpg",
            last_synced_at=datetime.now(UTC),
            parts=[make_part("3626", 14, "parts/3626_14.jpg")],
        )
    )
    repos.instances.create("sw0001", "Luke", "minifigs/sw0001.jpg", "75192-1", [])
    repos.instances.create("sw0001", "Luke", "minifigs/sw0001.jpg", "21034-1", [])

    repos.use_case().execute("75192-1")

    assert repos.minifigs.get("sw0001") is not None
    assert "minifigs/sw0001.jpg" not in repos.images.deleted
    assert "parts/3626_14.jpg" not in repos.images.deleted


def test_delete_handles_entities_that_never_cached_an_image(repos):
    repos.sets.save(make_set("6666-1", [make_part("1111", 0, None)], None))

    repos.use_case().execute("6666-1")

    assert repos.sets.get("6666-1") is None
    # No empty-string or None path is ever handed to the cache.
    assert all(path for path in repos.images.deleted)


def test_minifig_instance_carries_an_added_at_timestamp(repos):
    before = datetime.now(UTC)
    instance = repos.instances.create("sw0001", "Luke", None, "75192-1", [])
    assert instance.added_at >= before
