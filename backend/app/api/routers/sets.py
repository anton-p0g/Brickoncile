import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    HistoryRepoDep,
    InstanceRepoDep,
    SetRepoDep,
    ThemeRepoDep,
    get_adjust_set_part_found_use_case,
    get_delete_set_use_case,
    get_fetch_set_use_case,
    get_resync_use_case,
    get_set_parts_found_use_case,
    get_update_sorting_state_use_case,
)
from app.api.schemas import (
    AddSetRequest,
    AddSetResponse,
    BulkAddResultItem,
    BulkAddSetsRequest,
    BulkAddSetsResponse,
    EntityTotals,
    FoundDeltaRequest,
    HistoryEntryOut,
    MarkSetPartResponse,
    MinifigInstanceSummary,
    PartOut,
    SetDetail,
    SetPartsFoundRequest,
    SetPartsFoundResponse,
    SetSummary,
    SortingStateRequest,
)
from app.application.use_cases.adjust_set_part_found import AdjustSetPartFoundUseCase
from app.application.use_cases.delete_set import DeleteSetUseCase
from app.application.use_cases.fetch_set import FetchSetUseCase
from app.application.use_cases.resync_from_source import ResyncFromSourceUseCase
from app.application.use_cases.set_parts_found import SetPartsFoundUseCase
from app.application.use_cases.update_sorting_state import UpdateSortingStateUseCase
from app.domain.errors import (
    EntityNotFoundError,
    PartsCatalogNotFoundError,
    PartsCatalogUnavailableError,
)
from app.domain.repositories.dtos import PartFoundUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sets", tags=["sets"])


def _warning_text(warnings: tuple[str, ...]) -> str | None:
    """A set that landed with something missing reports what is missing, not a bare failure."""
    return "; ".join(warnings) if warnings else None


@router.get("")
def list_sets(set_repo: SetRepoDep, theme_repo: ThemeRepoDep) -> list[SetSummary]:
    # The theme tree is read once and shared across every set, rather than resolved per set.
    themes = theme_repo.get_by_id()
    return [SetSummary.from_domain(s, themes) for s in set_repo.list_all()]


@router.post("")
async def add_set(
    body: AddSetRequest,
    fetch_set: Annotated[FetchSetUseCase, Depends(get_fetch_set_use_case)],
    theme_repo: ThemeRepoDep,
) -> AddSetResponse:
    try:
        outcome = await fetch_set.execute_with_outcome(body.set_num)
    except PartsCatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Set not found on Rebrickable") from exc
    except PartsCatalogUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AddSetResponse(
        status="exists" if outcome.already_owned else "ok",
        set=SetDetail.from_domain(outcome.lego_set, theme_repo.get_by_id()),
        warning=_warning_text(outcome.warnings),
    )


@router.post("/bulk")
async def bulk_add_sets(
    body: BulkAddSetsRequest, fetch_set: Annotated[FetchSetUseCase, Depends(get_fetch_set_use_case)]
) -> BulkAddSetsResponse:
    """Every set is fetched independently: one bad number reports itself and the rest still land,
    rather than losing a long pasted list to a single typo."""
    results = []
    for raw_set_num in body.set_nums:
        try:
            outcome = await fetch_set.execute_with_outcome(raw_set_num)
        except PartsCatalogNotFoundError:
            results.append(
                BulkAddResultItem(
                    set_num=raw_set_num,
                    input_set_num=raw_set_num,
                    status="error",
                    error="not found on Rebrickable",
                )
            )
        except PartsCatalogUnavailableError as exc:
            results.append(
                BulkAddResultItem(set_num=raw_set_num, input_set_num=raw_set_num, status="error", error=str(exc))
            )
        except Exception as exc:
            # Anything unforeseen (a malformed Rebrickable payload, a write that fails) would
            # otherwise 500 the whole batch and lose the report for every set in it.
            logger.exception("Bulk add failed for %s", raw_set_num)
            results.append(
                BulkAddResultItem(
                    set_num=raw_set_num,
                    input_set_num=raw_set_num,
                    status="error",
                    error=f"unexpected error ({type(exc).__name__})",
                )
            )
        else:
            if outcome.already_owned:
                status = "exists"
            else:
                status = "partial" if outcome.warnings else "ok"
            results.append(
                BulkAddResultItem(
                    set_num=outcome.lego_set.set_num,
                    input_set_num=raw_set_num,
                    status=status,
                    name=outcome.lego_set.name,
                    error=_warning_text(outcome.warnings),
                )
            )
    return BulkAddSetsResponse(results=results)


