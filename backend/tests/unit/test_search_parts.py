from app.application.use_cases.search_parts import SearchPartsUseCase
from app.domain.entities import LegoSet, Part
from tests.unit.fakes import FakeMinifigInstanceRepository, FakeSetRepository


def part(part_num="3001", color_id=0, required=4, found=0, name="Brick 2x4", **overrides) -> Part:
    defaults = {
        "part_num": part_num,
        "color_id": color_id,
        "color_name": "Black" if color_id == 0 else "Red",
        "name": name,
        "element_id": "300126",
        "quantity_required": required,
        "quantity_found": found,
    }
    defaults.update(overrides)
    return Part(**defaults)


def seed(repo: FakeSetRepository, set_num: str, parts: list[Part], **overrides) -> None:
    defaults = {
        "set_num": set_num,
        "name": f"Set {set_num}",
        "num_parts": len(parts),
        "image_path": None,
        "last_synced_at": "2024-01-01T00:00:00Z",
        "parts": parts,
    }
    defaults.update(overrides)
    repo.save(LegoSet(**defaults))


def make_use_case(set_repo=None, instance_repo=None) -> SearchPartsUseCase:
    return SearchPartsUseCase(set_repo or FakeSetRepository(), instance_repo or FakeMinifigInstanceRepository())


def test_finds_every_set_that_still_wants_the_brick():
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part(required=2, found=0)])
    seed(set_repo, "2260-1", [part(required=4, found=1)])

    results = make_use_case(set_repo).execute("3001")

    assert len(results) == 1
    result = results[0]
    assert result.total_needed == 5
    assert {(s.source_id, s.quantity_unaccounted) for s in result.sources} == {("70202-1", 2), ("2260-1", 3)}


def test_same_part_in_two_colours_stays_two_results():
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part(color_id=0, required=2), part(color_id=4, required=7)])

    results = make_use_case(set_repo).execute("3001")

    assert [(r.color_id, r.total_needed) for r in results] == [(4, 7), (0, 2)]


def test_colour_filter_narrows_to_the_brick_in_hand():
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part(color_id=0, required=2), part(color_id=4, required=7)])

    results = make_use_case(set_repo).execute("3001", color_id=4)

    assert [r.color_id for r in results] == [4]


def test_matches_on_name_and_element_id_too():
    """Not every brick has a legible part number moulded into it."""
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part(name="Plate 1 x 2", element_id="302326")])

    assert make_use_case(set_repo).execute("plate 1 x 2")
    assert make_use_case(set_repo).execute("302326")
    assert make_use_case(set_repo).execute("PLATE") == make_use_case(set_repo).execute("plate")


def test_fully_found_parts_still_come_back_with_nothing_needed():
    """"Nothing needs this, put it in the spares bin" has to be distinguishable from "not yours"."""
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part(required=2, found=2)])

    results = make_use_case(set_repo).execute("3001")

    assert len(results) == 1
    assert results[0].total_needed == 0


def test_needed_bricks_are_ranked_above_accounted_for_ones():
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part("3001", required=2, found=2), part("3002", required=3, found=0)])

    results = make_use_case(set_repo).execute("300")

    assert [r.part_num for r in results] == ["3002", "3001"]


def test_an_exact_part_number_outranks_a_loose_match_that_needs_more():
    """A search for "4519" matches part 60176 too, whose element id is 4519225. The part actually
    numbered 4519 has to come first even when the other one is wanted more."""
    set_repo = FakeSetRepository()
    seed(
        set_repo,
        "70202-1",
        [
            part("60176", required=9, element_id="4519225"),
            part("4519", required=2, element_id="4211815"),
        ],
    )

    results = make_use_case(set_repo).execute("4519")

    assert [r.part_num for r in results] == ["4519", "60176"]


def test_a_part_number_prefix_outranks_an_unrelated_match():
    set_repo = FakeSetRepository()
    seed(
        set_repo,
        "70202-1",
        [part("99999", required=9, name="Brick 4519 lookalike"), part("45190", required=1, element_id=None)],
    )

    results = make_use_case(set_repo).execute("4519")

    assert [r.part_num for r in results] == ["45190", "99999"]


def test_spares_and_pruned_parts_are_not_offered():
    set_repo = FakeSetRepository()
    seed(
        set_repo,
        "70202-1",
        [part("3001", required=1, is_spare=True), part("3002", required=0), part("3003", required=2)],
    )

    results = make_use_case(set_repo).execute("300")

    assert [r.part_num for r in results] == ["3003"]


def test_minifig_instances_are_searched_alongside_sets():
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part(required=2)])
    instance_repo = FakeMinifigInstanceRepository()
    instance_repo.create(
        fig_num="fig-000272",
        fig_name="CHI Gorzan",
        image_path=None,
        source_set_num="70202-1",
        parts_template=[part(required=1)],
    )

    results = make_use_case(set_repo, instance_repo).execute("3001")

    assert results[0].total_needed == 3
    assert {s.source_type for s in results[0].sources} == {"set", "minifig_instance"}


def test_an_empty_query_returns_nothing():
    """This screen is driven by a brick in hand, not by browsing the whole collection."""
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part()])

    assert make_use_case(set_repo).execute("") == []
    assert make_use_case(set_repo).execute("   ") == []


def test_limit_caps_the_result_size():
    set_repo = FakeSetRepository()
    seed(set_repo, "70202-1", [part(f"300{i}", required=i + 1) for i in range(5)])

    assert len(make_use_case(set_repo).execute("300", limit=2)) == 2
