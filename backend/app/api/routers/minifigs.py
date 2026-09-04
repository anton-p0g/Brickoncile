import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import (
    HistoryRepoDep,
    InstanceRepoDep,
    SetRepoDep,
    get_add_loose_minifig_use_case,
    get_add_minifig_by_reference_use_case,
    get_adjust_minifig_part_found_use_case,
    get_change_minifig_fig_num_use_case,
    get_delete_minifig_instance_use_case,
    get_identify_minifig_use_case,
    get_mark_minifig_instance_found_use_case,
    get_resync_use_case,
    get_set_parts_found_use_case,
    get_update_part_condition_use_case,
    get_update_sorting_state_use_case,
)
from app.api.schemas import (
    AddLooseMinifigRequest,
    AddMinifigByReferenceRequest,
    AddMinifigByReferenceResponse,
    BulkAddMinifigResultItem,
    BulkAddMinifigsRequest,
    BulkAddMinifigsResponse,
    ChangeMinifigFigNumRequest,
    ChangeMinifigFigNumResponse,
    EntityTotals,
    FoundDeltaRequest,
    HistoryEntryOut,
    IdentifyMinifigResponse,
    MarkMinifigPartResponse,
    MinifigInstanceDetail,
    MinifigInstanceSummary,
    PartConditionRequest,
    PartOut,
    SetPartsFoundRequest,
    SetPartsFoundResponse,
    SortingStateRequest,
)
from app.application.use_cases.add_loose_minifig import AddLooseMinifigUseCase
from app.application.use_cases.add_minifig_by_reference import (
    AddMinifigByReferenceUseCase,
)
from app.application.use_cases.adjust_minifig_part_found import (
    AdjustMinifigPartFoundUseCase,
)
from app.application.use_cases.change_minifig_fig_num import ChangeMinifigFigNumUseCase
from app.application.use_cases.delete_minifig_instance import (
    DeleteMinifigInstanceUseCase,
)
from app.application.use_cases.identify_minifig import IdentifyMinifigUseCase
from app.application.use_cases.mark_minifig_instance_found import (
    MarkMinifigInstanceFoundUseCase,
)
from app.application.use_cases.resync_from_source import ResyncFromSourceUseCase
from app.application.use_cases.set_parts_found import SetPartsFoundUseCase
from app.application.use_cases.update_part_condition import UpdatePartConditionUseCase
from app.application.use_cases.update_sorting_state import UpdateSortingStateUseCase
from app.domain.entities import MinifigInstance
from app.domain.errors import (
    EntityNotFoundError,
    EntityOwnedBySetError,
    ImageRecognitionUnavailableError,
    PartsCatalogNotFoundError,
    PartsCatalogUnavailableError,
    UnreadableImageError,
    UnresolvableMinifigReferenceError,
)
from app.domain.repositories.dtos import PartFoundUpdate
from app.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/minifigs", tags=["minifigs"])


@router.post("/identify")
async def identify_minifig(
    identify: Annotated[IdentifyMinifigUseCase, Depends(get_identify_minifig_use_case)],
    photo: Annotated[UploadFile, File()],
) -> IdentifyMinifigResponse:
    """Suggest catalog entries for a photographed minifig. Read-only: nothing is added until the
    owner confirms one of the candidates, because the two catalogs' names disagree often enough
    that an automatic pick would quietly file the wrong figure."""
    settings = get_settings()
    image_bytes = await photo.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="That upload was empty; try taking the photo again.")
    if len(image_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="That photo is too large; try a smaller one.")

    try:
        result = await identify.execute(image_bytes, photo.filename or "upload.jpg", photo.content_type)
    except UnreadableImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImageRecognitionUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Image recognition is unavailable: {exc}") from exc
    except PartsCatalogUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return IdentifyMinifigResponse.from_use_case(result)


@router.post("/instances/loose", status_code=201)
async def add_loose_instance(
    body: AddLooseMinifigRequest,
    add_loose: Annotated[AddLooseMinifigUseCase, Depends(get_add_loose_minifig_use_case)],
) -> MinifigInstanceDetail:
    """Add a confirmed minifig that no owned set accounts for."""
    try:
        instance = await add_loose.execute(body.fig_num)
    except PartsCatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No minifig {body.fig_num} in the catalog") from exc
    except PartsCatalogUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return MinifigInstanceDetail.from_domain(instance, source_set_name=None)


