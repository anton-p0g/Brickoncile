from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.application.use_cases.add_minifig_by_reference import (
    AddMinifigByReferenceResult,
)
from app.application.use_cases.change_minifig_fig_num import ChangeMinifigFigNumResult
from app.application.use_cases.get_collection_stats import (
    BurnUp,
    CollectionStats,
    ColorStats,
    DayBucket,
    HourBucket,
    SessionStats,
    StatusCount,
    ThemeStats,
    Totals,
    YearBucket,
)
from app.application.use_cases.get_missing_summary import PartAggregate, SourceAggregate
from app.application.use_cases.identify_minifig import (
    IdentifyMinifigResult,
    MinifigMatch,
)
from app.application.use_cases.search_parts import PartSearchResult
from app.domain.entities import (
    LegoSet,
    MinifigInstance,
    MissingPartRecord,
    Part,
    SortingStatus,
    Theme,
    resolve_root,
)


def to_image_url(image_path: str | None) -> str | None:
    return f"/static/images/{image_path}" if image_path else None


class CollectionCreateRequest(BaseModel):
    name: str


class CollectionOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    is_default: bool


class PartOut(BaseModel):
    part_num: str
    color_id: int
    color_name: str
    part_name: str
    element_id: str | None
    image_url: str | None
    quantity_required: int
    quantity_found: int
    """How many found pieces are broken. This is a subset of quantity_found."""
    quantity_broken: int
    """Pieces not confirmed present. Whether the UI calls these "missing" or "not checked yet"
    depends on the owning inventory's status."""
    quantity_unaccounted: int
    is_fully_found: bool
    is_spare: bool

    @classmethod
    def from_domain(cls, part: Part) -> "PartOut":
        return cls(
            part_num=part.part_num,
            color_id=part.color_id,
            color_name=part.color_name,
            part_name=part.name,
            element_id=part.element_id,
            image_url=to_image_url(part.image_path),
            quantity_required=part.quantity_required,
            quantity_found=part.quantity_found,
            quantity_broken=part.quantity_broken,
            quantity_unaccounted=part.quantity_unaccounted,
            is_fully_found=part.is_fully_found,
            is_spare=part.is_spare,
        )


class SetSummary(BaseModel):
    set_num: str
    name: str
    year: int | None
    image_url: str | None
    num_parts: int
    quantity_required_total: int
    quantity_found_total: int
    """Confirmed missing. Zero until sorting is finished, since unfound pieces may still be in
    the pile. Use `quantity_required_total - quantity_found_total` for what is left to check."""
    quantity_missing_total: int
    is_complete: bool
    status: SortingStatus
    sorting_finished_at: datetime | None
    added_at: datetime
    theme_id: int | None
    """The set's own theme, which is often a sub-theme ("Constraction")."""
    theme_name: str | None
    """The top of that theme's tree ("Legends of Chima"), which is how an owner groups a shelf.
    Null when the theme tree has not been cached yet, or the set has no theme upstream."""
    root_theme_id: int | None
    root_theme_name: str | None

    @classmethod
    def from_domain(cls, s: LegoSet, themes: dict[int, Theme] | None = None) -> "SetSummary":
        """`themes` is the cached theme tree keyed by id. Omitting it leaves the theme names null,
        which is the right answer for callers that have no theme cache to consult."""
        by_id = themes or {}
        own = by_id.get(s.theme_id) if s.theme_id is not None else None
        root = resolve_root(s.theme_id, by_id)
        return cls(
            set_num=s.set_num,
            name=s.name,
            year=s.year,
            image_url=to_image_url(s.image_path),
            num_parts=s.num_parts,
            quantity_required_total=s.total_required,
            quantity_found_total=s.total_found,
            quantity_missing_total=s.total_missing,
            is_complete=s.is_complete,
            status=s.status,
            sorting_finished_at=s.sorting_finished_at,
            added_at=s.added_at,
            theme_id=s.theme_id,
            theme_name=own.name if own else None,
            root_theme_id=root.id if root else None,
            root_theme_name=root.name if root else None,
        )