@router.get("/{set_num}")
def get_set(set_num: str, set_repo: SetRepoDep, theme_repo: ThemeRepoDep) -> SetDetail:
    lego_set = set_repo.get(set_num)
    if lego_set is None:
        raise HTTPException(status_code=404, detail="Set not found in local cache")
    return SetDetail.from_domain(lego_set, theme_repo.get_by_id())


@router.delete("/{set_num}", status_code=204)
def delete_set(set_num: str, delete: Annotated[DeleteSetUseCase, Depends(get_delete_set_use_case)]) -> None:
    try:
        delete.execute(set_num)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{set_num}/parts/{part_num}/colors/{color_id}/found")
def adjust_part_found(
    set_num: str,
    part_num: str,
    color_id: int,
    body: FoundDeltaRequest,
    adjust_found: Annotated[AdjustSetPartFoundUseCase, Depends(get_adjust_set_part_found_use_case)],
) -> MarkSetPartResponse:
    try:
        part, lego_set = adjust_found.execute(set_num, part_num, color_id, body.found_delta)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarkSetPartResponse(part=PartOut.from_domain(part), set_summary=EntityTotals.from_inventory(lego_set))


@router.post("/{set_num}/parts/found")
def set_parts_found(
    set_num: str,
    body: SetPartsFoundRequest,
    set_parts_found_use_case: Annotated[SetPartsFoundUseCase, Depends(get_set_parts_found_use_case)],
) -> SetPartsFoundResponse:
    """Set many parts' found counts at once, for confirming everything still showing in the grid."""
    try:
        parts, lego_set = set_parts_found_use_case.execute(
            "set",
            set_num,
            [PartFoundUpdate(part_num=p.part_num, color_id=p.color_id, quantity_found=p.quantity_found) for p in body.parts],
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SetPartsFoundResponse.from_domain(parts, lego_set)


@router.post("/{set_num}/sorting")
def update_sorting(
    set_num: str,
    body: SortingStateRequest,
    update_state: Annotated[UpdateSortingStateUseCase, Depends(get_update_sorting_state_use_case)],
    set_repo: SetRepoDep,
    theme_repo: ThemeRepoDep,
) -> SetDetail:
    """Finish sorting, which turns unfound pieces into confirmed missing ones, or resume it."""
    try:
        update_state.execute("set", set_num, body.finished)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    lego_set = set_repo.get(set_num)
    assert lego_set is not None
    return SetDetail.from_domain(lego_set, theme_repo.get_by_id())


@router.post("/{set_num}/resync")
async def resync_set(
    set_num: str,
    resync: Annotated[ResyncFromSourceUseCase, Depends(get_resync_use_case)],
    theme_repo: ThemeRepoDep,
) -> SetDetail:
    try:
        lego_set = await resync.execute("set", set_num)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PartsCatalogUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SetDetail.from_domain(lego_set, theme_repo.get_by_id())


@router.get("/{set_num}/history")
def get_history(
    set_num: str,
    history_repo: HistoryRepoDep,
    part_num: str | None = None,
    color_id: int | None = None,
) -> list[HistoryEntryOut]:
    records = history_repo.list_for_entity("set", set_num, part_num=part_num, color_id=color_id)
    return [HistoryEntryOut.from_domain(r) for r in records]


@router.get("/{set_num}/minifigs")
def get_set_minifigs(set_num: str, set_repo: SetRepoDep, instance_repo: InstanceRepoDep) -> list[MinifigInstanceSummary]:
    lego_set = set_repo.get(set_num)
    if lego_set is None:
        raise HTTPException(status_code=404, detail="Set not found in local cache")
    instances = instance_repo.list_by_source_set(set_num)
    return [MinifigInstanceSummary.from_domain(i, source_set_name=lego_set.name) for i in instances]