@router.post("/instances/manual", status_code=201)
async def add_instance_by_reference(
    body: AddMinifigByReferenceRequest,
    add_by_reference: Annotated[
        AddMinifigByReferenceUseCase, Depends(get_add_minifig_by_reference_use_case)
    ],
) -> AddMinifigByReferenceResponse:
    """Add a minifig from a pasted Rebrickable link, fig ID, or BrickLink link.

    The manual way in when a photo cannot be identified. A reference that cannot become a fig id
    is a 400 rather than a 404: nothing was looked up, so the input is what needs correcting."""
    try:
        result = await add_by_reference.execute(body.reference)
    except UnresolvableMinifigReferenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PartsCatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No such minifigure on Rebrickable") from exc
    except PartsCatalogUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AddMinifigByReferenceResponse.from_use_case(result)


@router.post("/instances/manual/bulk")
async def bulk_add_instances_by_reference(
    body: BulkAddMinifigsRequest,
    add_by_reference: Annotated[
        AddMinifigByReferenceUseCase, Depends(get_add_minifig_by_reference_use_case)
    ],
) -> BulkAddMinifigsResponse:
    """Every reference is added independently, so one bad line reports itself and the rest still
    land. Mirrors the bulk set add, minus its "already owned" outcome: a second copy of a minifig
    is a second figure in a box, not a repeat of the first."""
    results: list[BulkAddMinifigResultItem] = []
    for raw_reference in body.references:
        try:
            result = await add_by_reference.execute(raw_reference)
        except (UnresolvableMinifigReferenceError, PartsCatalogUnavailableError) as exc:
            results.append(
                BulkAddMinifigResultItem(input_reference=raw_reference, status="error", error=str(exc))
            )
        except PartsCatalogNotFoundError:
            results.append(
                BulkAddMinifigResultItem(
                    input_reference=raw_reference, status="error", error="not found on Rebrickable"
                )
            )
        except Exception as exc:
            # Anything unforeseen would otherwise 500 the batch and lose the report for every line
            # in it, including the ones that already landed. See bulk_add_sets.
            logger.exception("Bulk minifig add failed for %s", raw_reference)
            results.append(
                BulkAddMinifigResultItem(
                    input_reference=raw_reference,
                    status="error",
                    error=f"unexpected error ({type(exc).__name__})",
                )
            )
        else:
            results.append(
                BulkAddMinifigResultItem(
                    input_reference=raw_reference,
                    status="ok",
                    fig_num=result.instance.fig_num,
                    fig_name=result.instance.fig_name,
                    instance_id=result.instance.id,
                    already_owned_count=result.already_owned_count,
                )
            )
    return BulkAddMinifigsResponse(results=results)


def _source_set_name(set_repo: SetRepoDep, instance: MinifigInstance) -> str | None:
    """None for a loose minifig, which has no source set to name."""
    if instance.source_set_num is None:
        return None
    source_set = set_repo.get(instance.source_set_num)
    return source_set.name if source_set else None


@router.get("/instances")
def list_instances(instance_repo: InstanceRepoDep, set_repo: SetRepoDep) -> list[MinifigInstanceSummary]:
    instances = instance_repo.list_all()
    set_names = {s.set_num: s.name for s in set_repo.list_all()}
    return [
        MinifigInstanceSummary.from_domain(
            i, source_set_name=set_names.get(i.source_set_num) if i.source_set_num else None
        )
        for i in instances
    ]