class SetDetail(SetSummary):
    last_synced_at: datetime
    parts: list[PartOut]

    @classmethod
    def from_domain(cls, s: LegoSet, themes: dict[int, Theme] | None = None) -> "SetDetail":
        # Reuse the summary's mapping rather than restating every field, so a field added to the
        # summary cannot be silently forgotten here.
        return cls(
            **SetSummary.from_domain(s, themes).model_dump(),
            last_synced_at=s.last_synced_at,
            parts=[PartOut.from_domain(p) for p in s.parts],
        )


class EntityTotals(BaseModel):
    """Rolled-up state returned after a change, so a client can patch a cached card in place."""

    quantity_required_total: int
    quantity_found_total: int
    quantity_missing_total: int
    is_complete: bool
    status: SortingStatus

    @classmethod
    def from_inventory(cls, inventory: LegoSet | MinifigInstance) -> "EntityTotals":
        return cls(
            quantity_required_total=inventory.total_required,
            quantity_found_total=inventory.total_found,
            quantity_missing_total=inventory.total_missing,
            is_complete=inventory.is_complete,
            status=inventory.status,
        )


class FoundDeltaRequest(BaseModel):
    """Change in confirmed-present pieces. Positive when pieces turn up while sorting, negative to
    walk that back. Clamped server-side to [0, quantity_required]."""

    found_delta: int


class PartConditionRequest(BaseModel):
    """Absolute counts from the condition editor. Broken is clamped within found server-side."""

    quantity_found: int
    quantity_broken: int


class MarkSetPartResponse(BaseModel):
    part: PartOut
    set_summary: EntityTotals


class PartFoundTarget(BaseModel):
    """One part's target found count. Clamped server-side to [0, quantity_required]."""

    part_num: str
    color_id: int
    quantity_found: int


class SetPartsFoundRequest(BaseModel):
    """Bulk counterpart to FoundDeltaRequest. Targets are absolute counts rather than deltas, so
    the same call both confirms a screenful of parts and puts the previous counts back to undo it."""

    parts: list[PartFoundTarget]


class SetPartsFoundResponse(BaseModel):
    """Only the parts that actually changed, so a client can patch its cache without a refetch."""

    parts: list[PartOut]
    summary: EntityTotals

    @classmethod
    def from_domain(cls, parts: list[Part], inventory: LegoSet | MinifigInstance) -> "SetPartsFoundResponse":
        return cls(
            parts=[PartOut.from_domain(p) for p in parts],
            summary=EntityTotals.from_inventory(inventory),
        )


class PartSourceOut(BaseModel):
    source_type: Literal["set", "minifig_instance"]
    source_id: str
    label: str
    quantity_required: int
    quantity_found: int
    quantity_unaccounted: int
    status: SortingStatus


class PartSearchResultOut(BaseModel):
    part_num: str
    color_id: int
    color_name: str
    part_name: str
    element_id: str | None
    image_url: str | None
    total_needed: int
    sources: list[PartSourceOut]

    @classmethod
    def from_use_case(cls, result: "PartSearchResult") -> "PartSearchResultOut":
        return cls(
            part_num=result.part_num,
            color_id=result.color_id,
            color_name=result.color_name,
            part_name=result.part_name,
            element_id=result.element_id,
            image_url=to_image_url(result.image_path),
            total_needed=result.total_needed,
            sources=[
                PartSourceOut(
                    source_type=s.source_type,
                    source_id=s.source_id,
                    label=s.label,
                    quantity_required=s.quantity_required,
                    quantity_found=s.quantity_found,
                    quantity_unaccounted=s.quantity_unaccounted,
                    status=s.status,
                )
                for s in result.sources
            ],
        )


class SortingStateRequest(BaseModel):
    """True to declare sorting finished (unfound pieces become confirmed missing), false to resume."""

    finished: bool


