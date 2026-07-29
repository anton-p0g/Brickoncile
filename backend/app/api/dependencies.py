from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.application.use_cases.add_loose_minifig import AddLooseMinifigUseCase
from app.application.use_cases.add_minifig_by_reference import (
    AddMinifigByReferenceUseCase,
)
from app.application.use_cases.adjust_minifig_part_found import (
    AdjustMinifigPartFoundUseCase,
)
from app.application.use_cases.adjust_set_part_found import AdjustSetPartFoundUseCase
from app.application.use_cases.change_minifig_fig_num import ChangeMinifigFigNumUseCase
from app.application.use_cases.delete_minifig_instance import (
    DeleteMinifigInstanceUseCase,
)
from app.application.use_cases.delete_set import DeleteSetUseCase
from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.application.use_cases.fetch_set import FetchSetUseCase
from app.application.use_cases.get_missing_summary import GetMissingSummaryUseCase
from app.application.use_cases.identify_minifig import IdentifyMinifigUseCase
from app.application.use_cases.mark_minifig_instance_found import (
    MarkMinifigInstanceFoundUseCase,
)
from app.application.use_cases.resync_from_source import ResyncFromSourceUseCase
from app.application.use_cases.search_parts import SearchPartsUseCase
from app.application.use_cases.set_parts_found import SetPartsFoundUseCase
from app.application.use_cases.sync_minifig_roster import SyncMinifigRosterUseCase
from app.application.use_cases.sync_themes import SyncThemesUseCase
from app.application.use_cases.update_sorting_state import UpdateSortingStateUseCase
from app.domain.repositories import ImageCache, MinifigRecognizer, PartsCatalogClient
from app.infrastructure.db.session import get_session
from app.infrastructure.db.sqlite_minifig_instance_repository import (
    SqliteMinifigInstanceRepository,
)
from app.infrastructure.db.sqlite_minifig_repository import SqliteMinifigRepository
from app.infrastructure.db.sqlite_missing_history_repository import (
    SqliteMissingHistoryRepository,
)
from app.infrastructure.db.sqlite_set_repository import SqliteSetRepository
from app.infrastructure.db.sqlite_theme_repository import SqliteThemeRepository

SessionDep = Annotated[Session, Depends(get_session)]


def get_catalog_client(request: Request) -> PartsCatalogClient:
    return request.app.state.catalog_client


def get_image_cache(request: Request) -> ImageCache:
    return request.app.state.image_cache


def get_minifig_recognizer(request: Request) -> MinifigRecognizer:
    return request.app.state.minifig_recognizer


CatalogDep = Annotated[PartsCatalogClient, Depends(get_catalog_client)]
ImagesDep = Annotated[ImageCache, Depends(get_image_cache)]
RecognizerDep = Annotated[MinifigRecognizer, Depends(get_minifig_recognizer)]


def get_set_repository(session: SessionDep) -> SqliteSetRepository:
    return SqliteSetRepository(session)


def get_minifig_repository(session: SessionDep) -> SqliteMinifigRepository:
    return SqliteMinifigRepository(session)


def get_minifig_instance_repository(session: SessionDep) -> SqliteMinifigInstanceRepository:
    return SqliteMinifigInstanceRepository(session)


def get_missing_history_repository(session: SessionDep) -> SqliteMissingHistoryRepository:
    return SqliteMissingHistoryRepository(session)


def get_theme_repository(session: SessionDep) -> SqliteThemeRepository:
    return SqliteThemeRepository(session)


SetRepoDep = Annotated[SqliteSetRepository, Depends(get_set_repository)]
MinifigRepoDep = Annotated[SqliteMinifigRepository, Depends(get_minifig_repository)]
InstanceRepoDep = Annotated[SqliteMinifigInstanceRepository, Depends(get_minifig_instance_repository)]
HistoryRepoDep = Annotated[SqliteMissingHistoryRepository, Depends(get_missing_history_repository)]
ThemeRepoDep = Annotated[SqliteThemeRepository, Depends(get_theme_repository)]


def get_sync_themes_use_case(theme_repo: ThemeRepoDep, catalog: CatalogDep) -> SyncThemesUseCase:
    return SyncThemesUseCase(theme_repo, catalog)


def get_fetch_minifig_use_case(
    minifig_repo: MinifigRepoDep, catalog: CatalogDep, images: ImagesDep
) -> FetchMinifigUseCase:
    return FetchMinifigUseCase(minifig_repo, catalog, images)


def get_sync_minifig_roster_use_case(
    instance_repo: InstanceRepoDep,
    catalog: CatalogDep,
    fetch_minifig: Annotated[FetchMinifigUseCase, Depends(get_fetch_minifig_use_case)],
) -> SyncMinifigRosterUseCase:
    return SyncMinifigRosterUseCase(instance_repo, catalog, fetch_minifig)


def get_identify_minifig_use_case(
    recognizer: RecognizerDep,
    catalog: CatalogDep,
    instance_repo: InstanceRepoDep,
    set_repo: SetRepoDep,
) -> IdentifyMinifigUseCase:
    # The set names come along so a match already in the collection can say which set it came from
    # rather than only that it is owned.
    set_names = {s.set_num: s.name for s in set_repo.list_all()}
    return IdentifyMinifigUseCase(recognizer, catalog, instance_repo, set_names)


