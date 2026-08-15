from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from typing import Literal

from pydantic import BaseModel

from app.application.use_cases.get_missing_summary import GetMissingSummaryUseCase
from app.domain.entities import (
    LegoSet,
    MinifigInstance,
    MissingPartRecord,
    Part,
    SortingStatus,
    resolve_root,
)
from app.domain.repositories import (
    MinifigInstanceRepository,
    MissingHistoryRepository,
    SetRepository,
    ThemeRepository,
)

STATUS_ORDER: tuple[SortingStatus, ...] = ("not_started", "sorting", "sorted", "complete")

"""A pause longer than this ends a sorting session. Half an hour is long enough to cover looking a
part up or refilling a tray, and short enough that yesterday's sort is never joined to today's."""
SESSION_GAP = timedelta(minutes=30)

"""Above this span the burn-up switches from hourly to daily buckets. Hourly keeps the curve
detailed while a collection is young; past two months the daily curve says the same thing in a
fraction of the points."""
HOURLY_BURN_UP_MAX_SPAN = timedelta(days=60)

TOP_MISSING_LIMIT = 12
COMMON_PARTS_LIMIT = 15
DUPLICATED_FIGS_LIMIT = 5


class Totals(BaseModel):
    """Raw counts only. Completion is deliberately left as a required/found pair rather than a
    percentage, so the UI applies the same rounding rule it uses on every other screen."""

    sets: int
    minifig_instances: int
    quantity_required: int
    quantity_found: int
    """Confirmed missing across finished inventories. See LegoSet.total_missing."""
    quantity_missing: int
    distinct_parts: int
    distinct_colors: int


class StatusCount(BaseModel):
    status: SortingStatus
    sets: int
    minifig_instances: int


class SetProgress(BaseModel):
    """One set, flattened for the completion grid and the size/completion scatter."""

    set_num: str
    name: str
    year: int | None
    image_path: str | None
    num_parts: int
    quantity_required: int
    quantity_found: int
    quantity_missing: int
    status: SortingStatus
    root_theme_name: str | None


class ThemeStats(BaseModel):
    """Rolled up to the *root* theme, which is how a shelf is organised. See Theme.resolve_root."""

    theme_name: str | None
    sets: int
    quantity_required: int
    quantity_found: int
    quantity_missing: int


class ColorStats(BaseModel):
    color_id: int
    color_name: str
    quantity_required: int
    quantity_found: int
    distinct_parts: int


class CommonPart(BaseModel):
    """A part/colour appearing across many sets — the ones worth keeping their own bin for."""

    part_num: str
    color_id: int
    part_name: str
    color_name: str
    image_path: str | None
    set_count: int
    quantity_required: int


class MissingPartStat(BaseModel):
    part_num: str
    color_id: int
    part_name: str
    color_name: str
    image_path: str | None
    total_missing: int
    source_count: int


class BurnUpPoint(BaseModel):
    timestamp: datetime
    quantity_found: int


class BurnUp(BaseModel):
    """Cumulative pieces confirmed present over time, replayed from the audit trail. Exact rather
    than sampled: every find is recorded with its before/after count, so the last point equals the
    collection's current found total."""

    granularity: Literal["hour", "day"]
    points: list[BurnUpPoint]


class HourBucket(BaseModel):
    hour: int
    events: int
    pieces: int


class DayBucket(BaseModel):
    day: date
    events: int
    pieces: int


class SessionStats(BaseModel):
    """Sorting runs, inferred by clustering finds that are less than SESSION_GAP apart."""

    count: int
    total_minutes: int
    longest_minutes: int
    pieces_per_session: int
    pieces_per_hour: int


class YearBucket(BaseModel):
    year: int | None
    sets: int
    quantity_required: int


class DuplicatedFig(BaseModel):
    fig_num: str
    fig_name: str
    image_path: str | None
    count: int


class MinifigStats(BaseModel):
    total: int
    loose: int
    from_set: int
    distinct_figs: int
    complete: int
    most_duplicated: list[DuplicatedFig]