class AddSetRequest(BaseModel):
    set_num: str


class BulkAddSetsRequest(BaseModel):
    set_nums: list[str]


class BulkAddResultItem(BaseModel):
    """`set_num` is the resolved number (a bare "70202" resolves to "70202-1"), so the report
    matches what actually landed in the collection rather than echoing the raw input."""

    set_num: str
    input_set_num: str
    status: Literal["ok", "exists", "partial", "error"]
    """"partial" means the set and its parts landed but its minifigures did not — the set is in
    the collection and usable, so reporting it as a plain failure would be a lie."""
    name: str | None = None
    """Set name once it resolved, so the report reads as names rather than bare numbers.
    None for a set that failed, since nothing was fetched."""
    error: str | None = None


class BulkAddSetsResponse(BaseModel):
    results: list[BulkAddResultItem]


class AddSetResponse(BaseModel):
    """Wraps the set so a single add can say whether it landed or was already owned — the two
    are indistinguishable from the set alone, and re-adding an owned set otherwise looks like
    a silent no-op."""

    status: Literal["ok", "exists"]
    set: SetDetail
    warning: str | None = None
    """Set when the add succeeded with something missing — currently only a minifig roster that
    could not be fetched. Not an error: the set is in the collection either way."""


class HistoryEntryOut(BaseModel):
    part_num: str
    color_id: int
    action: str
    quantity_before: int
    quantity_after: int
    timestamp: datetime

    @classmethod
    def from_domain(cls, record: MissingPartRecord) -> "HistoryEntryOut":
        return cls(
            part_num=record.part_num,
            color_id=record.color_id,
            action=record.action,
            quantity_before=record.quantity_before,
            quantity_after=record.quantity_after,
            timestamp=record.timestamp,
        )


class MinifigInstanceSummary(BaseModel):
    instance_id: str
    fig_num: str
    fig_name: str
    image_url: str | None
    source_set_num: str | None
    """Null for a loose minifig, owned without a set to attribute it to."""
    source_set_name: str | None
    quantity_required_total: int
    quantity_found_total: int
    quantity_missing_total: int
    is_complete: bool
    status: SortingStatus
    sorting_finished_at: datetime | None
    added_at: datetime

    @classmethod
    def from_domain(cls, instance: MinifigInstance, source_set_name: str | None) -> "MinifigInstanceSummary":
        return cls(
            instance_id=instance.id,
            fig_num=instance.fig_num,
            fig_name=instance.fig_name,
            image_url=to_image_url(instance.image_path),
            source_set_num=instance.source_set_num,
            source_set_name=source_set_name,
            quantity_required_total=instance.total_required,
            quantity_found_total=instance.total_found,
            quantity_missing_total=instance.total_missing,
            is_complete=instance.is_complete,
            status=instance.status,
            sorting_finished_at=instance.sorting_finished_at,
            added_at=instance.added_at,
        )


class MinifigInstanceDetail(MinifigInstanceSummary):
    parts: list[PartOut]

    @classmethod
    def from_domain(cls, instance: MinifigInstance, source_set_name: str | None) -> "MinifigInstanceDetail":
        # See SetDetail.from_domain: reuse the summary mapping instead of restating it.
        return cls(
            **MinifigInstanceSummary.from_domain(instance, source_set_name).model_dump(),
            parts=[PartOut.from_domain(p) for p in instance.parts],
        )


class MarkMinifigPartResponse(BaseModel):
    part: PartOut
    instance_summary: EntityTotals


class OwnedInstanceRefOut(BaseModel):
    instance_id: str
    source_set_num: str | None
    source_set_name: str | None
    is_complete: bool
    """Whether this particular copy is already accounted for. With the same fig listed twice in a
    set, this is what says which copy the photographed figure should be matched to."""
    quantity_found_total: int
    quantity_required_total: int


