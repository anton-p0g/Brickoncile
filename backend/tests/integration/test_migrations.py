"""Tests for the pre-quantity_found schema, written as raw SQL because the old SQLModel tables no
longer exist in code. This is the only place the legacy shape is still described."""

from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

from app.infrastructure.db.migrations import run_migrations

LEGACY_SCHEMA = """
CREATE TABLE sets (
    set_num VARCHAR NOT NULL PRIMARY KEY, name VARCHAR NOT NULL, year INTEGER, theme_id INTEGER,
    num_parts INTEGER NOT NULL, img_local_path VARCHAR, source_img_url VARCHAR,
    created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, last_synced_at DATETIME NOT NULL
);
CREATE TABLE set_parts (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, set_num VARCHAR NOT NULL, part_num VARCHAR NOT NULL,
    color_id INTEGER NOT NULL, color_name VARCHAR NOT NULL, part_name VARCHAR NOT NULL, element_id VARCHAR,
    quantity_required INTEGER NOT NULL, quantity_missing INTEGER NOT NULL, is_spare BOOLEAN NOT NULL,
    img_local_path VARCHAR, source_img_url VARCHAR, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE missing_history (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, entity_type VARCHAR NOT NULL, entity_id VARCHAR NOT NULL,
    part_num VARCHAR NOT NULL, color_id INTEGER NOT NULL, action VARCHAR NOT NULL,
    quantity_before INTEGER NOT NULL, quantity_after INTEGER NOT NULL, timestamp DATETIME NOT NULL
);
"""


def legacy_engine(tmp_path, rows_sql: str = ""):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        for statement in filter(str.strip, LEGACY_SCHEMA.split(";")):
            conn.execute(text(statement))
        for statement in filter(str.strip, rows_sql.split(";")):
            conn.execute(text(statement))
    return engine


def query(engine, sql: str):
    with Session(engine) as session:
        return session.exec(text(sql)).all()  # type: ignore[call-overload]


SEED = """
INSERT INTO sets VALUES ('70202-1','Shield',2015,1,59,NULL,NULL,'2024-01-01','2024-01-01','2024-01-01');
INSERT INTO set_parts (set_num,part_num,color_id,color_name,part_name,quantity_required,quantity_missing,is_spare,created_at,updated_at)
    VALUES ('70202-1','11334',0,'Black','Brick',2,2,0,'2024-01-01','2024-01-01');
INSERT INTO set_parts (set_num,part_num,color_id,color_name,part_name,quantity_required,quantity_missing,is_spare,created_at,updated_at)
    VALUES ('70202-1','3001',0,'Black','Brick',4,0,0,'2024-01-01','2024-01-01');
INSERT INTO missing_history (entity_type,entity_id,part_num,color_id,action,quantity_before,quantity_after,timestamp)
    VALUES ('set','70202-1','11334',0,'marked_missing',0,2,'2024-01-01');
"""


def test_converts_missing_counts_into_found_counts(tmp_path):
    engine = legacy_engine(tmp_path, SEED)

    run_migrations(engine)

    rows = dict(query(engine, "SELECT part_num, quantity_found FROM set_parts"))
    # 2 of 2 missing means none were found; 0 of 4 missing means all four were present.
    assert rows == {"11334": 0, "3001": 4}


def test_drops_the_legacy_column_so_the_schema_matches_a_fresh_database(tmp_path):
    engine = legacy_engine(tmp_path, SEED)

    run_migrations(engine)

    columns = {row[1] for row in query(engine, "PRAGMA table_info(set_parts)")}
    assert "quantity_found" in columns
    assert "quantity_broken" in columns
    assert "quantity_missing" not in columns


def test_restates_history_in_found_terms(tmp_path):
    engine = legacy_engine(tmp_path, SEED)

    run_migrations(engine)

    before, after = query(engine, "SELECT quantity_before, quantity_after FROM missing_history")[0]
    # Was "missing went 0 -> 2" on a part requiring 2, which is "found went 2 -> 0".
    assert (before, after) == (2, 0)


def test_marks_existing_sets_as_already_sorted(tmp_path):
    """Pre-existing rows were tracked as all-present-by-default, so their zero missing counts were
    assertions about the set, not untouched state."""
    engine = legacy_engine(tmp_path, SEED)

    run_migrations(engine)

    assert query(engine, "SELECT sorting_finished_at FROM sets")[0][0] is not None


