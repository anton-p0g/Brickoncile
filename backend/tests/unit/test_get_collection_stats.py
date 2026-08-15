from datetime import UTC, datetime, timedelta

from app.application.use_cases.get_collection_stats import GetCollectionStatsUseCase
from app.application.use_cases.get_missing_summary import GetMissingSummaryUseCase
from app.domain.entities import LegoSet, MissingPartRecord, Part, Theme
from tests.unit.fakes import (
    FakeMinifigInstanceRepository,
    FakeMissingHistoryRepository,
    FakeSetRepository,
    FakeThemeRepository,
)

SORTED_AT = "2024-01-02T00:00:00Z"
START = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)


def make_part(part_num, color_id=0, quantity_required=4, quantity_found=0, is_spare=False, color_name="Black"):
    return Part(
        part_num=part_num,
        color_id=color_id,
        color_name=color_name,
        name=f"Part {part_num}",
        element_id=None,
        quantity_required=quantity_required,
        quantity_found=quantity_found,
        is_spare=is_spare,
    )


def make_set(set_num, parts, sorting_finished_at=None, theme_id=None, year=2015, num_parts=None):
    return LegoSet(
        set_num=set_num,
        name=f"Set {set_num}",
        year=year,
        theme_id=theme_id,
        num_parts=num_parts if num_parts is not None else len(parts),
        last_synced_at="2024-01-01T00:00:00Z",
        sorting_finished_at=sorting_finished_at,
        parts=parts,
    )


def make_record(minutes, quantity_before=0, quantity_after=1, part_num="3001", entity_id="75192-1"):
    return MissingPartRecord(
        entity_type="set",
        entity_id=entity_id,
        part_num=part_num,
        color_id=0,
        action="marked_found",
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        timestamp=START + timedelta(minutes=minutes),
    )


def build(sets=(), instances=None, records=(), themes=()):
    set_repo = FakeSetRepository()
    for s in sets:
        set_repo.save(s)
    instance_repo = instances if instances is not None else FakeMinifigInstanceRepository()
    history_repo = FakeMissingHistoryRepository()
    for r in records:
        history_repo.append(r)
    return GetCollectionStatsUseCase(
        set_repo,
        instance_repo,
        history_repo,
        FakeThemeRepository(list(themes)),
        GetMissingSummaryUseCase(set_repo, instance_repo),
    )


def test_totals_exclude_spares():
    stats = build(
        sets=[make_set("75192-1", [make_part("3001", quantity_required=4, quantity_found=1), make_part("9999", quantity_required=7, is_spare=True)])]
    ).execute()

    assert stats.totals.quantity_required == 4
    assert stats.totals.quantity_found == 1
    assert stats.totals.distinct_parts == 1


def test_missing_only_counts_finished_inventories():
    """An unfinished set's unfound pieces are still in the pile, not confirmed missing."""
    stats = build(
        sets=[
            make_set("unsorted-1", [make_part("3001", quantity_required=4, quantity_found=1)]),
            make_set("sorted-1", [make_part("3002", quantity_required=4, quantity_found=1)], sorting_finished_at=SORTED_AT),
        ]
    ).execute()

    assert stats.totals.quantity_missing == 3


def test_themes_roll_up_to_the_root_theme():
    """A set filed under a sub-theme belongs to its line, which is how a shelf is organised."""
    themes = [Theme(id=1, parent_id=None, name="Star Wars"), Theme(id=2, parent_id=1, name="Ultimate Collector Series")]
    stats = build(
        sets=[
            make_set("a-1", [make_part("3001", quantity_required=10)], theme_id=1),
            make_set("b-1", [make_part("3002", quantity_required=5)], theme_id=2),
        ],
        themes=themes,
    ).execute()

    assert [(t.theme_name, t.sets, t.quantity_required) for t in stats.themes] == [("Star Wars", 2, 15)]


def test_sets_without_a_known_theme_bucket_under_none():
    stats = build(sets=[make_set("a-1", [make_part("3001")], theme_id=None)]).execute()

    assert [t.theme_name for t in stats.themes] == [None]


def test_status_breakdown_lists_every_status_even_when_empty():
    stats = build(sets=[make_set("a-1", [make_part("3001", quantity_found=0)])]).execute()

    assert [s.status for s in stats.status_breakdown] == ["not_started", "sorting", "sorted", "complete"]
    assert [s.sets for s in stats.status_breakdown] == [1, 0, 0, 0]


def test_common_parts_count_the_sets_sharing_each_part():
    stats = build(
        sets=[
            make_set("a-1", [make_part("3001", quantity_required=2), make_part("3020", quantity_required=1)]),
            make_set("b-1", [make_part("3001", quantity_required=3)]),
        ]
    ).execute()

    top = stats.common_parts[0]
    assert (top.part_num, top.set_count, top.quantity_required) == ("3001", 2, 5)


def test_common_parts_separate_colours_of_the_same_part():
    stats = build(
        sets=[make_set("a-1", [make_part("3001", color_id=0), make_part("3001", color_id=15, color_name="White")])]
    ).execute()

    assert {(c.part_num, c.color_id) for c in stats.common_parts} == {("3001", 0), ("3001", 15)}


