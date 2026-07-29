from pydantic import BaseModel


class Theme(BaseModel):
    """A Rebrickable theme, e.g. "Star Wars" or one of its sub-themes like "Ultimate Collector Series".

    Themes form a forest: `parent_id` is None only at a root. A set's own `theme_id` usually points
    at a sub-theme, so grouping a collection the way an owner thinks about it ("my Star Wars sets")
    means resolving each set up to its root theme.
    """

    id: int
    parent_id: int | None = None
    name: str


def resolve_root(theme_id: int | None, themes: dict[int, Theme]) -> Theme | None:
    """Walk up to the root theme. Returns None when the id is unknown, which happens when the theme
    cache predates a set, and falls back to the deepest theme still resolvable if a parent is
    missing. The visited set guards against a cycle in upstream data rather than trusting it."""
    if theme_id is None:
        return None

    current = themes.get(theme_id)
    if current is None:
        return None

    visited = {current.id}
    while current.parent_id is not None:
        parent = themes.get(current.parent_id)
        if parent is None or parent.id in visited:
            break
        visited.add(parent.id)
        current = parent
    return current
