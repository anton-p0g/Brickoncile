from pydantic import BaseModel


class Part(BaseModel):
    """A part line in a set or minifig inventory.

    `quantity_found` is the tracked value: pieces physically confirmed present while sorting.
    `quantity_broken` is a condition within that found count, never an additional piece. Missing
    is derived from found rather than stored alongside it, so broken pieces are not called missing.
    """

    part_num: str
    color_id: int
    color_name: str
    name: str
    element_id: str | None = None
    quantity_required: int
    quantity_found: int = 0
    quantity_broken: int = 0
    image_path: str | None = None
    is_spare: bool = False

    @property
    def quantity_unaccounted(self) -> int:
        """Pieces not confirmed present yet. This only means "missing" once the owner has finished
        sorting the set; until then it means "not checked yet"."""
        return max(0, self.quantity_required - self.quantity_found)

    @property
    def is_fully_found(self) -> bool:
        return self.quantity_found >= self.quantity_required
