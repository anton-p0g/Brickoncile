from app.application.use_cases.get_missing_summary import GetMissingSummaryUseCase
from app.domain.entities import LegoSet, Part
from tests.unit.fakes import FakeMinifigInstanceRepository, FakeSetRepository

SORTED_AT = "2024-01-02T00:00:00Z"


def make_part(part_num, color_id, missing, quantity_required=4, is_spare=False):
    """`missing` is expressed the way the shopping list thinks about it; storage tracks found."""
    return Part(
        part_num=part_num,
        color_id=color_id,
        color_name="Black",
        name="Brick 2x4",
        element_id=None,
        quantity_required=quantity_required,
        quantity_found=quantity_required - missing,
        is_spare=is_spare,
    )


def make_set(set_num, parts, sorting_finished_at=SORTED_AT, name=None, image_path=None):
    """`name` defaults to the set number; pass a distinct one when the difference is the point."""
    return LegoSet(
        set_num=set_num,
        name=name if name is not None else set_num,
        num_parts=len(parts),
        image_path=image_path,
        last_synced_at="2024-01-01T00:00:00Z",
        sorting_finished_at=sorting_finished_at,
        parts=parts,
    )


def test_group_by_part_aggregates_across_sets():
    set_repo = FakeSetRepository()
    set_repo.save(make_set("75192-1", [make_part("3020", 15, missing=2)]))
    set_repo.save(make_set("21034-1", [make_part("3020", 15, missing=3)]))

    result = GetMissingSummaryUseCase(set_repo, FakeMinifigInstanceRepository()).execute(group_by="part")

    assert len(result) == 1
    assert result[0].total_missing == 5
    assert {c.source_id for c in result[0].contributors} == {"75192-1", "21034-1"}


def test_group_by_set_returns_one_bucket_per_source():
    set_repo = FakeSetRepository()
    set_repo.save(make_set("75192-1", [make_part("3020", 15, missing=2), make_part("3001", 0, missing=1)]))

    result = GetMissingSummaryUseCase(set_repo, FakeMinifigInstanceRepository()).execute(group_by="set")

    assert len(result) == 1
    assert result[0].source_id == "75192-1"
    assert result[0].total_missing == 3
    assert len(result[0].items) == 2


def test_excludes_fully_found_parts_and_spares():
    set_repo = FakeSetRepository()
    set_repo.save(
        make_set("75192-1", [make_part("3020", 15, missing=0), make_part("9999", 0, missing=1, is_spare=True)])
    )

    result = GetMissingSummaryUseCase(set_repo, FakeMinifigInstanceRepository()).execute(group_by="part")

    assert result == []


def test_sets_still_being_sorted_are_excluded_entirely():
    """Unfound pieces in an unfinished set may still be in the pile, so ordering them would be
    wrong. They appear only once the owner declares sorting finished."""
    set_repo = FakeSetRepository()
    set_repo.save(make_set("75192-1", [make_part("3020", 15, missing=2)], sorting_finished_at=None))
    use_case = GetMissingSummaryUseCase(set_repo, FakeMinifigInstanceRepository())

    assert use_case.execute(group_by="part") == []
    assert use_case.execute(group_by="set") == []

    set_repo.set_sorting_finished("75192-1", SORTED_AT)

    result = use_case.execute(group_by="part")
    assert len(result) == 1
    assert result[0].total_missing == 2


def test_contributors_carry_name_reference_and_image_separately():
    """A caller laying these out as cards needs the three apart: the label alone cannot be split."""
    set_repo = FakeSetRepository()
    set_repo.save(
        make_set(
            "75192-1",
            [make_part("3020", 15, missing=2)],
            name="Millennium Falcon",
            image_path="sets/75192-1.jpg",
        )
    )

    by_part = GetMissingSummaryUseCase(set_repo, FakeMinifigInstanceRepository()).execute(group_by="part")
    contributor = by_part[0].contributors[0]
    assert contributor.name == "Millennium Falcon"
    assert contributor.reference == "75192-1"
    assert contributor.image_path == "sets/75192-1.jpg"

    by_set = GetMissingSummaryUseCase(set_repo, FakeMinifigInstanceRepository()).execute(group_by="set")
    assert by_set[0].name == "Millennium Falcon"
    assert by_set[0].reference == "75192-1"


def test_minifig_reference_is_the_fig_num_not_the_instance_id():
    """source_id is an internal instance id and means nothing to the owner, so a UI that showed it
    would print a UUID where the fig number belongs. reference is what carries that."""
    instance_repo = FakeMinifigInstanceRepository()
    instance = instance_repo.create(
        fig_num="sw0001",
        fig_name="Luke Skywalker",
        image_path="minifigs/sw0001.jpg",
        source_set_num="75192-1",
        parts_template=[make_part("3624", 14, missing=1, quantity_required=1)],
    )
    instance_repo.set_sorting_finished(instance.id, SORTED_AT)

    contributor = (
        GetMissingSummaryUseCase(FakeSetRepository(), instance_repo).execute(group_by="part")[0].contributors[0]
    )

    assert contributor.source_id == instance.id
    assert contributor.reference == "sw0001"
    assert contributor.name == "Luke Skywalker"
    assert contributor.image_path == "minifigs/sw0001.jpg"
    assert contributor.source_id != contributor.reference


def test_minifig_instances_contribute_once_sorted():
    instance_repo = FakeMinifigInstanceRepository()
    instance = instance_repo.create(
        fig_num="sw0001",
        fig_name="Luke Skywalker",
        image_path=None,
        source_set_num="75192-1",
        parts_template=[make_part("3624", 14, missing=0, quantity_required=1)],
    )
    instance_repo.update_part_found(instance.id, "3624", 14, quantity_found=0)
    use_case = GetMissingSummaryUseCase(FakeSetRepository(), instance_repo)

    assert use_case.execute(group_by="part") == []

    instance_repo.set_sorting_finished(instance.id, SORTED_AT)

    result = use_case.execute(group_by="part")
    assert len(result) == 1
    assert result[0].contributors[0].source_type == "minifig_instance"
