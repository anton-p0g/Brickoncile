from typing import Literal

from pydantic import BaseModel

from app.application.use_cases.add_loose_minifig import AddLooseMinifigUseCase
from app.application.use_cases.delete_minifig_instance import (
    DeleteMinifigInstanceUseCase,
)
from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.application.use_cases.mark_minifig_instance_found import (
    MarkMinifigInstanceFoundUseCase,
)
from app.domain.entities import MinifigInstance
from app.domain.errors import EntityNotFoundError, EntityOwnedBySetError
from app.domain.repositories import MinifigInstanceRepository

ChangeOutcome = Literal["unchanged", "replaced", "claimed_by_set"]


class ChangeMinifigFigNumResult(BaseModel):
    instance: MinifigInstance
    """What the collection now holds for the figure in hand — which is a different record than the
    one edited whenever the outcome is not `unchanged`."""
    outcome: ChangeOutcome
    previous_instance_id: str
    claimed_set_num: str | None = None
    """The set that took the figure over, when it turned out to be expecting one."""


class ChangeMinifigFigNumUseCase:
    """Correct the catalog id of a loose minifig that was filed under the wrong one.

    A misidentified photo is the usual cause: the figure in hand is real, but the fig_num beside it
    describes something else, and with it the whole parts list being sorted against. Correcting it
    means replacing that parts list, so this does not edit the record in place — it adds the figure
    under the right id and removes the wrong one. The id therefore changes, and callers holding the
    old one are told so by `previous_instance_id`.

    The correction can also reveal the figure was never loose at all. If an owned set lists this
    fig_num and is still waiting for its copy, that waiting copy is the figure in hand: filing a
    loose one beside it would leave the set short and the collection holding two. So the set's copy
    is confirmed found — the same resolution the identify flow offers for a photographed figure —
    and the loose record goes away.

    Only loose instances can be edited. One that came from a set is that set's roster to state, and
    `SyncMinifigRosterUseCase` would restore whatever a resync found missing.
    """

    def __init__(
        self,
        instance_repo: MinifigInstanceRepository,
        fetch_minifig: FetchMinifigUseCase,
        add_loose: AddLooseMinifigUseCase,
        delete_instance: DeleteMinifigInstanceUseCase,
        mark_found: MarkMinifigInstanceFoundUseCase,
    ):
        self.instance_repo = instance_repo
        self.fetch_minifig = fetch_minifig
        self.add_loose = add_loose
        self.delete_instance = delete_instance
        self.mark_found = mark_found

    async def execute(self, instance_id: str, fig_num: str) -> ChangeMinifigFigNumResult:
        instance = self.instance_repo.get(instance_id)
        if instance is None:
            raise EntityNotFoundError(f"minifig instance {instance_id} not found")
        if instance.source_set_num is not None:
            raise EntityOwnedBySetError(
                f"minifig instance {instance_id} came from set {instance.source_set_num}; "
                "its fig_num is that set's roster to state"
            )

        # Before anything is written: this validates the id against the catalog, and settles its
        # canonical spelling, which is what the search for a waiting copy has to match on. The
        # entry is cached by the time the replacement is added, so that add costs no second fetch.
        minifig = await self.fetch_minifig.execute(fig_num.strip())

        claim = self._pending_set_copy(minifig.fig_num)
        if claim is not None:
            claimed = self.mark_found.execute(claim.id)
            self.delete_instance.execute(instance_id)
            return ChangeMinifigFigNumResult(
                instance=claimed,
                outcome="claimed_by_set",
                previous_instance_id=instance_id,
                claimed_set_num=claimed.source_set_num,
            )

        # Nothing to correct and nothing waiting for it: leave the record and its sorting progress
        # alone rather than rebuilding an identical one from scratch.
        if minifig.fig_num == instance.fig_num:
            return ChangeMinifigFigNumResult(
                instance=instance, outcome="unchanged", previous_instance_id=instance_id
            )

        # Added before the old one goes, so a shared part image is never unlinked from under it.
        replacement = await self.add_loose.execute(minifig.fig_num)
        self.delete_instance.execute(instance_id)
        return ChangeMinifigFigNumResult(
            instance=replacement, outcome="replaced", previous_instance_id=instance_id
        )

    def _pending_set_copy(self, fig_num: str) -> MinifigInstance | None:
        """The copy an owned set is still waiting for, if any.

        A set copy already complete is a figure the owner has already accounted for, so a second one
        in hand is a genuine duplicate and stays loose. Where several sets are waiting the earliest
        acquired wins, since nothing distinguishes them and that is the one that has waited longest.
        """
        waiting = [
            candidate
            for candidate in self.instance_repo.list_by_fig_num(fig_num)
            if candidate.source_set_num is not None and not candidate.is_complete
        ]
        if not waiting:
            return None
        return min(waiting, key=lambda i: (i.added_at, i.source_set_num or "", i.id))
