import pytest

from app.application.use_cases.identify_minifig import (
    IdentifyMinifigUseCase,
    build_queries,
)
from app.domain.entities import Part
from app.domain.errors import ImageRecognitionUnavailableError
from app.domain.repositories.dtos import (
    MinifigRecognitionDTO,
    MinifigSearchResultDTO,
    PartFoundUpdate,
)
from tests.unit.fakes import (
    FakeMinifigInstanceRepository,
    FakeMinifigRecognizer,
    FakePartsCatalogClient,
    make_part_dto,
)

PHOTO = b"jpeg-bytes"


def recognition(name: str, score: float = 0.9, **overrides) -> MinifigRecognitionDTO:
    defaults = {
        "external_id": "sim021",
        "name": name,
        "score": score,
        "image_url": "https://brickognize.example/sim021.webp",
        "reference_url": "https://www.bricklink.com/v2/catalog/catalogitem.page?M=sim021",
    }
    defaults.update(overrides)
    return MinifigRecognitionDTO(**defaults)


def search_result(fig_num: str, name: str) -> MinifigSearchResultDTO:
    return MinifigSearchResultDTO(
        fig_num=fig_num, name=name, num_parts=4, image_url=f"https://cdn.example/{fig_num}.jpg"
    )


def use_case(recognizer, catalog, instance_repo=None, set_names=None) -> IdentifyMinifigUseCase:
    return IdentifyMinifigUseCase(
        recognizer, catalog, instance_repo or FakeMinifigInstanceRepository(), set_names
    )


class TestBuildQueries:
    """The two catalogs word names differently, so these cover the narrowing that bridges them.
    Each expectation is a real Brickognize name checked against the live Rebrickable search."""

    def test_drops_parenthetical_and_falls_back_to_the_leading_segment(self):
        queries = build_queries("Chief Wiggum, The Simpsons, Series 1 (Minifigure Only without Stand)")

        assert "Chief Wiggum" in queries
        assert not any("(" in q for q in queries)

    def test_tries_the_full_name_before_narrowing(self):
        queries = build_queries("Harry Potter, Gryffindor Sweater")

        assert queries[0] == "Harry Potter, Gryffindor Sweater"

    def test_shortens_a_long_single_segment_from_the_right(self):
        queries = build_queries("Chief Wiggum with Dark Pink Frosting Splotches on Face and Shirt")

        assert queries.index("Chief Wiggum with") < queries.index("Chief Wiggum") < queries.index("Chief")

    def test_splits_on_the_dash_that_bricklink_puts_after_the_name(self):
        # The recogniser reports "Sebulba - Dark Bluish Gray, Movable Arms"; the catalog calls it
        # "Sebulba". Glue the dash together and the name proper is never searched on its own.
        queries = build_queries("Sebulba - Dark Bluish Gray, Movable Arms")

        assert queries[1] == "Sebulba"

    def test_searches_the_leading_segment_before_the_description(self):
        queries = build_queries("Han Solo - Light Nougat, Black Legs")

        assert queries.index("Han Solo") < queries.index("Light Nougat")

    def test_skips_a_single_word_too_short_to_narrow_anything(self):
        queries = build_queries("Mr Freeze - Dark Blue")

        assert "Mr" not in queries
        assert "Mr Freeze" in queries

    def test_skips_a_segment_that_is_only_a_generic_word(self):
        # "Female" alone matches hundreds of unrelated figures, so it is not worth a request.
        queries = build_queries("Female, Toy Store Worker (LEGO Logo on Reverse of Torso)")

        assert "Female" not in queries
        assert "Toy Store" in queries

    def test_respects_the_query_budget(self):
        queries = build_queries("Alpha, Bravo, Charlie, Delta, Echo, Foxtrot", limit=3)

        assert len(queries) == 3


