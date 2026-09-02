from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CollectionManagerDep
from app.api.schemas import CollectionCreateRequest, CollectionOut
from app.domain.errors import CollectionNameConflictError, InvalidCollectionNameError
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


def _to_output(record: CollectionRecord) -> CollectionOut:
    return CollectionOut(
        id=record.id,
        name=record.name,
        created_at=record.created_at,
        is_default=record.is_default,
    )