class MinifigMatchOut(BaseModel):
    fig_num: str
    name: str
    num_parts: int | None
    image_url: str | None
    """Remote catalog image, not a cached one: nothing is downloaded until a match is confirmed."""
    score: float
    recognized_as: str
    recognition_image_url: str | None
    reference_url: str | None
    owned_instances: list[OwnedInstanceRefOut]

    @classmethod
    def from_use_case(cls, match: "MinifigMatch") -> "MinifigMatchOut":
        return cls(
            fig_num=match.fig_num,
            name=match.name,
            num_parts=match.num_parts,
            image_url=match.image_url,
            score=match.score,
            recognized_as=match.recognized_as,
            recognition_image_url=match.recognition_image_url,
            reference_url=match.reference_url,
            owned_instances=[
                OwnedInstanceRefOut(
                    instance_id=o.instance_id,
                    source_set_num=o.source_set_num,
                    source_set_name=o.source_set_name,
                    is_complete=o.is_complete,
                    quantity_found_total=o.quantity_found_total,
                    quantity_required_total=o.quantity_required_total,
                )
                for o in match.owned_instances
            ],
        )


class RecognitionOut(BaseModel):
    """What the recogniser saw, independent of whether it resolved to a catalog entry."""

    external_id: str
    name: str
    score: float
    image_url: str | None
    reference_url: str | None


class IdentifyMinifigResponse(BaseModel):
    recognitions: list[RecognitionOut]
    matches: list[MinifigMatchOut]

    @classmethod
    def from_use_case(cls, result: "IdentifyMinifigResult") -> "IdentifyMinifigResponse":
        return cls(
            recognitions=[
                RecognitionOut(
                    external_id=r.external_id,
                    name=r.name,
                    score=r.score,
                    image_url=r.image_url,
                    reference_url=r.reference_url,
                )
                for r in result.recognitions
            ],
            matches=[MinifigMatchOut.from_use_case(m) for m in result.matches],
        )


class AddLooseMinifigRequest(BaseModel):
    """`fig_num` is the catalog id the owner confirmed from the identification candidates."""

    fig_num: str


class AddMinifigByReferenceRequest(BaseModel):
    """`reference` is whatever the owner pasted — a Rebrickable link, a fig ID, a BrickLink link."""

    reference: str


class AddMinifigByReferenceResponse(BaseModel):
    instance: MinifigInstanceDetail
    already_owned_count: int
    """Copies owned before this one, so the UI can confirm a deliberate duplicate rather than let a
    list pasted twice pass unremarked."""

    @classmethod
    def from_use_case(cls, result: AddMinifigByReferenceResult) -> "AddMinifigByReferenceResponse":
        return cls(
            # Nothing added this way belongs to a set, so there is never a source set to name.
            instance=MinifigInstanceDetail.from_domain(result.instance, source_set_name=None),
            already_owned_count=result.already_owned_count,
        )


class BulkAddMinifigsRequest(BaseModel):
    references: list[str]


class BulkAddMinifigResultItem(BaseModel):
    """One pasted line's outcome. `input_reference` is echoed verbatim so a long paste's failures
    can be matched back to the lines that produced them, and put back in the box to be corrected."""

    input_reference: str
    status: Literal["ok", "error"]
    fig_num: str | None = None
    fig_name: str | None = None
    instance_id: str | None = None
    already_owned_count: int = 0
    error: str | None = None


class BulkAddMinifigsResponse(BaseModel):
    results: list[BulkAddMinifigResultItem]


class ChangeMinifigFigNumRequest(BaseModel):
    """`fig_num` is the corrected catalog id for a loose minifig filed under the wrong one."""

    fig_num: str