async def test_returns_catalog_matches_for_a_recognised_photo():
    recognizer = FakeMinifigRecognizer([recognition("Chief Wiggum, The Simpsons, Series 1")])
    catalog = FakePartsCatalogClient(
        minifig_search={"Chief Wiggum": [search_result("fig-000068", "Chief Wiggum (CMF)")]}
    )

    result = await use_case(recognizer, catalog).execute(PHOTO, "photo.jpg")

    assert [m.fig_num for m in result.matches] == ["fig-000068"]
    assert result.matches[0].recognized_as == "Chief Wiggum, The Simpsons, Series 1"
    assert result.matches[0].reference_url is not None


async def test_widens_the_query_until_the_catalog_answers():
    recognizer = FakeMinifigRecognizer([recognition("Female, Toy Store Worker (LEGO Logo)")])
    catalog = FakePartsCatalogClient(
        minifig_search={"Toy Store": [search_result("fig-000001", "Toy Store Employee")]}
    )

    result = await use_case(recognizer, catalog).execute(PHOTO, "photo.jpg")

    assert [m.fig_num for m in result.matches] == ["fig-000001"]
    # Narrower queries were tried first and came back empty.
    assert catalog.search_queries.index("Toy Store") > 0


async def test_stops_searching_once_a_query_returns_results():
    recognizer = FakeMinifigRecognizer([recognition("Harry Potter, Gryffindor Sweater")])
    catalog = FakePartsCatalogClient(
        minifig_search={
            "Harry Potter, Gryffindor Sweater": [search_result("fig-000457", "Harry Potter, Gryffindor Sweater")],
            "Harry Potter": [search_result("fig-999999", "Harry Potter, Something Else")],
        }
    )

    result = await use_case(recognizer, catalog).execute(PHOTO, "photo.jpg")

    assert catalog.search_queries == ["Harry Potter, Gryffindor Sweater"]
    assert [m.fig_num for m in result.matches] == ["fig-000457"]


async def test_ranks_the_closer_name_first():
    recognizer = FakeMinifigRecognizer([recognition("Chief Wiggum")])
    catalog = FakePartsCatalogClient(
        minifig_search={
            "Chief Wiggum": [
                search_result("fig-111111", "Chief Wiggum with Dark Pink Frosting Splotches"),
                search_result("fig-000068", "Chief Wiggum"),
            ]
        }
    )

    result = await use_case(recognizer, catalog).execute(PHOTO, "photo.jpg")

    assert result.matches[0].fig_num == "fig-000068"


async def test_a_more_confident_recognition_outranks_a_less_confident_one():
    recognizer = FakeMinifigRecognizer(
        [recognition("Chief Wiggum", score=0.9), recognition("Ned Flanders", score=0.2)]
    )
    catalog = FakePartsCatalogClient(
        minifig_search={
            "Chief Wiggum": [search_result("fig-000068", "Chief Wiggum")],
            "Ned Flanders": [search_result("fig-000070", "Ned Flanders")],
        }
    )

    result = await use_case(recognizer, catalog).execute(PHOTO, "photo.jpg")

    assert [m.fig_num for m in result.matches] == ["fig-000068", "fig-000070"]


async def test_the_same_fig_from_two_recognitions_appears_once_at_its_best_score():
    recognizer = FakeMinifigRecognizer(
        [recognition("Chief Wiggum", score=0.9), recognition("Wiggum", score=0.3)]
    )
    catalog = FakePartsCatalogClient(
        minifig_search={
            "Chief Wiggum": [search_result("fig-000068", "Chief Wiggum")],
            "Wiggum": [search_result("fig-000068", "Chief Wiggum")],
        }
    )

    result = await use_case(recognizer, catalog).execute(PHOTO, "photo.jpg")

    assert [m.fig_num for m in result.matches] == ["fig-000068"]


async def test_flags_a_match_already_in_the_collection_with_its_source_set():
    instance_repo = FakeMinifigInstanceRepository()
    instance_repo.create(
        fig_num="fig-000068",
        fig_name="Chief Wiggum",
        image_path=None,
        source_set_num="71006-1",
        parts_template=[],
    )
    recognizer = FakeMinifigRecognizer([recognition("Chief Wiggum")])
    catalog = FakePartsCatalogClient(
        minifig_search={"Chief Wiggum": [search_result("fig-000068", "Chief Wiggum")]}
    )

    result = await use_case(
        recognizer, catalog, instance_repo, {"71006-1": "The Simpsons House"}
    ).execute(PHOTO, "photo.jpg")

    owned = result.matches[0].owned_instances
    assert len(owned) == 1
    assert owned[0].source_set_num == "71006-1"
    assert owned[0].source_set_name == "The Simpsons House"


