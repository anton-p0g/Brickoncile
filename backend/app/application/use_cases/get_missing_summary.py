from typing import Literal

from pydantic import BaseModel

from app.domain.repositories import MinifigInstanceRepository, SetRepository


class Contributor(BaseModel):
    source_type: Literal["set", "minifig_instance"]
    source_id: str
    label: str
    """Single-line description, for the CSV and clipboard exports."""
    name: str
    """The set's or figure's own name, for a UI that lays the two out separately."""
    reference: str
    """The catalog id worth showing: a set number, or a fig number. Distinct from source_id, which
    for a minifig is an internal instance id and means nothing to the owner."""
    image_path: str | None
    quantity_found: int
    quantity_missing: int
    quantity_broken: int

    @property
    def quantity_needed(self) -> int:
        return self.quantity_missing + self.quantity_broken


class PartAggregate(BaseModel):
    part_num: str
    color_id: int
    part_name: str
    color_name: str
    image_path: str | None
    total_missing: int
    total_broken: int
    contributors: list[Contributor]

    @property
    def total_needed(self) -> int:
        return self.total_missing + self.total_broken


class SourceItem(BaseModel):
    part_num: str
    color_id: int
    part_name: str
    color_name: str
    image_path: str | None
    quantity_missing: int
    quantity_found: int
    quantity_broken: int

    @property
    def quantity_needed(self) -> int:
        return self.quantity_missing + self.quantity_broken


class SourceAggregate(BaseModel):
    source_type: Literal["set", "minifig_instance"]
    source_id: str
    label: str
    name: str
    reference: str
    """See Contributor.reference."""
    image_path: str | None
    items: list[SourceItem]
    total_missing: int
    total_broken: int

    @property
    def total_needed(self) -> int:
        return self.total_missing + self.total_broken


class _Contribution(BaseModel):
    source_type: Literal["set", "minifig_instance"]
    source_id: str
    label: str
    name: str
    reference: str
    image_path: str | None
    part_num: str
    color_id: int
    part_name: str
    color_name: str
    part_image_path: str | None
    quantity_missing: int
    quantity_found: int
    quantity_broken: int


class GetMissingSummaryUseCase:
    """Aggregates every part that needs replacing across all sets and minifig instances,
    grouped either by part (default, for reordering) or by owning source.

    Only inventories whose sorting is finished contribute. A set still being worked through has
    pieces that simply have not turned up yet, and counting those would fill the shopping list with
    bricks that are sitting in the unsorted pile. Missing and broken counts remain separate so a
    caller can explain why each replacement is needed.
    """

    def __init__(self, set_repo: SetRepository, instance_repo: MinifigInstanceRepository):
        self.set_repo = set_repo
        self.instance_repo = instance_repo

    def execute(self, group_by: Literal["part", "set"] = "part") -> list[PartAggregate] | list[SourceAggregate]:
        contributions = self._collect_contributions()
        if group_by == "set":
            return self._group_by_source(contributions)
        return self._group_by_part(contributions)

    def _collect_contributions(self) -> list[_Contribution]:
        contributions: list[_Contribution] = []

        for lego_set in self.set_repo.list_all():
            if not lego_set.is_sorted:
                continue
            for part in lego_set.parts:
                if part.is_spare or (
                    part.quantity_unaccounted <= 0 and part.quantity_broken <= 0
                ):
                    continue
                contributions.append(
                    _Contribution(
                        source_type="set",
                        source_id=lego_set.set_num,
                        label=lego_set.set_num,
                        name=lego_set.name,
                        reference=lego_set.set_num,
                        image_path=lego_set.image_path,
                        part_num=part.part_num,
                        color_id=part.color_id,
                        part_name=part.name,
                        color_name=part.color_name,
                        part_image_path=part.image_path,
                        quantity_missing=part.quantity_unaccounted,
                        quantity_found=part.quantity_found,
                        quantity_broken=part.quantity_broken,
                    )
                )

        for instance in self.instance_repo.list_all():
            if not instance.is_sorted:
                continue
            for part in instance.parts:
                if part.quantity_unaccounted <= 0 and part.quantity_broken <= 0:
                    continue
                contributions.append(
                    _Contribution(
                        source_type="minifig_instance",
                        source_id=instance.id,
                        label=f"{instance.fig_num} (from {instance.source_set_num or 'loose'})",
                        name=instance.fig_name,
                        reference=instance.fig_num,
                        image_path=instance.image_path,
                        part_num=part.part_num,
                        color_id=part.color_id,
                        part_name=part.name,
                        color_name=part.color_name,
                        part_image_path=part.image_path,
                        quantity_missing=part.quantity_unaccounted,
                        quantity_found=part.quantity_found,
                        quantity_broken=part.quantity_broken,
                    )
                )

        return contributions

    def _group_by_part(self, contributions: list[_Contribution]) -> list[PartAggregate]:
        buckets: dict[tuple[str, int], list[_Contribution]] = {}
        for c in contributions:
            buckets.setdefault((c.part_num, c.color_id), []).append(c)

        aggregates = [
            PartAggregate(
                part_num=part_num,
                color_id=color_id,
                part_name=items[0].part_name,
                color_name=items[0].color_name,
                image_path=items[0].part_image_path,
                total_missing=sum(i.quantity_missing for i in items),
                total_broken=sum(i.quantity_broken for i in items),
                contributors=[
                    Contributor(
                        source_type=i.source_type,
                        source_id=i.source_id,
                        label=i.label,
                        name=i.name,
                        reference=i.reference,
                        image_path=i.image_path,
                        quantity_found=i.quantity_found,
                        quantity_missing=i.quantity_missing,
                        quantity_broken=i.quantity_broken,
                    )
                    for i in items
                ],
            )
            for (part_num, color_id), items in buckets.items()
        ]
        aggregates.sort(key=lambda a: a.total_needed, reverse=True)
        return aggregates

    def _group_by_source(self, contributions: list[_Contribution]) -> list[SourceAggregate]:
        buckets: dict[tuple[str, str], list[_Contribution]] = {}
        for c in contributions:
            buckets.setdefault((c.source_type, c.source_id), []).append(c)

        aggregates = [
            SourceAggregate(
                source_type=items[0].source_type,
                source_id=source_id,
                label=items[0].label,
                name=items[0].name,
                reference=items[0].reference,
                image_path=items[0].image_path,
                items=[
                    SourceItem(
                        part_num=i.part_num,
                        color_id=i.color_id,
                        part_name=i.part_name,
                        color_name=i.color_name,
                        image_path=i.part_image_path,
                        quantity_missing=i.quantity_missing,
                        quantity_found=i.quantity_found,
                        quantity_broken=i.quantity_broken,
                    )
                    for i in items
                ],
                total_missing=sum(i.quantity_missing for i in items),
                total_broken=sum(i.quantity_broken for i in items),
            )
            for (_, source_id), items in buckets.items()
        ]
        aggregates.sort(key=lambda a: a.total_needed, reverse=True)
        return aggregates
