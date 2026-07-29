import re
from typing import Literal

from pydantic import BaseModel

ReferenceKind = Literal["rebrickable", "bricklink", "unrecognised"]

_REBRICKABLE_FIG = re.compile(r"fig-(\d{1,6})\b", re.IGNORECASE)
"""Rebrickable's own minifig id, as it appears bare or inside one of its URLs."""

_BRICKLINK_QUERY = re.compile(r"[?&]M=([A-Za-z]{1,4}\d{1,5}[a-z]?)\b")
"""BrickLink links carry the item in a query parameter: catalogitem.page?M=sw0001. Both the modern
and the legacy catalogItem.asp form use it, so matching the parameter covers both."""

_BRICKLINK_ID = re.compile(r"^[A-Za-z]{1,4}\d{1,5}[a-z]?$")
"""A BrickLink minifig id typed on its own: a short theme prefix and a number, "sw0001", "cty0123",
sometimes with a variant letter. The leading letters are what separate it from a Rebrickable id,
which is digits throughout."""

_BARE_NUMBER = re.compile(r"^\d{1,6}$")


class MinifigReference(BaseModel):
    """What a pasted line turned out to be.

    `value` is normalized for `rebrickable` — the zero-padded `fig-000068` the catalog answers to,
    whatever width was typed. For the other kinds it is whatever was recognised, kept so a message
    about it can quote the id rather than the whole pasted line.
    """

    kind: ReferenceKind
    value: str
    raw: str


def parse_minifig_reference(raw: str) -> MinifigReference:
    """Read a pasted minifig identifier: a Rebrickable link or fig id, or a BrickLink link or id.

    Rebrickable is checked first and by pattern rather than by host, so a fig id copied out of any
    page — a forum post, a search result, the address bar — reads the same as one typed by hand.

    A BrickLink id is recognised but deliberately not converted here. The two catalogs number
    minifigs independently and Rebrickable publishes no mapping between them, which is the same
    wall `IdentifyMinifigUseCase` runs into; naming the kind is what lets the caller say so
    precisely instead of reporting a fig id that was never valid.
    """
    text = raw.strip()
    if not text:
        return MinifigReference(kind="unrecognised", value="", raw=raw)

    fig = _REBRICKABLE_FIG.search(text)
    if fig:
        return MinifigReference(kind="rebrickable", value=_normalize_fig_num(fig.group(1)), raw=raw)

    query = _BRICKLINK_QUERY.search(text)
    if query:
        return MinifigReference(kind="bricklink", value=query.group(1), raw=raw)

    # Bare identifiers only past this point: anything still holding a slash or a space is a URL
    # that matched nothing above, or prose, and guessing at it would add the wrong figure.
    if "/" in text or " " in text:
        return MinifigReference(kind="unrecognised", value=text, raw=raw)

    if _BARE_NUMBER.match(text):
        return MinifigReference(kind="rebrickable", value=_normalize_fig_num(text), raw=raw)
    if _BRICKLINK_ID.match(text):
        return MinifigReference(kind="bricklink", value=text, raw=raw)
    return MinifigReference(kind="unrecognised", value=text, raw=raw)


def _normalize_fig_num(digits: str) -> str:
    """Rebrickable pads its minifig ids to six digits, so `fig-68` and `68` both mean fig-000068."""
    return f"fig-{int(digits):06d}"
