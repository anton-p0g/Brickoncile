import httpx
import pytest

from app.domain.errors import PartsCatalogNotFoundError, PartsCatalogUnavailableError
from app.infrastructure.external import rebrickable_client
from app.infrastructure.external.rebrickable_client import BASE_URL, RebrickableClient

THROTTLED_BODY = '{"detail":"Request was throttled. Expected available in 38 seconds."}'


@pytest.fixture
def slept(monkeypatch):
    """Records what the client would have waited, so the tests do not actually wait."""
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(rebrickable_client.asyncio, "sleep", fake_sleep)
    return waits


def make_client(responses: list[httpx.Response]) -> tuple[RebrickableClient, list[httpx.Request]]:
    """Replies with `responses` in order, repeating the last one once exhausted."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses[min(len(seen) - 1, len(responses) - 1)]

    http_client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return RebrickableClient(api_key="test", http_client=http_client), seen


def set_payload() -> dict:
    return {"set_num": "75192-1", "name": "Millennium Falcon", "year": 2017, "num_parts": 7541}


async def test_waits_out_a_throttle_and_retries(slept):
    client, seen = make_client(
        [
            httpx.Response(429, text=THROTTLED_BODY),
            httpx.Response(200, json=set_payload()),
        ]
    )

    metadata = await client.fetch_set_metadata("75192-1")

    assert metadata.set_num == "75192-1"
    assert len(seen) == 2
    # The wait the API asked for, plus the margin that keeps the retry off the exact boundary.
    assert slept == [38.5]


async def test_prefers_the_retry_after_header(slept):
    client, _ = make_client(
        [
            httpx.Response(429, headers={"Retry-After": "12"}, text=THROTTLED_BODY),
            httpx.Response(200, json=set_payload()),
        ]
    )

    await client.fetch_set_metadata("75192-1")

    assert slept == [12.5]


async def test_falls_back_to_a_default_wait_when_the_throttle_says_nothing(slept):
    client, _ = make_client([httpx.Response(429, text="slow down"), httpx.Response(200, json=set_payload())])

    await client.fetch_set_metadata("75192-1")

    assert slept == [rebrickable_client.DEFAULT_THROTTLE_WAIT_SECONDS]


async def test_gives_up_after_the_retry_budget(slept):
    client, seen = make_client([httpx.Response(429, text=THROTTLED_BODY)])

    with pytest.raises(PartsCatalogUnavailableError) as exc_info:
        await client.fetch_set_metadata("75192-1")

    assert "429" in str(exc_info.value)
    assert len(seen) == rebrickable_client.MAX_THROTTLE_RETRIES + 1
    assert len(slept) == rebrickable_client.MAX_THROTTLE_RETRIES


async def test_does_not_sit_on_a_throttle_that_will_not_clear_soon(slept):
    """A limit measured in hours is reported rather than waited out — a request that hangs for
    that long is worse than being told what happened."""
    client, seen = make_client([httpx.Response(429, headers={"Retry-After": "3600"}, text="")])

    with pytest.raises(PartsCatalogUnavailableError):
        await client.fetch_set_metadata("75192-1")

    assert len(seen) == 1
    assert slept == []


async def test_a_404_is_still_a_missing_set_not_a_retry(slept):
    client, seen = make_client([httpx.Response(404, text="")])

    with pytest.raises(PartsCatalogNotFoundError):
        await client.fetch_set_metadata("nope-1")

    assert len(seen) == 1
    assert slept == []


async def test_search_minifigs_maps_the_fig_identifier_out_of_set_num(slept):
    """Rebrickable returns minifigs shaped like sets, so the fig_num arrives under `set_num`."""
    results = {
        "count": 2,
        "next": None,
        "results": [
            {"set_num": "fig-000068", "name": "Chief Wiggum (CMF)", "num_parts": 4, "set_img_url": "https://x/1.jpg"},
            {"set_num": "fig-004550", "name": "Chief Wiggum", "num_parts": 5, "set_img_url": None},
        ],
    }
    client, seen = make_client([httpx.Response(200, json=results)])

    found = await client.search_minifigs("Chief Wiggum", limit=20)

    assert [f.fig_num for f in found] == ["fig-000068", "fig-004550"]
    assert found[0].name == "Chief Wiggum (CMF)"
    assert seen[0].url.params["search"] == "Chief Wiggum"
    assert seen[0].url.params["page_size"] == "20"


async def test_search_minifigs_with_no_hits_is_an_empty_list(slept):
    client, _ = make_client([httpx.Response(200, json={"count": 0, "next": None, "results": []})])

    assert await client.search_minifigs("Nothing Here", limit=20) == []


async def test_throttles_are_retried_while_paging_too(slept):
    """Parts lists page, and the throttle usually lands mid-way — a retry that only covered the
    first page would still lose the rest of the set."""
    page_one = {"count": 2, "next": f"{BASE_URL}/sets/75192-1/parts/?page=2", "results": [{"a": 1}]}
    client, seen = make_client(
        [
            httpx.Response(200, json=page_one),
            httpx.Response(429, text=THROTTLED_BODY),
            httpx.Response(200, json={"count": 2, "next": None, "results": [{"a": 2}]}),
        ]
    )

    results = await client._paginate("/sets/75192-1/parts/")

    assert results == [{"a": 1}, {"a": 2}]
    assert len(seen) == 3
    assert slept == [38.5]
