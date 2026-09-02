from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.application.use_cases.delete_minifig_instance import (
    DeleteMinifigInstanceUseCase,
)
from app.domain.entities import LegoSet, Minifig, MissingPartRecord, Part
from app.domain.errors import EntityNotFoundError, EntityOwnedBySetError
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigInstanceRepository,
    FakeMinifigRepository,
    FakeMissingHistoryRepository,
    FakeSetRepository,
)


@dataclass
class Repos:
    instances: FakeMinifigInstanceRepository
    minifigs: FakeMinifigRepository
    history: FakeMissingHistoryRepository
    sets: FakeSetRepository
    images: FakeImageCache

    def use_case(self) -> DeleteMinifigInstanceUseCase:
        return DeleteMinifigInstanceUseCase(self.instances, self.minifigs, self.history, self.sets)


def make_part(part_num: str, color_id: int, image_path: str | None) -> Part:
    return Part(
        part_num=part_num,
        color_id=color_id,
        color_name="Black",
        name="Brick",
        quantity_required=1,
        image_path=image_path,
    )


def make_minifig(fig_num: str, parts: list[Part], image_path: str | None) -> Minifig:
    return Minifig(
        fig_num=fig_num,
        name=f"Fig {fig_num}",
        image_path=image_path,
        last_synced_at=datetime.now(UTC),
        parts=parts,
    )


@pytest.fixture
def repos():
    """One owned set holding part 3001/0, so that image must survive any minifig deletion."""
    r = Repos(
        instances=FakeMinifigInstanceRepository(),
        minifigs=FakeMinifigRepository(),
        history=FakeMissingHistoryRepository(),
        sets=FakeSetRepository(),
        images=FakeImageCache(),
    )
    r.sets.save(
        LegoSet(
            set_num="75192-1",
            name="Falcon",
            num_parts=1,
            image_path="sets/75192-1.jpg",
            last_synced_at=datetime.now(UTC),
            parts=[make_part("3001", 0, "parts/3001_0.jpg")],
        )
    )
    return r


def add_loose(repos: Repos, fig_num: str, parts: list[Part], image_path: str | None = None):
    repos.minifigs.save(make_minifig(fig_num, parts, image_path))
    return repos.instances.create(fig_num, f"Fig {fig_num}", image_path, None, parts)


def test_delete_removes_a_loose_instance(repos):
    instance = add_loose(repos, "fig-003769", [])

    repos.use_case().execute(instance.id)

    assert repos.instances.get(instance.id) is None


def test_delete_purges_only_that_instances_history(repos):
    doomed = add_loose(repos, "fig-003769", [])
    survivor = add_loose(repos, "fig-000068", [])
    for entity_id in (doomed.id, survivor.id):
        repos.history.append(
            MissingPartRecord(
                entity_type="minifig_instance",
                entity_id=entity_id,
                part_num="3626",
                color_id=14,
                action="marked_missing",
                quantity_before=0,
                quantity_after=1,
                timestamp=datetime.now(UTC),
            )
        )

    repos.use_case().execute(doomed.id)

    assert {r.entity_id for r in repos.history.records} == {survivor.id}


def test_delete_unknown_instance_raises(repos):
    with pytest.raises(EntityNotFoundError):
        repos.use_case().execute("no-such-instance")


def test_delete_refuses_an_instance_that_came_from_a_set(repos):
    """The set's roster would recreate it on the next resync, so removing it here would not stick."""
    instance = repos.instances.create("fig-003769", "Sebulba", None, "75192-1", [])

    with pytest.raises(EntityOwnedBySetError):
        repos.use_case().execute(instance.id)

    assert repos.instances.get(instance.id) is not None


def test_delete_retains_images_for_the_shared_cross_collection_cache(repos):
    instance = add_loose(
        repos, "fig-003769", [make_part("3626", 14, "parts/3626_14.jpg")], "minifigs/fig-003769.jpg"
    )

    repos.use_case().execute(instance.id)

    assert repos.images.deleted == []


def test_delete_keeps_a_part_image_an_owned_set_still_uses(repos):
    instance = add_loose(repos, "fig-003769", [make_part("3001", 0, "parts/3001_0.jpg")])

    repos.use_case().execute(instance.id)

    assert "parts/3001_0.jpg" not in repos.images.deleted


def test_delete_keeps_everything_a_second_copy_still_references(repos):
    """Duplicates are allowed on purpose, so deleting one copy must leave the other whole."""
    parts = [make_part("3626", 14, "parts/3626_14.jpg")]
    first = add_loose(repos, "fig-003769", parts, "minifigs/fig-003769.jpg")
    second = repos.instances.create("fig-003769", "Sebulba", "minifigs/fig-003769.jpg", None, parts)

    repos.use_case().execute(first.id)

    assert repos.instances.get(second.id) is not None
    assert repos.minifigs.get("fig-003769") is not None
    assert repos.images.deleted == []


def test_delete_prunes_the_catalog_entry_once_the_last_copy_is_gone(repos):
    instance = add_loose(repos, "fig-003769", [], "minifigs/fig-003769.jpg")

    repos.use_case().execute(instance.id)

    assert repos.minifigs.get("fig-003769") is None


def test_delete_keeps_a_catalog_entry_still_owned_through_a_set(repos):
    """The same fig can be owned both loose and via a set; only the loose copy goes."""
    loose = add_loose(repos, "fig-003769", [], "minifigs/fig-003769.jpg")
    repos.instances.create("fig-003769", "Sebulba", "minifigs/fig-003769.jpg", "75192-1", [])

    repos.use_case().execute(loose.id)

    assert repos.minifigs.get("fig-003769") is not None
    assert "minifigs/fig-003769.jpg" not in repos.images.deleted


def test_delete_handles_an_instance_that_never_cached_an_image(repos):
    instance = add_loose(repos, "fig-003769", [make_part("3626", 14, None)], None)

    repos.use_case().execute(instance.id)

    assert repos.instances.get(instance.id) is None
    assert repos.images.deleted == []
