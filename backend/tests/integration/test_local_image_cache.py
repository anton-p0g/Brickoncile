import httpx

from app.infrastructure.cache.local_image_cache import LocalImageCache


async def test_downloads_once_and_reuses_the_shared_file(tmp_path):
    requests = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=b"jpeg", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        cache = LocalImageCache(tmp_path, client)
        first = await cache.get_or_download("https://example.com/3001.jpg", "parts", "3001_0")
        second = await cache.get_or_download("https://example.com/3001.jpg", "parts", "3001_0")

    assert first == second == "parts/3001_0.jpg"
    assert (tmp_path / "parts" / "3001_0.jpg").read_bytes() == b"jpeg"
    assert requests == 1
    assert [path.name for path in (tmp_path / "parts").iterdir()] == ["3001_0.jpg"]


def test_delete_removes_the_file_from_disk(tmp_path):
    cache = LocalImageCache(tmp_path)
    image = tmp_path / "parts" / "3001_0.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg")

    cache.delete("parts/3001_0.jpg")

    assert not image.exists()


def test_delete_is_silent_when_the_file_is_already_gone(tmp_path):
    """Deleting a set whose image download had failed must not blow up the request."""
    LocalImageCache(tmp_path).delete("parts/never-downloaded.jpg")


def test_delete_refuses_to_escape_the_cache_root(tmp_path):
    root = tmp_path / "images"
    root.mkdir()
    outsider = tmp_path / "important.db"
    outsider.write_bytes(b"data")

    LocalImageCache(root).delete("../important.db")

    assert outsider.exists()