def test_is_idempotent(tmp_path):
    engine = legacy_engine(tmp_path, SEED)

    run_migrations(engine)
    first = query(engine, "SELECT part_num, quantity_found FROM set_parts")
    history_first = query(engine, "SELECT quantity_before, quantity_after FROM missing_history")

    run_migrations(engine)

    assert query(engine, "SELECT part_num, quantity_found FROM set_parts") == first
    assert query(engine, "SELECT quantity_before, quantity_after FROM missing_history") == history_first


MINIFIG_INSTANCES_SCHEMA = """
CREATE TABLE minifigs (
    fig_num VARCHAR NOT NULL PRIMARY KEY, name VARCHAR NOT NULL, num_parts INTEGER,
    img_local_path VARCHAR, source_img_url VARCHAR,
    created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, last_synced_at DATETIME NOT NULL
);
CREATE TABLE minifig_instances (
    id VARCHAR NOT NULL, fig_num VARCHAR NOT NULL, fig_name VARCHAR NOT NULL, img_local_path VARCHAR,
    source_set_num VARCHAR NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
    sorting_finished_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(fig_num) REFERENCES minifigs (fig_num),
    FOREIGN KEY(source_set_num) REFERENCES sets (set_num)
);
CREATE INDEX ix_minifig_instances_fig_num ON minifig_instances (fig_num);
CREATE INDEX ix_minifig_instances_source_set_num ON minifig_instances (source_set_num);
INSERT INTO minifig_instances VALUES
    ('inst-1','sw0001','Luke',NULL,'70202-1','2024-01-01','2024-01-01',NULL);
"""


def instances_engine(tmp_path):
    """A database whose minifig_instances still requires a source set."""
    engine = legacy_engine(tmp_path)
    with engine.begin() as conn:
        for statement in filter(str.strip, MINIFIG_INSTANCES_SCHEMA.split(";")):
            conn.execute(text(statement))
    return engine


def test_allows_a_loose_minifig_with_no_source_set(tmp_path):
    engine = instances_engine(tmp_path)

    run_migrations(engine)

    with Session(engine) as session:
        session.exec(  # type: ignore[call-overload]
            text(
                "INSERT INTO minifig_instances VALUES "
                "('inst-2','sw0002','Han',NULL,NULL,'2024-01-01','2024-01-01',NULL)"
            )
        )
        session.commit()

    loose = query(engine, "SELECT source_set_num FROM minifig_instances WHERE id = 'inst-2'")
    assert loose == [(None,)]


def test_keeps_existing_instances_and_their_source_sets(tmp_path):
    engine = instances_engine(tmp_path)

    run_migrations(engine)

    assert query(engine, "SELECT id, fig_num, source_set_num FROM minifig_instances") == [
        ("inst-1", "sw0001", "70202-1")
    ]


def test_rebuilding_the_table_puts_its_indexes_back(tmp_path):
    """The rebuild drops the old table, which takes its indexes with it."""
    engine = instances_engine(tmp_path)

    run_migrations(engine)

    indexes = {row[1] for row in query(engine, "PRAGMA index_list(minifig_instances)")}
    assert "ix_minifig_instances_fig_num" in indexes
    assert "ix_minifig_instances_source_set_num" in indexes


def test_loosening_the_source_set_is_idempotent(tmp_path):
    engine = instances_engine(tmp_path)

    run_migrations(engine)
    run_migrations(engine)

    assert query(engine, "SELECT id FROM minifig_instances") == [("inst-1",)]


def test_runs_clean_on_a_brand_new_database(tmp_path):
    """A fresh database is created by create_all and must need no migrating."""
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    from app.infrastructure.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    run_migrations(engine)

    columns = {row[1] for row in query(engine, "PRAGMA table_info(set_parts)")}
    assert "quantity_found" in columns
    assert "quantity_broken" in columns
    assert "quantity_missing" not in columns


def test_adds_zero_broken_count_to_an_existing_found_inventory(tmp_path):
    """The direct upgrade path for current users preserves every existing found count."""
    engine = create_engine(f"sqlite:///{tmp_path / 'current.db'}")
    from app.infrastructure.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE set_parts DROP COLUMN quantity_broken"))
        connection.execute(
            text(
                """
                INSERT INTO set_parts
                    (set_num, part_num, color_id, color_name, part_name, quantity_required,
                     quantity_found, is_spare, created_at, updated_at)
                VALUES
                    ('75192-1', '3001', 0, 'Black', 'Brick 2x4', 4, 3, 0,
                     '2024-01-01', '2024-01-01')
                """
            )
        )

    run_migrations(engine)

    row = query(engine, "SELECT quantity_found, quantity_broken FROM set_parts")[0]
    assert row == (3, 0)
