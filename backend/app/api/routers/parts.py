from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_search_parts_use_case
from app.api.schemas import PartSearchResultOut
from app.application.use_cases.search_parts import DEFAULT_LIMIT, SearchPartsUseCase

router = APIRouter(prefix="/api/parts", tags=["parts"])


@router.get("/search")
def search_parts(
    use_case: Annotated[SearchPartsUseCase, Depends(get_search_parts_use_case)],
    q: str = "",
    color_id: int | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=200),
) -> list[PartSearchResultOut]:
    """Which inventories contain this part, and how many copies each still wants.

    `q` matches a part number, part name, or element id. An empty query returns nothing rather
    than the whole collection, since this screen is driven by a brick in hand.
    """
    results = use_case.execute(query=q, color_id=color_id, limit=limit)
    return [PartSearchResultOut.from_use_case(r) for r in results]