class CollectionStats(BaseModel):
    totals: Totals
    status_breakdown: list[StatusCount]
    sets: list[SetProgress]
    themes: list[ThemeStats]
    colors: list[ColorStats]
    common_parts: list[CommonPart]
    top_missing: list[MissingPartStat]
    burn_up: BurnUp
    activity_by_hour: list[HourBucket]
    activity_by_day: list[DayBucket]
    sessions: SessionStats
    years: list[YearBucket]
    minifigs: MinifigStats


def _tracked(parts: list[Part]) -> list[Part]:
    """Spares are extras rather than part of the build, and are excluded from every total here for
    the same reason the domain entities exclude them."""
    return [p for p in parts if not p.is_spare]


class GetCollectionStatsUseCase:
    """Every number behind the dashboard, computed in one pass over the collection.

    The whole collection is loaded into memory rather than aggregated in SQL. That keeps the
    counting rules in one place — spares excluded, missing only once sorting is finished — instead
    of restating them in a query language where they could quietly drift from the domain. A
    collection is a few thousand part rows, which is nothing to walk.
    """

    def __init__(
        self,
        set_repo: SetRepository,
        instance_repo: MinifigInstanceRepository,
        history_repo: MissingHistoryRepository,
        theme_repo: ThemeRepository,
        missing_summary: GetMissingSummaryUseCase,
    ):
        self.set_repo = set_repo
        self.instance_repo = instance_repo
        self.history_repo = history_repo
        self.theme_repo = theme_repo
        self.missing_summary = missing_summary

    def execute(self) -> CollectionStats:
        sets = self.set_repo.list_all()
        instances = self.instance_repo.list_all()
        history = self.history_repo.list_all()
        themes = self.theme_repo.get_by_id()

        set_progress = [
            SetProgress(
                set_num=s.set_num,
                name=s.name,
                year=s.year,
                image_path=s.image_path,
                num_parts=s.num_parts,
                quantity_required=s.total_required,
                quantity_found=s.total_found,
                quantity_missing=s.total_missing,
                status=s.status,
                root_theme_name=(root.name if (root := resolve_root(s.theme_id, themes)) else None),
            )
            for s in sets
        ]
        set_progress.sort(key=lambda p: p.name.lower())

        return CollectionStats(
            totals=self._totals(sets, instances),
            status_breakdown=self._status_breakdown(sets, instances),
            sets=set_progress,
            themes=self._themes(set_progress),
            colors=self._colors(sets, instances),
            common_parts=self._common_parts(sets),
            top_missing=self._top_missing(),
            burn_up=self._burn_up(history),
            activity_by_hour=self._activity_by_hour(history),
            activity_by_day=self._activity_by_day(history),
            sessions=self._sessions(history),
            years=self._years(sets),
            minifigs=self._minifigs(instances),
        )

    def _totals(self, sets: list[LegoSet], instances: list[MinifigInstance]) -> Totals:
        keys = {
            (p.part_num, p.color_id)
            for parts in ([s.parts for s in sets] + [i.parts for i in instances])
            for p in _tracked(parts)
        }
        return Totals(
            sets=len(sets),
            minifig_instances=len(instances),
            quantity_required=sum(s.total_required for s in sets) + sum(i.total_required for i in instances),
            quantity_found=sum(s.total_found for s in sets) + sum(i.total_found for i in instances),
            quantity_missing=sum(s.total_missing for s in sets) + sum(i.total_missing for i in instances),
            distinct_parts=len({part_num for part_num, _ in keys}),
            distinct_colors=len({color_id for _, color_id in keys}),
        )

    def _status_breakdown(self, sets: list[LegoSet], instances: list[MinifigInstance]) -> list[StatusCount]:
        set_counts: dict[SortingStatus, int] = defaultdict(int)
        instance_counts: dict[SortingStatus, int] = defaultdict(int)
        for s in sets:
            set_counts[s.status] += 1
        for i in instances:
            instance_counts[i.status] += 1
        # Every status appears even at zero, so the funnel keeps its shape on an empty collection.
        return [
            StatusCount(status=status, sets=set_counts[status], minifig_instances=instance_counts[status])
            for status in STATUS_ORDER
        ]

    def _themes(self, set_progress: list[SetProgress]) -> list[ThemeStats]:
        buckets: dict[str | None, list[SetProgress]] = defaultdict(list)
        for p in set_progress:
            buckets[p.root_theme_name].append(p)

        themes = [
            ThemeStats(
                theme_name=name,
                sets=len(items),
                quantity_required=sum(i.quantity_required for i in items),
                quantity_found=sum(i.quantity_found for i in items),
                quantity_missing=sum(i.quantity_missing for i in items),
            )
            for name, items in buckets.items()
        ]
        # Biggest first by pieces: a treemap lays out from the largest tile, and pieces rather than
        # set count is what its areas encode.
        themes.sort(key=lambda t: (-t.quantity_required, t.theme_name or ""))
        return themes

    def _colors(self, sets: list[LegoSet], instances: list[MinifigInstance]) -> list[ColorStats]:
        required: dict[int, int] = defaultdict(int)
        found: dict[int, int] = defaultdict(int)
        names: dict[int, str] = {}
        part_nums: dict[int, set[str]] = defaultdict(set)

        for parts in [s.parts for s in sets] + [i.parts for i in instances]:
            for p in _tracked(parts):
                required[p.color_id] += p.quantity_required
                found[p.color_id] += p.quantity_found
                names.setdefault(p.color_id, p.color_name)
                part_nums[p.color_id].add(p.part_num)

        colors = [
            ColorStats(
                color_id=color_id,
                color_name=names[color_id],
                quantity_required=quantity,
                quantity_found=found[color_id],
                distinct_parts=len(part_nums[color_id]),
            )
            for color_id, quantity in required.items()
        ]
        colors.sort(key=lambda c: (-c.quantity_required, c.color_name))
        return colors

    def _common_parts(self, sets: list[LegoSet]) -> list[CommonPart]:
        """Counted across sets only. Minifig inventories are a handful of pieces each and would
        bury the structural bricks this is meant to surface."""
        set_counts: dict[tuple[str, int], set[str]] = defaultdict(set)
        quantities: dict[tuple[str, int], int] = defaultdict(int)
        labels: dict[tuple[str, int], Part] = {}

        for s in sets:
            for p in _tracked(s.parts):
                key = (p.part_num, p.color_id)
                set_counts[key].add(s.set_num)
                quantities[key] += p.quantity_required
                labels.setdefault(key, p)

        common = [
            CommonPart(
                part_num=part_num,
                color_id=color_id,
                part_name=labels[(part_num, color_id)].name,
                color_name=labels[(part_num, color_id)].color_name,
                image_path=labels[(part_num, color_id)].image_path,
                set_count=len(owners),
                quantity_required=quantities[(part_num, color_id)],
            )
            for (part_num, color_id), owners in set_counts.items()
        ]
        common.sort(key=lambda c: (-c.set_count, -c.quantity_required, c.part_name))
        return common[:COMMON_PARTS_LIMIT]

    def _top_missing(self) -> list[MissingPartStat]:
        aggregates = self.missing_summary.execute(group_by="part")
        return [
            MissingPartStat(
                part_num=a.part_num,
                color_id=a.color_id,
                part_name=a.part_name,
                color_name=a.color_name,
                image_path=a.image_path,
                total_missing=a.total_missing,
                source_count=len(a.contributors),
            )
            for a in aggregates[:TOP_MISSING_LIMIT]
        ]

    def _burn_up(self, history: list[MissingPartRecord]) -> BurnUp:
        if not history:
            return BurnUp(granularity="hour", points=[])

        ordered = sorted(history, key=lambda r: r.timestamp)
        span = ordered[-1].timestamp - ordered[0].timestamp
        granularity: Literal["hour", "day"] = "hour" if span <= HOURLY_BURN_UP_MAX_SPAN else "day"

        def bucket_of(moment: datetime) -> datetime:
            moment = moment.astimezone(UTC)
            if granularity == "day":
                return moment.replace(hour=0, minute=0, second=0, microsecond=0)
            return moment.replace(minute=0, second=0, microsecond=0)

        totals: dict[datetime, int] = defaultdict(int)
        for record in ordered:
            totals[bucket_of(record.timestamp)] += record.quantity_after - record.quantity_before

        # Open on zero one bucket before the first find, so the curve visibly rises from nothing
        # rather than starting part-way up its own first step.
        step = timedelta(days=1) if granularity == "day" else timedelta(hours=1)
        buckets = sorted(totals)
        points = [BurnUpPoint(timestamp=buckets[0] - step, quantity_found=0)]

        running = 0
        for bucket in buckets:
            running += totals[bucket]
            points.append(BurnUpPoint(timestamp=bucket + step, quantity_found=running))
        return BurnUp(granularity=granularity, points=points)

    def _activity_by_hour(self, history: list[MissingPartRecord]) -> list[HourBucket]:
        events: dict[int, int] = defaultdict(int)
        pieces: dict[int, int] = defaultdict(int)
        for record in history:
            # Local time, because "when do I sort" is a question about the owner's evening rather
            # than about UTC.
            hour = record.timestamp.astimezone().hour
            events[hour] += 1
            pieces[hour] += record.quantity_after - record.quantity_before
        # All 24 hours, so the histogram keeps a stable x axis and the quiet ones read as quiet.
        return [HourBucket(hour=h, events=events[h], pieces=pieces[h]) for h in range(24)]

    def _activity_by_day(self, history: list[MissingPartRecord]) -> list[DayBucket]:
        events: dict[date, int] = defaultdict(int)
        pieces: dict[date, int] = defaultdict(int)
        for record in history:
            day = record.timestamp.astimezone().date()
            events[day] += 1
            pieces[day] += record.quantity_after - record.quantity_before
        return [DayBucket(day=day, events=events[day], pieces=pieces[day]) for day in sorted(events)]

    def _sessions(self, history: list[MissingPartRecord]) -> SessionStats:
        if not history:
            return SessionStats(
                count=0, total_minutes=0, longest_minutes=0, pieces_per_session=0, pieces_per_hour=0
            )

        ordered = sorted(history, key=lambda r: r.timestamp)
        runs: list[list[MissingPartRecord]] = [[ordered[0]]]
        for previous, record in pairwise(ordered):
            if record.timestamp - previous.timestamp > SESSION_GAP:
                runs.append([record])
            else:
                runs[-1].append(record)

        durations = [(run[-1].timestamp - run[0].timestamp).total_seconds() / 60 for run in runs]
        pieces = sum(r.quantity_after - r.quantity_before for r in ordered)
        total_minutes = sum(durations)
        return SessionStats(
            count=len(runs),
            total_minutes=round(total_minutes),
            longest_minutes=round(max(durations)),
            pieces_per_session=round(pieces / len(runs)),
            # A session of a single find spans no time at all, so the rate is reported over the
            # summed durations and reads as zero only when every session was instantaneous.
            pieces_per_hour=round(pieces / (total_minutes / 60)) if total_minutes else 0,
        )

    def _years(self, sets: list[LegoSet]) -> list[YearBucket]:
        counts: dict[int | None, int] = defaultdict(int)
        pieces: dict[int | None, int] = defaultdict(int)
        for s in sets:
            counts[s.year] += 1
            pieces[s.year] += s.total_required
        # Unknown years last, so the axis stays a clean chronological run.
        years = sorted(counts, key=lambda y: (y is None, y or 0))
        return [YearBucket(year=y, sets=counts[y], quantity_required=pieces[y]) for y in years]

    def _minifigs(self, instances: list[MinifigInstance]) -> MinifigStats:
        by_fig: dict[str, list[MinifigInstance]] = defaultdict(list)
        for i in instances:
            by_fig[i.fig_num].append(i)

        duplicated = [
            DuplicatedFig(
                fig_num=fig_num,
                fig_name=owned[0].fig_name,
                image_path=owned[0].image_path,
                count=len(owned),
            )
            for fig_num, owned in by_fig.items()
            if len(owned) > 1
        ]
        duplicated.sort(key=lambda d: (-d.count, d.fig_name))

        return MinifigStats(
            total=len(instances),
            loose=sum(1 for i in instances if i.source_set_num is None),
            from_set=sum(1 for i in instances if i.source_set_num is not None),
            distinct_figs=len(by_fig),
            complete=sum(1 for i in instances if i.is_complete),
            most_duplicated=duplicated[:DUPLICATED_FIGS_LIMIT],
        )
