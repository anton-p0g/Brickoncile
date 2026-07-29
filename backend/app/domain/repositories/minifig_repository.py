from typing import Protocol

from app.domain.entities import Minifig


class MinifigRepository(Protocol):
    def get(self, fig_num: str) -> Minifig | None: ...

    def save(self, minifig: Minifig) -> None:
        """Upsert the catalog-level minifig and its part template (no per-instance state here)."""
        ...

    def delete(self, fig_num: str) -> None:
        """Drop a catalog entry and its part template, once no instance references it."""
        ...

    def list_referenced_image_paths(self) -> set[str]:
        """Every cached image path still in use by the minifig catalog."""
        ...
