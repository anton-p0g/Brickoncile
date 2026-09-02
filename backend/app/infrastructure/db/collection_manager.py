"""Registry and request-scoped SQLite engines for independent collections."""

import sqlite3
import threading
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine

from app.domain.errors import (
    CollectionNameConflictError,
    CollectionNotFoundError,
    InvalidCollectionNameError,
)
from app.infrastructure.db import models  # noqa: F401 — registers collection tables
from app.infrastructure.db.migrations import run_migrations

DEFAULT_COLLECTION_NAME = "My Collection"
MAX_COLLECTION_NAME_LENGTH = 50


@dataclass(frozen=True)
class CollectionRecord:
    id: str
    name: str
    database_path: Path
    created_at: datetime
    is_default: bool


def _normalise_name(raw_name: str) -> tuple[str, str]:
    name = raw_name.strip()
    if not name:
        raise InvalidCollectionNameError("Collection name cannot be empty")
    if len(name) > MAX_COLLECTION_NAME_LENGTH:
        raise InvalidCollectionNameError(
            f"Collection name must be {MAX_COLLECTION_NAME_LENGTH} characters or fewer"
        )
    if any(unicodedata.category(character).startswith("C") for character in name):
        raise InvalidCollectionNameError("Collection name cannot contain control characters")
    return name, unicodedata.normalize("NFKC", name).casefold()


def create_collection_engine(database_path: Path) -> Engine:
    return create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )


def prepare_collection_database(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    # create_all never alters existing tables, so older collection files still need migrations.
    run_migrations(engine)


class CollectionManager:
    """Own the small registry and lazily open one engine per collection.

    The original configured database remains the default collection. New database filenames are
    opaque IDs rather than display names, so a rename can never move a file and user input never
    participates in filesystem paths.
    """

    def __init__(
        self,
        default_database_path: Path,
        registry_path: Path | None = None,
        collections_dir: Path | None = None,
    ):
        self.default_database_path = default_database_path.resolve()
        self.registry_path = (registry_path or default_database_path.parent / "collections-registry.db").resolve()
        self.collections_dir = (collections_dir or default_database_path.parent / "collections").resolve()
        self._engines: dict[str, Engine] = {}
        self._lock = threading.RLock()

    def initialize(self) -> CollectionRecord:
        """Create the registry and adopt the pre-existing database without moving or copying it."""
        with self._lock:
            self.default_database_path.parent.mkdir(parents=True, exist_ok=True)
            self.collections_dir.mkdir(parents=True, exist_ok=True)
            self._create_registry_schema()

            records = self.list_collections()
            if records:
                default = next((record for record in records if record.is_default), records[0])
            else:
                default = self._register_default_collection()

            # Open and migrate only the default at startup. Other collections are prepared when
            # selected, isolating a failure to the collection being opened.
            self.get_engine(default.id)
            return default

    def list_collections(self) -> list[CollectionRecord]:
        with self._connect_registry() as connection:
            rows = connection.execute(
                """
                SELECT id, name, database_path, created_at, is_default
                FROM collections
                ORDER BY is_default DESC, created_at ASC, name COLLATE NOCASE ASC
                """
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def get_collection(self, collection_id: str | None) -> CollectionRecord:
        with self._connect_registry() as connection:
            if collection_id:
                row = connection.execute(
                    """SELECT id, name, database_path, created_at, is_default
                       FROM collections WHERE id = ?""",
                    (collection_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT id, name, database_path, created_at, is_default
                       FROM collections ORDER BY is_default DESC, created_at ASC LIMIT 1"""
                ).fetchone()
        if row is None:
            label = collection_id or "default"
            raise CollectionNotFoundError(f"Collection {label} was not found")
        return self._record_from_row(row)

    def create_collection(self, raw_name: str) -> CollectionRecord:
        name, normalised_name = _normalise_name(raw_name)
        with self._lock:
            with self._connect_registry() as connection:
                duplicate = connection.execute(
                    "SELECT 1 FROM collections WHERE normalised_name = ?", (normalised_name,)
                ).fetchone()
            if duplicate is not None:
                raise CollectionNameConflictError(f'A collection named "{name}" already exists')

            collection_id = str(uuid4())
            final_path = self.collections_dir / f"{collection_id}.db"
            temporary_path = self.collections_dir / f".{collection_id}.tmp"
            engine = create_collection_engine(temporary_path)
            try:
                prepare_collection_database(engine)
            except Exception:
                engine.dispose()
                temporary_path.unlink(missing_ok=True)
                raise
            else:
                engine.dispose()
            temporary_path.replace(final_path)

            created_at = datetime.now(UTC)
            try:
                with self._connect_registry() as connection:
                    connection.execute(
                        """INSERT INTO collections
                           (id, name, normalised_name, database_path, created_at, is_default)
                           VALUES (?, ?, ?, ?, ?, 0)""",
                        (
                            collection_id,
                            name,
                            normalised_name,
                            str(final_path),
                            created_at.isoformat(),
                        ),
                    )
                    connection.commit()
            except sqlite3.IntegrityError as exc:
                final_path.unlink(missing_ok=True)
                raise CollectionNameConflictError(f'A collection named "{name}" already exists') from exc

            return CollectionRecord(collection_id, name, final_path, created_at, False)

    def get_engine(self, collection_id: str | None = None) -> Engine:
        record = self.get_collection(collection_id)
        with self._lock:
            cached = self._engines.get(record.id)
            if cached is not None:
                return cached
            if not record.database_path.is_file():
                raise CollectionNotFoundError(f'Database for collection "{record.name}" was not found')
            engine = create_collection_engine(record.database_path)
            prepare_collection_database(engine)
            self._engines[record.id] = engine
            return engine

    def close(self) -> None:
        with self._lock:
            for engine in self._engines.values():
                engine.dispose()
            self._engines.clear()

    def _create_registry_schema(self) -> None:
        with self._connect_registry() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    normalised_name TEXT NOT NULL UNIQUE,
                    database_path TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS one_default_collection
                   ON collections(is_default) WHERE is_default = 1"""
            )
            connection.commit()

    def _register_default_collection(self) -> CollectionRecord:
        name, normalised_name = _normalise_name(DEFAULT_COLLECTION_NAME)
        collection_id = str(uuid4())
        created_at = datetime.now(UTC)
        engine = create_collection_engine(self.default_database_path)
        try:
            prepare_collection_database(engine)
        finally:
            engine.dispose()
        with self._connect_registry() as connection:
            connection.execute(
                """INSERT INTO collections
                   (id, name, normalised_name, database_path, created_at, is_default)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (
                    collection_id,
                    name,
                    normalised_name,
                    str(self.default_database_path),
                    created_at.isoformat(),
                ),
            )
            connection.commit()
        return CollectionRecord(collection_id, name, self.default_database_path, created_at, True)

    def _connect_registry(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.registry_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> CollectionRecord:
        return CollectionRecord(
            id=row["id"],
            name=row["name"],
            database_path=Path(row["database_path"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            is_default=bool(row["is_default"]),
        )
