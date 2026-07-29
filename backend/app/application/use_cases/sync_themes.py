from app.domain.entities import Theme
from app.domain.repositories import PartsCatalogClient, ThemeRepository


class SyncThemesUseCase:
    """Refresh the local copy of the upstream theme tree.

    The whole tree is one request and a few hundred rows, so it is pulled wholesale rather than a
    theme at a time. It only changes when LEGO launches a new line, which is why `ensure_populated`
    is the normal entry point: it does nothing once the cache exists.
    """

    def __init__(self, theme_repo: ThemeRepository, catalog: PartsCatalogClient):
        self.theme_repo = theme_repo
        self.catalog = catalog

    async def execute(self) -> list[Theme]:
        dtos = await self.catalog.fetch_themes()
        themes = [Theme(id=d.id, parent_id=d.parent_id, name=d.name) for d in dtos]
        self.theme_repo.upsert_many(themes)
        return themes

    async def ensure_populated(self) -> None:
        """Fetch only when nothing is cached yet, so startup and adding a set stay offline-friendly
        once the tree has been pulled once."""
        if self.theme_repo.count() > 0:
            return
        await self.execute()

    async def ensure_known(self, theme_id: int | None) -> None:
        """Refresh when a set arrives carrying a theme the cache has never seen, which is how a
        theme added upstream since the last sync gets picked up."""
        if theme_id is None:
            return
        if theme_id in self.theme_repo.get_by_id():
            return
        await self.execute()
