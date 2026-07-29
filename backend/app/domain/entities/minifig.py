from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.entities.part import Part


class Minifig(BaseModel):
    """Catalog-level entry: one row per fig_num, shared across all owned instances."""

    fig_num: str
    name: str
    num_parts: int | None = None
    image_path: str | None = None
    last_synced_at: datetime
    parts: list[Part] = Field(default_factory=list)
