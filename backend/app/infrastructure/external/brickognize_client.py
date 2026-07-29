import logging

import httpx
from pydantic import BaseModel

from app.domain.errors import ImageRecognitionUnavailableError, UnreadableImageError
from app.domain.repositories.dtos import MinifigRecognitionDTO

logger = logging.getLogger(__name__)

BASE_URL = "https://api.brickognize.com"

PREDICT_FIGS_PATH = "/predict/figs/"
"""Brickognize labels every /predict/ endpoint "legacy" and says it will be deprecated eventually,
without naming a date, and publishes no replacement. It is the only recognition endpoint there is,
so it is what this adapter calls — and the MinifigRecognizer port exists so that swapping it out
later touches this file alone."""


class _ExternalSiteResponse(BaseModel):
    model_config = {"extra": "ignore"}
    name: str
    url: str


class _CandidateItemResponse(BaseModel):
    model_config = {"extra": "ignore"}
    id: str
    name: str
    img_url: str | None = None
    category: str | None = None
    score: float = 0.0
    external_sites: list[_ExternalSiteResponse] = []


class _SearchResultsResponse(BaseModel):
    model_config = {"extra": "ignore"}
    listing_id: str | None = None
    items: list[_CandidateItemResponse] = []


class BrickognizeClient:
    """Implements MinifigRecognizer against the Brickognize image-recognition API."""

    def __init__(self, base_url: str = BASE_URL, http_client: httpx.AsyncClient | None = None):
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(base_url=base_url, timeout=60.0)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def identify(
        self, image_bytes: bytes, filename: str, content_type: str | None = None
    ) -> list[MinifigRecognitionDTO]:
        if not image_bytes:
            raise UnreadableImageError("the uploaded photo was empty")

        files = {"query_image": (filename or "upload.jpg", image_bytes, content_type or "image/jpeg")}
        try:
            response = await self._client.post(PREDICT_FIGS_PATH, files=files)
        except httpx.HTTPError as exc:
            raise ImageRecognitionUnavailableError(str(exc)) from exc

        # 422 is how the API reports a body it could not decode as an image, which is the caller's
        # problem to fix by uploading a different photo — not an outage.
        if response.status_code in (400, 415, 422):
            raise UnreadableImageError("that file could not be read as a photo of a minifigure")
        if response.is_error:
            raise ImageRecognitionUnavailableError(f"{response.status_code}: {response.text}")

        parsed = _SearchResultsResponse.model_validate(response.json())
        return [
            MinifigRecognitionDTO(
                external_id=item.id,
                name=item.name,
                score=item.score,
                image_url=item.img_url,
                category=item.category,
                reference_url=_bricklink_url(item),
            )
            for item in parsed.items
        ]


def _bricklink_url(item: _CandidateItemResponse) -> str | None:
    """BrickLink is the catalog the recogniser's ids and names come from, so it is the one worth
    linking. Any other site it happens to list is a fallback rather than nothing."""
    for site in item.external_sites:
        if site.name.lower() == "bricklink":
            return site.url
    return item.external_sites[0].url if item.external_sites else None
