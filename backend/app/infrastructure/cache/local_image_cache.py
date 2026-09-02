import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx


class LocalImageCache:
    """Fetch-once-cache-forever: returns the relative path immediately if the file already
    exists on disk (no revalidation against the remote), otherwise downloads and stores it."""

    def __init__(self, root: Path, http_client: httpx.AsyncClient | None = None):
        self.root = root
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def delete(self, relative_path: str) -> None:
        # Resolve and confine to the cache root so a malformed stored path cannot reach outside it.
        full_path = (self.root / relative_path).resolve()
        if not full_path.is_relative_to(self.root.resolve()):
            return
        full_path.unlink(missing_ok=True)

    async def get_or_download(self, remote_url: str | None, category: str, key: str) -> str | None:
        if not remote_url:
            return None

        extension = Path(urlparse(remote_url).path).suffix or ".jpg"
        relative_path = f"{category}/{key}{extension}"
        full_path = self.root / relative_path

        if full_path.exists():
            return relative_path

        try:
            response = await self._client.get(remote_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None  # a broken image link shouldn't fail the whole set/minifig fetch

        full_path.parent.mkdir(parents=True, exist_ok=True)
        # A second collection can request the same image concurrently. Write beside the target and
        # atomically replace it so neither request can expose a partially written image.
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=full_path.parent, delete=False) as temporary:
                temporary.write(response.content)
                temporary_path = temporary.name
            os.replace(temporary_path, full_path)
        finally:
            if temporary_path is not None:
                Path(temporary_path).unlink(missing_ok=True)
        return relative_path
