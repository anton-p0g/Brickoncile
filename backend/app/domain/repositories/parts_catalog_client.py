from typing import Protocol

from app.domain.repositories.dtos import (
    MinifigMetadataDTO,
    MinifigRosterEntryDTO,
    MinifigSearchResultDTO,
    PartDTO,
    SetMetadataDTO,
    ThemeDTO,
)


class PartsCatalogClient(Protocol):
    """Abstraction over the external parts-catalog source (Rebrickable in production)."""

    async def fetch_set_metadata(self, set_num: str) -> SetMetadataDTO: ...

    async def fetch_themes(self) -> list[ThemeDTO]:
        """The whole theme tree in one go. A few hundred rows that change only when LEGO launches a
        new line, so callers cache it rather than resolving themes set by set."""
        ...

    async def fetch_set_parts(self, set_num: str) -> list[PartDTO]: ...

    async def fetch_set_minifigs(self, set_num: str) -> list[MinifigRosterEntryDTO]: ...

    async def fetch_minifig_metadata(self, fig_num: str) -> MinifigMetadataDTO: ...

    async def fetch_minifig_parts(self, fig_num: str) -> list[PartDTO]: ...

    async def search_minifigs(self, query: str, limit: int) -> list[MinifigSearchResultDTO]:
        """Minifigs whose name matches every word in `query`. The all-words rule matters to callers:
        a longer query is strictly narrower, so widening a search means passing fewer words."""
        ...
