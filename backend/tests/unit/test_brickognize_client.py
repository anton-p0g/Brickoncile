import httpx
import pytest

from app.domain.errors import ImageRecognitionUnavailableError, UnreadableImageError
from app.infrastructure.external.brickognize_client import BASE_URL, BrickognizeClient

PHOTO = b"jpeg-bytes"

# Trimmed from a real /predict/figs/ response.
PREDICTION = {
    "listing_id": "res-bd810b16f57446a2",
    "bounding_box": {"left": 170.6, "upper": 21.5, "right": 604.7, "lower": 746.0, "score": 0.95},
    "items": [
        {
            "id": "sim021",
            "name": "Chief Wiggum, The Simpsons, Series 1 (Minifigure Only without Stand)",
            "img_url": "https://storage.googleapis.com/brickognize-static/fig/sim021/0.webp",
            "external_sites": [
                {"name": "bricklink", "url": "https://www.bricklink.com/v2/catalog/catalogitem.page?M=sim021"}
            ],
            "category": "Collectible Minifigures / The Simpsons",
            "type": "fig",
            "score": 0.869,
        }
    ],
}


def make_client(response: httpx.Response) -> tuple[BrickognizeClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response

    http_client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return BrickognizeClient(http_client=http_client), seen


async def test_parses_candidates_most_confident_first():
    client, _ = make_client(httpx.Response(200, json=PREDICTION))

    candidates = await client.identify(PHOTO, "photo.jpg", "image/jpeg")

    assert len(candidates) == 1
    assert candidates[0].external_id == "sim021"
    assert candidates[0].score == pytest.approx(0.869)
    assert candidates[0].category == "Collectible Minifigures / The Simpsons"


async def test_carries_the_bricklink_link_for_checking_a_match_by_hand():
    client, _ = make_client(httpx.Response(200, json=PREDICTION))

    candidates = await client.identify(PHOTO, "photo.jpg")

    assert candidates[0].reference_url == "https://www.bricklink.com/v2/catalog/catalogitem.page?M=sim021"


async def test_posts_the_photo_as_multipart():
    client, seen = make_client(httpx.Response(200, json=PREDICTION))

    await client.identify(PHOTO, "photo.jpg", "image/jpeg")

    assert seen[0].method == "POST"
    assert seen[0].url.path == "/predict/figs/"
    assert b"query_image" in seen[0].content


async def test_no_match_is_an_empty_list_not_an_error():
    client, _ = make_client(httpx.Response(200, json={"listing_id": "res-1", "items": []}))

    assert await client.identify(PHOTO, "photo.jpg") == []


async def test_an_empty_upload_is_rejected_before_any_request():
    client, seen = make_client(httpx.Response(200, json=PREDICTION))

    with pytest.raises(UnreadableImageError):
        await client.identify(b"", "photo.jpg")

    assert seen == []


@pytest.mark.parametrize("status", [400, 415, 422])
async def test_a_file_the_service_cannot_decode_is_the_callers_problem(status):
    client, _ = make_client(httpx.Response(status, json={"detail": "not an image"}))

    with pytest.raises(UnreadableImageError):
        await client.identify(PHOTO, "notes.txt")


@pytest.mark.parametrize("status", [500, 503])
async def test_a_service_failure_is_reported_as_unavailable(status):
    client, _ = make_client(httpx.Response(status, text="boom"))

    with pytest.raises(ImageRecognitionUnavailableError):
        await client.identify(PHOTO, "photo.jpg")


async def test_a_transport_failure_is_reported_as_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    http_client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    client = BrickognizeClient(http_client=http_client)

    with pytest.raises(ImageRecognitionUnavailableError):
        await client.identify(PHOTO, "photo.jpg")
