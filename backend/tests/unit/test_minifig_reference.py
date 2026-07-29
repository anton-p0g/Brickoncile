import pytest

from app.application.minifig_reference import parse_minifig_reference


@pytest.mark.parametrize(
    "raw",
    [
        "https://rebrickable.com/minifigs/fig-000068/chief-wiggum/",
        "https://rebrickable.com/minifigs/fig-000068/",
        "rebrickable.com/minifigs/fig-000068",
        "fig-000068",
        "FIG-000068",
        "  fig-000068  ",
    ],
)
def test_reads_a_rebrickable_fig_id_however_it_was_copied(raw):
    reference = parse_minifig_reference(raw)

    assert reference.kind == "rebrickable"
    assert reference.value == "fig-000068"


@pytest.mark.parametrize("raw", ["fig-68", "68", "000068"])
def test_pads_a_short_fig_id_to_the_width_the_catalog_uses(raw):
    assert parse_minifig_reference(raw).value == "fig-000068"


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.bricklink.com/v2/catalog/catalogitem.page?M=sw0001",
        "https://www.bricklink.com/v2/catalog/catalogitem.page?M=sw0001#T=C",
        "https://www.bricklink.com/catalogItem.asp?M=sw0001",
        "sw0001",
        "cty0123",
    ],
)
def test_recognises_a_bricklink_id_without_pretending_to_convert_it(raw):
    """Naming the kind is the point: the caller can say why it cannot be looked up."""
    reference = parse_minifig_reference(raw)

    assert reference.kind == "bricklink"
    assert reference.value in {"sw0001", "cty0123"}


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "Chief Wiggum",
        "https://example.com/some/page",
        "https://rebrickable.com/sets/75192-1/millennium-falcon/",
    ],
)
def test_anything_without_an_id_in_it_is_left_unrecognised(raw):
    """Better to say it could not be read than to guess and file the wrong figure."""
    assert parse_minifig_reference(raw).kind == "unrecognised"


def test_the_raw_input_is_kept_for_reporting_back():
    reference = parse_minifig_reference("  https://rebrickable.com/minifigs/fig-000068/  ")

    assert reference.raw == "  https://rebrickable.com/minifigs/fig-000068/  "
