from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_collection_stats_use_case
from app.api.schemas import CollectionStatsOut
from app.application.use_cases.get_collection_stats import GetCollectionStatsUseCase

router = APIRouter(prefix="/api/stats", tags=["stats"])

UseCaseDep = Annotated[GetCollectionStatsUseCase, Depends(get_collection_stats_use_case)]


@router.get("")
def get_collection_stats(use_case: UseCaseDep) -> CollectionStatsOut:
    """One request for the whole dashboard. The sections are computed from a single read of the
    collection, so the numbers on screen always agree with each other."""
    return CollectionStatsOut.from_use_case(use_case.execute())