class ChangeMinifigFigNumResponse(BaseModel):
    """`instance` is where the figure lives now, which is rarely where the request was addressed:
    correcting the id rebuilds the record, and a set that was waiting for this figure takes it over
    entirely. `outcome` is what the caller needs to know which of those happened, since only
    `unchanged` leaves the edited instance id still valid."""

    outcome: Literal["unchanged", "replaced", "claimed_by_set"]
    instance: MinifigInstanceDetail
    previous_instance_id: str
    claimed_set_num: str | None
    claimed_set_name: str | None

    @classmethod
    def from_use_case(
        cls, result: ChangeMinifigFigNumResult, source_set_name: str | None
    ) -> "ChangeMinifigFigNumResponse":
        return cls(
            outcome=result.outcome,
            instance=MinifigInstanceDetail.from_domain(result.instance, source_set_name=source_set_name),
            previous_instance_id=result.previous_instance_id,
            claimed_set_num=result.claimed_set_num,
            claimed_set_name=source_set_name if result.claimed_set_num else None,
        )


class ContributorOut(BaseModel):
    source_type: Literal["set", "minifig_instance"]
    source_id: str
    label: str
    name: str
    reference: str
    image_url: str | None
    quantity_found: int
    quantity_missing: int
    quantity_broken: int
    quantity_needed: int


class PartAggregateOut(BaseModel):
    part_num: str
    color_id: int
    part_name: str
    color_name: str
    image_url: str | None
    total_missing: int
    total_broken: int
    total_needed: int
    contributors: list[ContributorOut]

    @classmethod
    def from_use_case(cls, aggregate: "PartAggregate") -> "PartAggregateOut":
        return cls(
            part_num=aggregate.part_num,
            color_id=aggregate.color_id,
            part_name=aggregate.part_name,
            color_name=aggregate.color_name,
            image_url=to_image_url(aggregate.image_path),
            total_missing=aggregate.total_missing,
            total_broken=aggregate.total_broken,
            total_needed=aggregate.total_needed,
            contributors=[
                ContributorOut(
                    source_type=c.source_type,
                    source_id=c.source_id,
                    label=c.label,
                    name=c.name,
                    reference=c.reference,
                    image_url=to_image_url(c.image_path),
                    quantity_found=c.quantity_found,
                    quantity_missing=c.quantity_missing,
                    quantity_broken=c.quantity_broken,
                    quantity_needed=c.quantity_needed,
                )
                for c in aggregate.contributors
            ],
        )


class SourceItemOut(BaseModel):
    part_num: str
    color_id: int
    part_name: str
    color_name: str
    image_url: str | None
    quantity_missing: int
    quantity_found: int
    quantity_broken: int
    quantity_needed: int


class SourceAggregateOut(BaseModel):
    source_type: Literal["set", "minifig_instance"]
    source_id: str
    label: str
    name: str
    reference: str
    image_url: str | None
    items: list[SourceItemOut]
    total_missing: int
    total_broken: int
    total_needed: int

    @classmethod
    def from_use_case(cls, aggregate: "SourceAggregate") -> "SourceAggregateOut":
        return cls(
            source_type=aggregate.source_type,
            source_id=aggregate.source_id,
            label=aggregate.label,
            name=aggregate.name,
            reference=aggregate.reference,
            image_url=to_image_url(aggregate.image_path),
            items=[
                SourceItemOut(
                    part_num=i.part_num,
                    color_id=i.color_id,
                    part_name=i.part_name,
                    color_name=i.color_name,
                    image_url=to_image_url(i.image_path),
                    quantity_missing=i.quantity_missing,
                    quantity_found=i.quantity_found,
                    quantity_broken=i.quantity_broken,
                    quantity_needed=i.quantity_needed,
                )
                for i in aggregate.items
            ],
            total_missing=aggregate.total_missing,
            total_broken=aggregate.total_broken,
            total_needed=aggregate.total_needed,
        )


class SetProgressOut(BaseModel):
    set_num: str
    name: str
    year: int | None
    image_url: str | None
    num_parts: int
    quantity_required: int
    quantity_found: int
    quantity_missing: int
    status: SortingStatus
    root_theme_name: str | None


class CommonPartOut(BaseModel):
    part_num: str
    color_id: int
    part_name: str
    color_name: str
    image_url: str | None
    set_count: int
    quantity_required: int


