from collections.abc import Generator

from fastapi import Header, HTTPException, Query, Request
from sqlmodel import Session

from app.domain.errors import CollectionNotFoundError


def get_session(
    request: Request,
    collection_header: str | None = Header(default=None, alias="X-Collection-ID"),
    collection_query: str | None = Query(default=None, alias="collection_id"),
) -> Generator[Session, None, None]:
    """Open the selected collection for this request, falling back to the original database.

    The query form exists for direct browser downloads such as CSV exports, which cannot attach a
    custom header. Regular API calls use the header so existing route shapes remain compatible.
    """
    collection_id = collection_header or collection_query
    try:
        engine = request.app.state.collection_manager.get_engine(collection_id)
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    with Session(engine) as session:
        yield session
