"""Schema migrations for databases created before a model change.

The project has no migration framework, and `SQLModel.metadata.create_all` only creates missing
tables, never alters existing ones. These steps are idempotent and run at startup, so a database
migrated here ends up with the same schema `create_all` would produce from scratch.
"""

import logging

from sqlalchemy import Engine, text
from sqlmodel import Session

logger = logging.getLogger(__name__)


def _columns(session: Session, table: str) -> set[str]:
    rows = session.exec(text(f"PRAGMA table_info({table})")).all()  # type: ignore[call-overload]
    return {row[1] for row in rows}


def _table_exists(session: Session, table: str) -> bool:
    row = session.exec(  # type: ignore[call-overload]
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name").bindparams(name=table)
    ).first()
    return row is not None


def run_migrations(engine: Engine) -> None:
    with Session(engine) as session:
        _migrate_missing_to_found(session, "set_parts")
        _migrate_missing_to_found(session, "minifig_instance_parts")
        _add_quantity_broken(session, "set_parts")
        _add_quantity_broken(session, "minifig_instance_parts")
        _add_sorting_finished_at(session, "sets")
        _add_sorting_finished_at(session, "minifig_instances")
        _allow_loose_minifig_instances(session)
        session.commit()


def _add_quantity_broken(session: Session, table: str) -> None:
    """Add the condition count without changing what existing found counts mean."""
    if not _table_exists(session, table):
        return
    if "quantity_broken" in _columns(session, table):
        return

    logger.info("migrating %s: adding quantity_broken", table)
    session.exec(  # type: ignore[call-overload]
        text(f"ALTER TABLE {table} ADD COLUMN quantity_broken INTEGER NOT NULL DEFAULT 0")
    )


def _migrate_missing_to_found(session: Session, table: str) -> None:
    """Switch the tracked quantity from "missing" to "found".

    Existing rows recorded how many pieces were absent under the old all-present-by-default model,
    so the equivalent found count is `required - missing`.
    """
    if not _table_exists(session, table):
        return
    columns = _columns(session, table)
    if "quantity_found" in columns:
        return

    logger.info("migrating %s: quantity_missing -> quantity_found", table)
    session.exec(text(f"ALTER TABLE {table} ADD COLUMN quantity_found INTEGER NOT NULL DEFAULT 0"))  # type: ignore[call-overload]
    if "quantity_missing" in columns:
        session.exec(  # type: ignore[call-overload]
            text(
                f"UPDATE {table} SET quantity_found = "
                f"MAX(0, MIN(quantity_required, quantity_required - quantity_missing))"
            )
        )
        _convert_history_to_found_terms(session, table)
        session.exec(text(f"ALTER TABLE {table} DROP COLUMN quantity_missing"))  # type: ignore[call-overload]


def _convert_history_to_found_terms(session: Session, table: str) -> None:
    """Restate the audit log in found counts.

    History rows previously stored missing counts. Leaving them as-is would mix two meanings in one
    column, so each row is converted with `found = required - missing` against its part's required
    quantity. The action names still hold: `marked_found` remains the label for pieces turning up.
    """
    entity_type, id_column = (
        ("set", "set_num") if table == "set_parts" else ("minifig_instance", "instance_id")
    )
    session.exec(  # type: ignore[call-overload]
        text(f"""
        UPDATE missing_history SET
            quantity_before = (
                SELECT MAX(0, p.quantity_required - missing_history.quantity_before)
                FROM {table} p
                WHERE p.{id_column} = missing_history.entity_id
                  AND p.part_num = missing_history.part_num
                  AND p.color_id = missing_history.color_id
            ),
            quantity_after = (
                SELECT MAX(0, p.quantity_required - missing_history.quantity_after)
                FROM {table} p
                WHERE p.{id_column} = missing_history.entity_id
                  AND p.part_num = missing_history.part_num
                  AND p.color_id = missing_history.color_id
            )
        WHERE entity_type = :entity_type
          AND EXISTS (
            SELECT 1 FROM {table} p
            WHERE p.{id_column} = missing_history.entity_id
              AND p.part_num = missing_history.part_num
              AND p.color_id = missing_history.color_id
          )
        """).bindparams(entity_type=entity_type)
    )


def _allow_loose_minifig_instances(session: Session) -> None:
    """Drop the NOT NULL on `minifig_instances.source_set_num`.

    A minifig identified from a photo often has no set to attribute it to — it was bought on its
    own or came out of a mixed pile — so the column has to admit null. SQLite cannot relax a NOT
    NULL in place, so the table is rebuilt: create the new shape, copy every row, swap the names,
    and put the indexes back. Existing rows all have a source set and are copied unchanged.
    """
    if not _table_exists(session, "minifig_instances"):
        return
    if _is_nullable(session, "minifig_instances", "source_set_num"):
        return

    logger.info("migrating minifig_instances: allowing a null source_set_num for loose minifigs")
    session.exec(  # type: ignore[call-overload]
        text("""
        CREATE TABLE minifig_instances_new (
            id VARCHAR NOT NULL,
            fig_num VARCHAR NOT NULL,
            fig_name VARCHAR NOT NULL,
            img_local_path VARCHAR,
            source_set_num VARCHAR,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            sorting_finished_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(fig_num) REFERENCES minifigs (fig_num),
            FOREIGN KEY(source_set_num) REFERENCES sets (set_num)
        )
        """)
    )
    session.exec(  # type: ignore[call-overload]
        text("""
        INSERT INTO minifig_instances_new
            (id, fig_num, fig_name, img_local_path, source_set_num,
             created_at, updated_at, sorting_finished_at)
        SELECT id, fig_num, fig_name, img_local_path, source_set_num,
               created_at, updated_at, sorting_finished_at
        FROM minifig_instances
        """)
    )
    session.exec(text("DROP TABLE minifig_instances"))  # type: ignore[call-overload]
    session.exec(text("ALTER TABLE minifig_instances_new RENAME TO minifig_instances"))  # type: ignore[call-overload]
    # Dropping the old table took its indexes with it.
    session.exec(  # type: ignore[call-overload]
        text("CREATE INDEX ix_minifig_instances_fig_num ON minifig_instances (fig_num)")
    )
    session.exec(  # type: ignore[call-overload]
        text("CREATE INDEX ix_minifig_instances_source_set_num ON minifig_instances (source_set_num)")
    )


def _is_nullable(session: Session, table: str, column: str) -> bool:
    rows = session.exec(text(f"PRAGMA table_info({table})")).all()  # type: ignore[call-overload]
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    return any(row[1] == column and not row[3] for row in rows)


def _add_sorting_finished_at(session: Session, table: str) -> None:
    """Add the finished-sorting marker.

    Anything already in the collection was tracked under the old model, where a missing count of
    zero meant "assumed complete" rather than "not checked". Treating those as already sorted
    preserves exactly what the owner currently sees; a set they want to re-check can simply be
    resumed from the UI.
    """
    if not _table_exists(session, table):
        return
    if "sorting_finished_at" in _columns(session, table):
        return

    logger.info("migrating %s: adding sorting_finished_at", table)
    session.exec(text(f"ALTER TABLE {table} ADD COLUMN sorting_finished_at DATETIME"))  # type: ignore[call-overload]
    session.exec(text(f"UPDATE {table} SET sorting_finished_at = created_at"))  # type: ignore[call-overload]