class MissingPartStatOut(BaseModel):
    part_num: str
    color_id: int
    part_name: str
    color_name: str
    image_url: str | None
    total_missing: int
    source_count: int


class DuplicatedFigOut(BaseModel):
    fig_num: str
    fig_name: str
    image_url: str | None
    count: int


class LooseFigOut(BaseModel):
    instance_id: str
    fig_num: str
    fig_name: str
    image_url: str | None
    status: SortingStatus


class MinifigStatsOut(BaseModel):
    total: int
    loose: int
    from_set: int
    distinct_figs: int
    complete: int
    most_duplicated: list[DuplicatedFigOut]
    loose_figs: list[LooseFigOut]


class CollectionStatsOut(BaseModel):
    """The dashboard payload.

    Sections carrying a cached image are restated here to turn `image_path` into a servable URL,
    the way every other response does. The rest are plain numbers with nothing to translate, so
    they travel as the use case computed them rather than being retyped field for field.
    """

    totals: Totals
    status_breakdown: list[StatusCount]
    sets: list[SetProgressOut]
    themes: list[ThemeStats]
    colors: list[ColorStats]
    common_parts: list[CommonPartOut]
    top_missing: list[MissingPartStatOut]
    burn_up: BurnUp
    activity_by_hour: list[HourBucket]
    activity_by_day: list[DayBucket]
    sessions: SessionStats
    years: list[YearBucket]
    minifigs: MinifigStatsOut

    @classmethod
    def from_use_case(cls, stats: "CollectionStats") -> "CollectionStatsOut":
        return cls(
            totals=stats.totals,
            status_breakdown=stats.status_breakdown,
            sets=[
                SetProgressOut(
                    set_num=s.set_num,
                    name=s.name,
                    year=s.year,
                    image_url=to_image_url(s.image_path),
                    num_parts=s.num_parts,
                    quantity_required=s.quantity_required,
                    quantity_found=s.quantity_found,
                    quantity_missing=s.quantity_missing,
                    status=s.status,
                    root_theme_name=s.root_theme_name,
                )
                for s in stats.sets
            ],
            themes=stats.themes,
            colors=stats.colors,
            common_parts=[
                CommonPartOut(
                    part_num=c.part_num,
                    color_id=c.color_id,
                    part_name=c.part_name,
                    color_name=c.color_name,
                    image_url=to_image_url(c.image_path),
                    set_count=c.set_count,
                    quantity_required=c.quantity_required,
                )
                for c in stats.common_parts
            ],
            top_missing=[
                MissingPartStatOut(
                    part_num=m.part_num,
                    color_id=m.color_id,
                    part_name=m.part_name,
                    color_name=m.color_name,
                    image_url=to_image_url(m.image_path),
                    total_missing=m.total_missing,
                    source_count=m.source_count,
                )
                for m in stats.top_missing
            ],
            burn_up=stats.burn_up,
            activity_by_hour=stats.activity_by_hour,
            activity_by_day=stats.activity_by_day,
            sessions=stats.sessions,
            years=stats.years,
            minifigs=MinifigStatsOut(
                total=stats.minifigs.total,
                loose=stats.minifigs.loose,
                from_set=stats.minifigs.from_set,
                distinct_figs=stats.minifigs.distinct_figs,
                complete=stats.minifigs.complete,
                most_duplicated=[
                    DuplicatedFigOut(
                        fig_num=d.fig_num,
                        fig_name=d.fig_name,
                        image_url=to_image_url(d.image_path),
                        count=d.count,
                    )
                    for d in stats.minifigs.most_duplicated
                ],
                loose_figs=[
                    LooseFigOut(
                        instance_id=f.instance_id,
                        fig_num=f.fig_num,
                        fig_name=f.fig_name,
                        image_url=to_image_url(f.image_path),
                        status=f.status,
                    )
                    for f in stats.minifigs.loose_figs
                ],
            ),
        )