async def test_a_loose_owned_instance_reports_no_source_set():
    instance_repo = FakeMinifigInstanceRepository()
    instance_repo.create(
        fig_num="fig-000068", fig_name="Chief Wiggum", image_path=None, source_set_num=None, parts_template=[]
    )
    recognizer = FakeMinifigRecognizer([recognition("Chief Wiggum")])
    catalog = FakePartsCatalogClient(
        minifig_search={"Chief Wiggum": [search_result("fig-000068", "Chief Wiggum")]}
    )

    result = await use_case(recognizer, catalog, instance_repo).execute(PHOTO, "photo.jpg")

    assert result.matches[0].owned_instances[0].source_set_num is None


async def test_owned_copies_report_whether_each_is_still_expected():
    """A set can list the same fig twice. Confirming one copy leaves the other unaccounted for, and
    the photographed figure has to be matchable to that remaining one specifically."""
    instance_repo = FakeMinifigInstanceRepository()
    parts = [
        Part(part_num="3626", color_id=14, color_name="Yellow", name="Head", quantity_required=1)
    ]
    done = instance_repo.create("fig-000068", "Chief Wiggum", None, "71006-1", parts)
    instance_repo.update_parts_found(
        done.id, [PartFoundUpdate(part_num="3626", color_id=14, quantity_found=1)]
    )
    still_expected = instance_repo.create("fig-000068", "Chief Wiggum", None, "71006-1", parts)

    recognizer = FakeMinifigRecognizer([recognition("Chief Wiggum")])
    catalog = FakePartsCatalogClient(
        minifig_search={"Chief Wiggum": [search_result("fig-000068", "Chief Wiggum")]}
    )

    result = await use_case(recognizer, catalog, instance_repo).execute(PHOTO, "photo.jpg")

    owned = result.matches[0].owned_instances
    # The copy still waiting to be found is listed first, because that is the one to claim.
    assert [o.instance_id for o in owned] == [still_expected.id, done.id]
    assert [o.is_complete for o in owned] == [False, True]
    assert owned[0].quantity_found_total == 0
    assert owned[1].quantity_found_total == 1


async def test_reports_recognitions_even_when_none_resolve_to_the_catalog():
    """The recogniser saw something; saying what it thought it saw beats an empty screen."""
    recognizer = FakeMinifigRecognizer([recognition("Some Obscure Figure")])

    result = await use_case(recognizer, FakePartsCatalogClient()).execute(PHOTO, "photo.jpg")

    assert result.matches == []
    assert [r.name for r in result.recognitions] == ["Some Obscure Figure"]


async def test_an_unrecognised_photo_returns_nothing_without_searching():
    catalog = FakePartsCatalogClient()

    result = await use_case(FakeMinifigRecognizer([]), catalog).execute(PHOTO, "photo.jpg")

    assert result.matches == []
    assert result.recognitions == []
    assert catalog.search_queries == []


async def test_propagates_a_recogniser_outage():
    with pytest.raises(ImageRecognitionUnavailableError):
        await use_case(FakeMinifigRecognizer(unavailable=True), FakePartsCatalogClient()).execute(
            PHOTO, "photo.jpg"
        )


async def test_identifying_does_not_change_the_collection():
    instance_repo = FakeMinifigInstanceRepository()
    recognizer = FakeMinifigRecognizer([recognition("Chief Wiggum")])
    catalog = FakePartsCatalogClient(
        minifig_search={"Chief Wiggum": [search_result("fig-000068", "Chief Wiggum")]},
        minifig_parts={"fig-000068": [make_part_dto()]},
    )

    await use_case(recognizer, catalog, instance_repo).execute(PHOTO, "photo.jpg")

    assert instance_repo.list_all() == []
