from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CollectionManagerDep
from app.api.schemas import (
    CollectionCreateRequest,
    CollectionNameRequest,
    CollectionOut,
)
from app.domain.errors import (
    CollectionNameConflictError,
    CollectionNotFoundError,
    InvalidCollectionNameError,
    LastCollectionDeletionError,
)
from app.infrastructure.db.collection_manager import CollectionRecord

router = APIRouter(prefix="/api/collections", tags=["collections"])


@router.get("")
def list_collections(collection_manager: CollectionManagerDep) -> list[CollectionOut]:
    return [_to_output(record) for record in collection_manager.list_collections()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_collection(body: CollectionCreateRequest, collection_manager: CollectionManagerDep) -> CollectionOut:
    try:
        record = collection_manager.create_collection(body.name)
    except InvalidCollectionNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_output(record)


@router.patch("/{collection_id}")
def rename_collection(
    collection_id: str,
    body: CollectionNameRequest,
    collection_manager: CollectionManagerDep,
) -> CollectionOut:
    try:
        record = collection_manager.rename_collection(collection_id, body.name)
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidCollectionNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_output(record)


@router.post("/{collection_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_collection(
    collection_id: str,
    body: CollectionNameRequest,
    collection_manager: CollectionManagerDep,
) -> CollectionOut:
    try:
        record = collection_manager.duplicate_collection(collection_id, body.name)
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidCollectionNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_output(record)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(collection_id: str, collection_manager: CollectionManagerDep) -> None:
    try:
        collection_manager.delete_collection(collection_id)
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LastCollectionDeletionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _to_output(record: CollectionRecord) -> CollectionOut:
    return CollectionOut(
        id=record.id,
        name=record.name,
        created_at=record.created_at,
        is_default=record.is_default,
    )
