from datetime import datetime
from typing import Literal

SortingStatus = Literal["not_started", "sorting", "sorted", "complete"]


def derive_status(total_required: int, total_found: int, sorting_finished_at: datetime | None) -> SortingStatus:
    """Where an inventory sits in the sorting workflow.

    - `complete`  every required piece is confirmed present, so there is nothing left to find.
    - `sorted`    the owner declared sorting finished, so whatever is unfound is confirmed missing.
    - `sorting`   part-way through checking the pile.
    - `not_started` nothing confirmed yet, so it has not been touched.

    `complete` deliberately outranks the finished flag: if every piece turned up, the inventory is
    complete whether or not the owner ever pressed "finish sorting".
    """
    if total_found >= total_required:
        return "complete"
    if sorting_finished_at is not None:
        return "sorted"
    return "sorting" if total_found > 0 else "not_started"