def get_add_loose_minifig_use_case(
    instance_repo: InstanceRepoDep,
    fetch_minifig: Annotated[FetchMinifigUseCase, Depends(get_fetch_minifig_use_case)],
) -> AddLooseMinifigUseCase:
    return AddLooseMinifigUseCase(instance_repo, fetch_minifig)


def get_add_minifig_by_reference_use_case(
    instance_repo: InstanceRepoDep,
    add_loose: Annotated[AddLooseMinifigUseCase, Depends(get_add_loose_minifig_use_case)],
) -> AddMinifigByReferenceUseCase:
    return AddMinifigByReferenceUseCase(instance_repo, add_loose)


def get_fetch_set_use_case(
    set_repo: SetRepoDep,
    catalog: CatalogDep,
    images: ImagesDep,
    sync_roster: Annotated[SyncMinifigRosterUseCase, Depends(get_sync_minifig_roster_use_case)],
    sync_themes: Annotated[SyncThemesUseCase, Depends(get_sync_themes_use_case)],
) -> FetchSetUseCase:
    return FetchSetUseCase(set_repo, catalog, images, sync_roster, sync_themes)


def get_delete_set_use_case(
    set_repo: SetRepoDep,
    instance_repo: InstanceRepoDep,
    minifig_repo: MinifigRepoDep,
    history_repo: HistoryRepoDep,
    images: ImagesDep,
) -> DeleteSetUseCase:
    return DeleteSetUseCase(set_repo, instance_repo, minifig_repo, history_repo, images)


def get_delete_minifig_instance_use_case(
    instance_repo: InstanceRepoDep,
    minifig_repo: MinifigRepoDep,
    history_repo: HistoryRepoDep,
    set_repo: SetRepoDep,
    images: ImagesDep,
) -> DeleteMinifigInstanceUseCase:
    return DeleteMinifigInstanceUseCase(instance_repo, minifig_repo, history_repo, set_repo, images)


def get_adjust_set_part_found_use_case(
    set_repo: SetRepoDep, history_repo: HistoryRepoDep
) -> AdjustSetPartFoundUseCase:
    return AdjustSetPartFoundUseCase(set_repo, history_repo)


def get_adjust_minifig_part_found_use_case(
    instance_repo: InstanceRepoDep, history_repo: HistoryRepoDep
) -> AdjustMinifigPartFoundUseCase:
    return AdjustMinifigPartFoundUseCase(instance_repo, history_repo)


def get_update_sorting_state_use_case(
    set_repo: SetRepoDep, instance_repo: InstanceRepoDep
) -> UpdateSortingStateUseCase:
    return UpdateSortingStateUseCase(set_repo, instance_repo)


def get_missing_summary_use_case(set_repo: SetRepoDep, instance_repo: InstanceRepoDep) -> GetMissingSummaryUseCase:
    return GetMissingSummaryUseCase(set_repo, instance_repo)


def get_search_parts_use_case(set_repo: SetRepoDep, instance_repo: InstanceRepoDep) -> SearchPartsUseCase:
    return SearchPartsUseCase(set_repo, instance_repo)


def get_set_parts_found_use_case(
    set_repo: SetRepoDep, instance_repo: InstanceRepoDep, history_repo: HistoryRepoDep
) -> SetPartsFoundUseCase:
    return SetPartsFoundUseCase(set_repo, instance_repo, history_repo)


def get_mark_minifig_instance_found_use_case(
    instance_repo: InstanceRepoDep,
    set_parts_found: Annotated[SetPartsFoundUseCase, Depends(get_set_parts_found_use_case)],
) -> MarkMinifigInstanceFoundUseCase:
    return MarkMinifigInstanceFoundUseCase(instance_repo, set_parts_found)


def get_change_minifig_fig_num_use_case(
    instance_repo: InstanceRepoDep,
    fetch_minifig: Annotated[FetchMinifigUseCase, Depends(get_fetch_minifig_use_case)],
    add_loose: Annotated[AddLooseMinifigUseCase, Depends(get_add_loose_minifig_use_case)],
    delete_instance: Annotated[
        DeleteMinifigInstanceUseCase, Depends(get_delete_minifig_instance_use_case)
    ],
    mark_found: Annotated[
        MarkMinifigInstanceFoundUseCase, Depends(get_mark_minifig_instance_found_use_case)
    ],
) -> ChangeMinifigFigNumUseCase:
    return ChangeMinifigFigNumUseCase(instance_repo, fetch_minifig, add_loose, delete_instance, mark_found)


def get_resync_use_case(
    set_repo: SetRepoDep,
    minifig_repo: MinifigRepoDep,
    instance_repo: InstanceRepoDep,
    catalog: CatalogDep,
    images: ImagesDep,
    sync_roster: Annotated[SyncMinifigRosterUseCase, Depends(get_sync_minifig_roster_use_case)],
) -> ResyncFromSourceUseCase:
    return ResyncFromSourceUseCase(set_repo, minifig_repo, instance_repo, catalog, images, sync_roster)
