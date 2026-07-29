import pytest

from app.application.use_cases.add_loose_minifig import AddLooseMinifigUseCase
from app.application.use_cases.add_minifig_by_reference import (
    AddMinifigByReferenceUseCase,
)
from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.domain.errors import (
    PartsCatalogNotFoundError,
    UnresolvableMinifigReferenceError,
)
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigInstanceRepository,
    FakeMinifigRepository,
    FakePartsCatalogClient,
    make_minifig_metadata_dto,
    make_part_dto,
)


@pytest.fixture
def world():
    instances = FakeMinifigInstanceRepository()
    catalog = FakePartsCatalogClient(
        minifigs={"fig-000068": make_minifig_metadata_dto("fig-000068", name="Chief Wiggum")},
        minifig_parts={"fig-000068": [make_part_dto("3626", 14, part_name="Head")]},
    )
    fetch_minifig = FetchMinifigUseCase(FakeMinifigRepository(), catalog, FakeImageCache())
    return instances, AddMinifigByReferenceUseCase(instances, AddLooseMinifigUseCase(instances, fetch_minifig))


@pytest.mark.parametrize(
    "reference",
    ["https://rebrickable.com/minifigs/fig-000068/chief-wiggum/", "fig-000068", "fig-68", "68"],
)
async def test_adds_the_figure_a_rebrickable_reference_names(world, reference):
    instances, use_case = world

    result = await use_case.execute(reference)

    assert result.instance.fig_num == "fig-000068"
    assert result.instance.fig_name == "Chief Wiggum"
    assert result.instance.source_set_num is None
    assert len(instances.list_all()) == 1


async def test_reports_how_many_copies_were_already_owned(world):
    """A list pasted twice is the case worth catching; a second copy is still allowed."""
    instances, use_case = world
    await use_case.execute("fig-000068")

    result = await use_case.execute("fig-000068")

    assert result.already_owned_count == 1
    assert len(instances.list_all()) == 2


async def test_the_first_copy_reports_none_already_owned(world):
    _, use_case = world

    assert (await use_case.execute("fig-000068")).already_owned_count == 0


async def test_a_bricklink_reference_explains_why_it_cannot_be_looked_up(world):
    instances, use_case = world

    with pytest.raises(UnresolvableMinifigReferenceError, match="BrickLink"):
        await use_case.execute("https://www.bricklink.com/v2/catalog/catalogitem.page?M=sw0001")

    assert instances.list_all() == []


async def test_text_with_no_id_in_it_is_refused_before_anything_is_fetched(world):
    instances, use_case = world

    with pytest.raises(UnresolvableMinifigReferenceError):
        await use_case.execute("Chief Wiggum")

    assert instances.list_all() == []


async def test_a_well_formed_id_the_catalog_does_not_have_still_reaches_the_catalog(world):
    """This one is a lookup failure rather than a bad reference, and reports as one."""
    _, use_case = world

    with pytest.raises(PartsCatalogNotFoundError):
        await use_case.execute("fig-999999")
