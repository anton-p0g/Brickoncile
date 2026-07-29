from typing import Protocol

from app.domain.repositories.dtos import MinifigRecognitionDTO


class MinifigRecognizer(Protocol):
    """Abstraction over the image-recognition service (Brickognize in production).

    Deliberately separate from PartsCatalogClient: recognition answers "what does this photo look
    like?" against its own catalog, while the catalog answers "what is fig-000068?". Nothing maps
    one catalog's identifiers onto the other's, so the two stay independent ports and the use case
    bridges them by name.
    """

    async def identify(self, image_bytes: bytes, filename: str, content_type: str | None = None) -> list[MinifigRecognitionDTO]:
        """Best guesses for the minifig in the photo, most confident first. An empty list means the
        photo was readable but nothing matched, which is a normal answer rather than an error."""
        ...
