import asyncio
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel

from app.domain.errors import PartsCatalogNotFoundError, PartsCatalogUnavailableError
from app.domain.repositories.dtos import (
    MinifigMetadataDTO,
    MinifigRosterEntryDTO,
    MinifigSearchResultDTO,
    PartDTO,
    SetMetadataDTO,
    ThemeDTO,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://rebrickable.com/api/v3/lego"
PAGE_SIZE = 1000

MAX_THROTTLE_RETRIES = 3
"""How many times a single request waits out a throttle before giving up."""

MAX_THROTTLE_WAIT_SECONDS = 90.0
"""Longest wait worth sitting through. A throttle asking for more than this is reported instead,
so an add cannot hang indefinitely on a limit that will not clear soon."""

DEFAULT_THROTTLE_WAIT_SECONDS = 5.0
"""Used when a 429 arrives with no hint about how long to wait."""

_THROTTLE_SECONDS_RE = re.compile(r"available in (\d+(?:\.\d+)?) second")


class _SetResponse(BaseModel):
    model_config = {"extra": "ignore"}
    set_num: str
    name: str
    year: int | None = None
    theme_id: int | None = None
    num_parts: int = 0
    set_img_url: str | None = None


class _ColorResponse(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    name: str


class _PartInfoResponse(BaseModel):
    model_config = {"extra": "ignore"}
    part_num: str
    name: str
    part_img_url: str | None = None


class _InventoryPartResponse(BaseModel):
    model_config = {"extra": "ignore"}
    part: _PartInfoResponse
    color: _ColorResponse
    quantity: int
    is_spare: bool = False
    element_id: str | None = None


class _ThemeResponse(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    parent_id: int | None = None
    name: str


class _MinifigRosterResponse(BaseModel):
    # Rebrickable quirk: GET /sets/{set_num}/minifigs/ represents each minifig as a "set" object —
    # the fig identifier (e.g. "fig-000272") comes back under `set_num`, name under `set_name`.
    model_config = {"extra": "ignore"}
    set_num: str
    set_name: str
    quantity: int
    set_img_url: str | None = None


class _MinifigResponse(BaseModel):
    # Same quirk on GET /minifigs/{fig_num}/: the fig identifier echoes back as `set_num`.
    model_config = {"extra": "ignore"}
    set_num: str
    name: str
    num_parts: int | None = None
    set_img_url: str | None = None


class RebrickableClient:
    """Implements PartsCatalogClient against the real Rebrickable API v3."""

    def __init__(self, api_key: str, http_client: httpx.AsyncClient | None = None):
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"key {api_key}"},
            timeout=30.0,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_set_metadata(self, set_num: str) -> SetMetadataDTO:
        data = await self._get(f"/sets/{set_num}/")
        parsed = _SetResponse.model_validate(data)
        return SetMetadataDTO(
            set_num=parsed.set_num,
            name=parsed.name,
            year=parsed.year,
            theme_id=parsed.theme_id,
            num_parts=parsed.num_parts,
            image_url=parsed.set_img_url,
        )

    async def fetch_themes(self) -> list[ThemeDTO]:
        results = await self._paginate("/themes/")
        parsed = [_ThemeResponse.model_validate(r) for r in results]
        return [ThemeDTO(id=t.id, parent_id=t.parent_id, name=t.name) for t in parsed]

    async def fetch_set_parts(self, set_num: str) -> list[PartDTO]:
        results = await self._paginate(f"/sets/{set_num}/parts/")
        return [self._to_part_dto(_InventoryPartResponse.model_validate(r)) for r in results]

    async def fetch_set_minifigs(self, set_num: str) -> list[MinifigRosterEntryDTO]:
        results = await self._paginate(f"/sets/{set_num}/minifigs/")
        parsed = [_MinifigRosterResponse.model_validate(r) for r in results]
        return [
            MinifigRosterEntryDTO(
                fig_num=r.set_num,
                quantity=r.quantity,
                image_url=r.set_img_url,
            )
            for r in parsed
        ]

    async def fetch_minifig_metadata(self, fig_num: str) -> MinifigMetadataDTO:
        data = await self._get(f"/minifigs/{fig_num}/")
        parsed = _MinifigResponse.model_validate(data)
        return MinifigMetadataDTO(
            fig_num=parsed.set_num,
            name=parsed.name,
            num_parts=parsed.num_parts,
            image_url=parsed.set_img_url,
        )

    async def fetch_minifig_parts(self, fig_num: str) -> list[PartDTO]:
        results = await self._paginate(f"/minifigs/{fig_num}/parts/")
        return [self._to_part_dto(_InventoryPartResponse.model_validate(r)) for r in results]

    async def search_minifigs(self, query: str, limit: int) -> list[MinifigSearchResultDTO]:
        """One page only, deliberately: `search` matches every word, so a query broad enough to run
        past one page ("Luke Skywalker") is one the caller should narrow rather than exhaust."""
        data = await self._get("/minifigs/", params={"search": query, "page_size": limit})
        parsed = [_MinifigResponse.model_validate(r) for r in data.get("results", [])]
        return [
            MinifigSearchResultDTO(
                fig_num=r.set_num,
                name=r.name,
                num_parts=r.num_parts,
                image_url=r.set_img_url,
            )
            for r in parsed
        ]

    def _to_part_dto(self, inv_part: _InventoryPartResponse) -> PartDTO:
        return PartDTO(
            part_num=inv_part.part.part_num,
            color_id=inv_part.color.id,
            color_name=inv_part.color.name,
            part_name=inv_part.part.name,
            element_id=inv_part.element_id,
            quantity=inv_part.quantity,
            is_spare=inv_part.is_spare,
            image_url=inv_part.part.part_img_url,
        )

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._request(path, params=params)

        if response.status_code == 404:
            raise PartsCatalogNotFoundError(path)
        if response.is_error:
            raise PartsCatalogUnavailableError(f"{response.status_code}: {response.text}")
        return response.json()

    async def _paginate(self, path: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        data = await self._get(path, params={"page_size": PAGE_SIZE})
        results.extend(data.get("results", []))
        next_url = data.get("next")

        while next_url:
            response = await self._request(next_url)
            if response.is_error:
                raise PartsCatalogUnavailableError(f"{response.status_code}: {response.text}")
            data = response.json()
            results.extend(data.get("results", []))
            next_url = data.get("next")

        return results

    async def _request(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """One GET, waiting out Rebrickable's rate limit rather than surfacing it.

        The API answers a throttle with how long it wants to be left alone, and adding a set is a
        burst of requests (metadata, parts, every minifig), so hitting the limit part-way through
        is routine rather than exceptional. Waiting is what the caller would do by hand anyway,
        and it is bounded: a throttle that will not clear soon is returned as the error it is.
        """
        for attempt in range(MAX_THROTTLE_RETRIES + 1):
            try:
                response = await self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                raise PartsCatalogUnavailableError(str(exc)) from exc

            if response.status_code != 429 or attempt == MAX_THROTTLE_RETRIES:
                return response

            wait = self._throttle_wait(response)
            if wait > MAX_THROTTLE_WAIT_SECONDS:
                return response

            logger.info(
                "Rebrickable throttled %s, waiting %.1fs (attempt %d/%d)",
                url,
                wait,
                attempt + 1,
                MAX_THROTTLE_RETRIES,
            )
            await asyncio.sleep(wait)

        return response

    @staticmethod
    def _throttle_wait(response: httpx.Response) -> float:
        """Seconds to wait, from `Retry-After` if present, else the wait named in the message.

        Half a second is added on top: retrying on the exact boundary the server named tends to
        come back throttled again.
        """
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.strip().isdigit():
            return float(retry_after) + 0.5

        match = _THROTTLE_SECONDS_RE.search(response.text)
        if match:
            return float(match.group(1)) + 0.5

        return DEFAULT_THROTTLE_WAIT_SECONDS