@router.get("/instances/{instance_id}")
def get_instance(instance_id: str, instance_repo: InstanceRepoDep, set_repo: SetRepoDep) -> MinifigInstanceDetail:
    instance = instance_repo.get(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Minifig instance not found")
    return MinifigInstanceDetail.from_domain(instance, source_set_name=_source_set_name(set_repo, instance))


@router.post("/instances/{instance_id}/found")
def mark_instance_found(
    instance_id: str,
    mark_found: Annotated[
        MarkMinifigInstanceFoundUseCase, Depends(get_mark_minifig_instance_found_use_case)
    ],
    set_repo: SetRepoDep,
) -> MinifigInstanceDetail:
    """Account for an assembled minifig the owner has in hand, confirming all of its pieces.

    This is how identifying a photo resolves to a minifig an owned set already expects, instead of
    filing a loose duplicate beside it."""
    try:
        instance = mark_found.execute(instance_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MinifigInstanceDetail.from_domain(instance, source_set_name=_source_set_name(set_repo, instance))


@router.post("/instances/{instance_id}/fig-num")
async def change_instance_fig_num(
    instance_id: str,
    body: ChangeMinifigFigNumRequest,
    change_fig_num: Annotated[ChangeMinifigFigNumUseCase, Depends(get_change_minifig_fig_num_use_case)],
    set_repo: SetRepoDep,
) -> ChangeMinifigFigNumResponse:
    """Correct which catalog entry a loose minifig is filed under, refetching its parts list.

    The response says where the figure ended up: unless the outcome is `unchanged`, the instance in
    it is a different record than the one addressed here, and `instance_id` no longer resolves."""
    try:
        result = await change_fig_num.execute(instance_id, body.fig_num)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EntityOwnedBySetError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PartsCatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No minifig {body.fig_num} in the catalog") from exc
    except PartsCatalogUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ChangeMinifigFigNumResponse.from_use_case(
        result, source_set_name=_source_set_name(set_repo, result.instance)
    )


@router.delete("/instances/{instance_id}", status_code=204)
def delete_instance(
    instance_id: str,
    delete: Annotated[DeleteMinifigInstanceUseCase, Depends(get_delete_minifig_instance_use_case)],
) -> None:
    """Remove a loose minifig while retaining images in the shared collection cache."""
    try:
        delete.execute(instance_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EntityOwnedBySetError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/instances/{instance_id}/parts/{part_num}/colors/{color_id}/found")
def adjust_instance_part_found(
    instance_id: str,
    part_num: str,
    color_id: int,
    body: FoundDeltaRequest,
    adjust_found: Annotated[AdjustMinifigPartFoundUseCase, Depends(get_adjust_minifig_part_found_use_case)],
) -> MarkMinifigPartResponse:
    try:
        part, instance = adjust_found.execute(instance_id, part_num, color_id, body.found_delta)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarkMinifigPartResponse(
        part=PartOut.from_domain(part), instance_summary=EntityTotals.from_inventory(instance)
    )


@router.post("/instances/{instance_id}/parts/{part_num}/colors/{color_id}/condition")
def update_instance_part_condition(
    instance_id: str,
    part_num: str,
    color_id: int,
    body: PartConditionRequest,
    update_condition: Annotated[
        UpdatePartConditionUseCase, Depends(get_update_part_condition_use_case)
    ],
) -> MarkMinifigPartResponse:
    try:
        part, instance = update_condition.execute(
            "minifig_instance",
            instance_id,
            part_num,
            color_id,
            body.quantity_found,
            body.quantity_broken,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarkMinifigPartResponse(
        part=PartOut.from_domain(part), instance_summary=EntityTotals.from_inventory(instance)
    )


@router.post("/instances/{instance_id}/parts/found")
def set_instance_parts_found(
    instance_id: str,
    body: SetPartsFoundRequest,
    set_parts_found_use_case: Annotated[SetPartsFoundUseCase, Depends(get_set_parts_found_use_case)],
) -> SetPartsFoundResponse:
    """Set many parts' found counts at once. See the set equivalent."""
    try:
        parts, instance = set_parts_found_use_case.execute(
            "minifig_instance",
            instance_id,
            [PartFoundUpdate(part_num=p.part_num, color_id=p.color_id, quantity_found=p.quantity_found) for p in body.parts],
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SetPartsFoundResponse.from_domain(parts, instance)


@router.post("/instances/{instance_id}/sorting")
def update_instance_sorting(
    instance_id: str,
    body: SortingStateRequest,
    update_state: Annotated[UpdateSortingStateUseCase, Depends(get_update_sorting_state_use_case)],
    instance_repo: InstanceRepoDep,
    set_repo: SetRepoDep,
) -> MinifigInstanceDetail:
    try:
        update_state.execute("minifig_instance", instance_id, body.finished)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    instance = instance_repo.get(instance_id)
    assert instance is not None
    return MinifigInstanceDetail.from_domain(instance, source_set_name=_source_set_name(set_repo, instance))


@router.post("/instances/{instance_id}/resync")
async def resync_instance(
    instance_id: str,
    instance_repo: InstanceRepoDep,
    set_repo: SetRepoDep,
    resync: Annotated[ResyncFromSourceUseCase, Depends(get_resync_use_case)],
) -> MinifigInstanceDetail:
    instance = instance_repo.get(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Minifig instance not found")
    try:
        await resync.execute("minifig", instance.fig_num)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PartsCatalogUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    refreshed = instance_repo.get(instance_id)
    assert refreshed is not None
    return MinifigInstanceDetail.from_domain(refreshed, source_set_name=_source_set_name(set_repo, refreshed))


@router.get("/instances/{instance_id}/history")
def get_instance_history(
    instance_id: str,
    history_repo: HistoryRepoDep,
    part_num: str | None = None,
    color_id: int | None = None,
) -> list[HistoryEntryOut]:
    records = history_repo.list_for_entity("minifig_instance", instance_id, part_num=part_num, color_id=color_id)
    return [HistoryEntryOut.from_domain(r) for r in records]
