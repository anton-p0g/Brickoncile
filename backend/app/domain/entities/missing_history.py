from datetime import datetime
from typing import Literal

from pydantic import BaseModel

EntityType = Literal["set", "minifig_instance"]
MissingAction = Literal["marked_missing", "marked_found"]


class MissingPartRecord(BaseModel):
    entity_type: EntityType
    entity_id: str
    part_num: str
    color_id: int
    action: MissingAction
    quantity_before: int
    quantity_after: int
    timestamp: datetime