def test_colors_aggregate_required_and_found():
    stats = build(
        sets=[
            make_set("a-1", [make_part("3001", color_id=0, quantity_required=4, quantity_found=2)]),
            make_set("b-1", [make_part("3020", color_id=0, quantity_required=6, quantity_found=1)]),
        ]
    ).execute()

    assert [(c.color_id, c.quantity_required, c.quantity_found, c.distinct_parts) for c in stats.colors] == [(0, 10, 3, 2)]


def test_burn_up_ends_at_the_current_found_total():
    """The audit trail is the only source for the curve, so it has to reconcile with the totals."""
    records = [make_record(0, 0, 3), make_record(10, 0, 2), make_record(20, 2, 5)]
    stats = build(records=records).execute()

    assert stats.burn_up.points[0].quantity_found == 0
    assert stats.burn_up.points[-1].quantity_found == 8


def test_burn_up_is_cumulative_across_buckets():
    records = [make_record(0, 0, 3), make_record(120, 0, 4)]
    stats = build(records=records).execute()

    assert [p.quantity_found for p in stats.burn_up.points] == [0, 3, 7]


def test_burn_up_switches_to_daily_buckets_over_a_long_span():
    records = [make_record(0, 0, 1), make_record(90 * 24 * 60, 0, 1)]
    stats = build(records=records).execute()

    assert stats.burn_up.granularity == "day"


def test_burn_up_is_empty_without_history():
    stats = build(sets=[make_set("a-1", [make_part("3001")])]).execute()

    assert stats.burn_up.points == []


def test_sessions_split_on_a_long_pause():
    """Two finds an hour apart are two sittings; two a few minutes apart are one."""
    records = [make_record(0, 0, 1), make_record(5, 0, 1), make_record(65, 0, 1)]
    stats = build(records=records).execute()

    assert stats.sessions.count == 2
    assert stats.sessions.longest_minutes == 5


def test_sessions_report_zero_on_an_untouched_collection():
    stats = build().execute()

    assert stats.sessions.count == 0
    assert stats.sessions.pieces_per_hour == 0


def test_activity_by_hour_covers_the_whole_day():
    stats = build(records=[make_record(0, 0, 2)]).execute()

    assert len(stats.activity_by_hour) == 24
    assert sum(h.pieces for h in stats.activity_by_hour) == 2


def test_years_sort_chronologically_with_unknown_last():
    stats = build(
        sets=[
            make_set("a-1", [make_part("3001")], year=2015),
            make_set("b-1", [make_part("3002")], year=None),
            make_set("c-1", [make_part("3003")], year=2009),
        ]
    ).execute()

    assert [y.year for y in stats.years] == [2009, 2015, None]


def test_minifig_stats_split_loose_from_set_owned_and_rank_duplicates():
    instance_repo = FakeMinifigInstanceRepository()
    template = [make_part("3626", quantity_required=1)]
    instance_repo.create("fig-001", "Battle Droid", None, "75192-1", template)
    instance_repo.create("fig-001", "Battle Droid", None, "75193-1", template)
    instance_repo.create("fig-002", "R2-D2", None, None, template)

    stats = build(instances=instance_repo).execute()

    assert (stats.minifigs.total, stats.minifigs.loose, stats.minifigs.from_set) == (3, 1, 2)
    assert stats.minifigs.distinct_figs == 2
    assert [(d.fig_num, d.count) for d in stats.minifigs.most_duplicated] == [("fig-001", 2)]


def test_top_missing_reports_how_many_sources_want_each_part():
    stats = build(
        sets=[
            make_set("a-1", [make_part("3001", quantity_required=4, quantity_found=1)], sorting_finished_at=SORTED_AT),
            make_set("b-1", [make_part("3001", quantity_required=4, quantity_found=2)], sorting_finished_at=SORTED_AT),
        ]
    ).execute()

    assert len(stats.top_missing) == 1
    assert (stats.top_missing[0].total_missing, stats.top_missing[0].source_count) == (5, 2)


def test_colors_are_ranked_most_used_first():
    """The palette chart shows only the leading colours, so the order decides what is on screen."""
    stats = build(
        sets=[
            make_set(
                "a-1",
                [
                    make_part("3001", color_id=0, quantity_required=40),
                    make_part("3002", color_id=15, color_name="White", quantity_required=2),
                    make_part("3003", color_id=4, color_name="Red", quantity_required=9),
                ],
            )
        ]
    ).execute()

    assert [c.color_name for c in stats.colors] == ["Black", "Red", "White"]


def test_set_progress_carries_the_cached_image():
    """The completion grid previews a set on hover, which needs its picture."""
    lego_set = make_set("a-1", [make_part("3001")])
    lego_set.image_path = "sets/a-1.jpg"
    stats = build(sets=[lego_set]).execute()

    assert stats.sets[0].image_path == "sets/a-1.jpg"
