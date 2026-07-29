from typing import Literal

from pydantic import BaseModel

from app.domain.entities import LegoSet, MinifigInstance, SortingStatus
from app.domain.repositories import MinifigInstanceRepository, SetRepository

DEFAULT_LIMIT = 50


class PartSource(BaseModel):
    """One inventory that contains the part, and where it stands there."""

    source_type: Literal["set", "minifig_instance"]
    source_id: str
    label: str
    quantity_required: int
    quantity_found: int
    """Pieces still to account for. Reads as "needs this many" while sorting, and as "confirmed
    missing" once that inventory's sort is finished; `status` says which."""
    quantity_unaccounted: int
    status: SortingStatus


class PartSearchResult(BaseModel):
    part_num: str
    color_id: int
    color_name: str
    part_name: str
    element_id: str | None
    image_path: str | None
    """Summed across every source that still wants a copy. Zero means the brick is fully accounted
    for everywhere it appears, which is the "put it in the spares bin" answer."""
    total_needed: int
    sources: list[PartSource]


class SearchPartsUseCase:
    """Answer "which of my sets needs this brick?".

    Every other screen starts from an inventory and works toward the pile. Sorting a mixed
    collection runs the other way: a brick is in hand and the question is where it belongs. That
    makes this a lookup across all inventories at once, keyed on the part rather than the set.

    Unlike the shopping list, this deliberately includes inventories still being sorted (that is
    the common case here) and parts that are already fully found, so "nothing needs this" is a
    real answer rather than an empty result indistinguishable from "not in your collection".
    """

    def __init__(self, set_repo: SetRepository, instance_repo: MinifigInstanceRepository):
        self.set_repo = set_repo
        self.instance_repo = instance_repo

    def execute(
        self, query: str, color_id: int | None = None, limit: int = DEFAULT_LIMIT
    ) -> list[PartSearchResult]:
        needle = query.strip().lower()
        if not needle:
            return []

        results: dict[tuple[str, int], PartSearchResult] = {}

        for lego_set in self.set_repo.list_all():
            self._collect(results, lego_set, "set", lego_set.set_num, lego_set.set_num, needle, color_id)

        for instance in self.instance_repo.list_all():
            origin = instance.source_set_num or "loose"
            label = f"{instance.fig_name} (from {origin})"
            self._collect(results, instance, "minifig_instance", instance.id, label, needle, color_id)

        ordered = sorted(results.values(), key=lambda r: self._rank(r, needle))
        return ordered[:limit]

    @staticmethod
    def _rank(result: PartSearchResult, needle: str) -> tuple:
        """Closeness of the identifier first, then what is still wanted.

        Typing a part number should not rank a loosely related part above the exact one just because
        more sets happen to want it. A search for "4519" matches part 60176 too, whose element id is
        4519225, and that must stay below the part actually numbered 4519.
        """
        part_num = result.part_num.lower()
        return (
            part_num != needle,
            not part_num.startswith(needle),
            -result.total_needed,
            result.part_num,
            result.color_name,
        )

    def _collect(
        self,
        results: dict[tuple[str, int], PartSearchResult],
        inventory: LegoSet | MinifigInstance,
        source_type: Literal["set", "minifig_instance"],
        source_id: str,
        label: str,
        needle: str,
        color_id: int | None,
    ) -> None:
        for part in inventory.parts:
            # Spares are not tracked, and a pruned part (no longer in the upstream list) is not
            # something any set can still want.
            if part.is_spare or part.quantity_required == 0:
                continue
            if color_id is not None and part.color_id != color_id:
                continue
            if not self._matches(part.part_num, part.name, part.element_id, needle):
                continue

            key = (part.part_num, part.color_id)
            result = results.get(key)
            if result is None:
                result = PartSearchResult(
                    part_num=part.part_num,
                    color_id=part.color_id,
                    color_name=part.color_name,
                    part_name=part.name,
                    element_id=part.element_id,
                    image_path=part.image_path,
                    total_needed=0,
                    sources=[],
                )
                results[key] = result

            # An inventory with no image cached for this part should not leave the row blank when
            # another one has it.
            if result.image_path is None:
                result.image_path = part.image_path

            result.total_needed += part.quantity_unaccounted
            result.sources.append(
                PartSource(
                    source_type=source_type,
                    source_id=source_id,
                    label=label,
                    quantity_required=part.quantity_required,
                    quantity_found=part.quantity_found,
                    quantity_unaccounted=part.quantity_unaccounted,
                    status=inventory.status,
                )
            )

    @staticmethod
    def _matches(part_num: str, part_name: str, element_id: str | None, needle: str) -> bool:
        """Part number first: it is the one identifier moulded into the brick itself, so it is what
        someone holding the piece can actually read off it. Name and element id widen the net for
        the common case of not being able to."""
        if needle in part_num.lower() or needle in part_name.lower():
            return True
        return element_id is not None and needle in element_id.lower()
