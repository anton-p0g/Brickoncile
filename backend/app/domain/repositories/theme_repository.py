from typing import Protocol

from app.domain.entities import Theme


class ThemeRepository(Protocol):
    """Local cache of the upstream theme tree. Small (a few hundred rows) and near-static, so it is
    fetched wholesale rather than per-set."""

    def list_all(self) -> list[Theme]: ...

    def get_by_id(self) -> dict[int, Theme]:
        """Every cached theme keyed by id, ready for `resolve_root`."""
        ...

    def upsert_many(self, themes: list[Theme]) -> None: ...

    def count(self) -> int: ...
