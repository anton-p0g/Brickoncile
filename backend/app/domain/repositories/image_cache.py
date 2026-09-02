from typing import Protocol


class ImageCache(Protocol):
    """Fetch-once-cache-forever local image store. Returns a path relative to the images root."""

    async def get_or_download(self, remote_url: str | None, category: str, key: str) -> str | None: ...

    def delete(self, relative_path: str) -> None:
        """Remove a cached file during global maintenance, never from one collection alone."""
        ...
