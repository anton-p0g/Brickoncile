from app.application.use_cases.sync_themes import SyncThemesUseCase
from app.domain.entities import Theme, resolve_root
from tests.unit.fakes import (
    FakePartsCatalogClient,
    FakeThemeRepository,
    make_theme_dtos,
)

CHIMA = Theme(id=571, parent_id=None, name="Legends of Chima")
CONSTRACTION = Theme(id=573, parent_id=571, name="Constraction")
BY_ID = {t.id: t for t in (CHIMA, CONSTRACTION)}


def test_resolve_root_walks_up_from_a_sub_theme():
    """A set's own theme_id is usually a sub-theme, but an owner groups a shelf by the line."""
    assert resolve_root(573, BY_ID) == CHIMA


def test_resolve_root_of_a_root_theme_is_itself():
    assert resolve_root(571, BY_ID) == CHIMA


def test_resolve_root_returns_none_for_unknown_or_missing_theme():
    assert resolve_root(None, BY_ID) is None
    assert resolve_root(999, BY_ID) is None


def test_resolve_root_stops_at_the_deepest_resolvable_theme():
    """A parent absent from the cache should not lose the theme entirely."""
    orphan = {573: Theme(id=573, parent_id=571, name="Constraction")}
    assert resolve_root(573, orphan) == orphan[573]


def test_resolve_root_survives_a_cycle():
    cyclic = {
        1: Theme(id=1, parent_id=2, name="A"),
        2: Theme(id=2, parent_id=1, name="B"),
    }
    assert resolve_root(1, cyclic) in cyclic.values()


async def test_sync_caches_the_whole_tree():
    catalog = FakePartsCatalogClient(themes=make_theme_dtos())
    theme_repo = FakeThemeRepository()

    await SyncThemesUseCase(theme_repo, catalog).execute()

    assert theme_repo.count() == 3
    assert resolve_root(573, theme_repo.get_by_id()).name == "Legends of Chima"


async def test_ensure_populated_only_fetches_once():
    catalog = FakePartsCatalogClient(themes=make_theme_dtos())
    sync = SyncThemesUseCase(FakeThemeRepository(), catalog)

    await sync.ensure_populated()
    await sync.ensure_populated()

    assert catalog.theme_fetches == 1


async def test_ensure_known_refetches_only_for_an_unseen_theme():
    catalog = FakePartsCatalogClient(themes=make_theme_dtos())
    sync = SyncThemesUseCase(FakeThemeRepository([CHIMA, CONSTRACTION]), catalog)

    await sync.ensure_known(573)
    assert catalog.theme_fetches == 0

    # A theme newer than the cached tree pulls a refresh.
    await sync.ensure_known(435)
    assert catalog.theme_fetches == 1

    await sync.ensure_known(None)
    assert catalog.theme_fetches == 1
