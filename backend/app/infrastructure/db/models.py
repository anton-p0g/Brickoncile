from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class SetTable(SQLModel, table=True):
    __tablename__ = "sets"

    set_num: str = Field(primary_key=True)
    name: str
    year: int | None = None
    theme_id: int | None = None
    num_parts: int = 0
    img_local_path: str | None = None
    source_img_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    last_synced_at: datetime = Field(default_factory=utcnow)
    sorting_finished_at: datetime | None = None


class ThemeTable(SQLModel, table=True):
    """Cached copy of the upstream theme tree. `parent_id` is a self-reference, left unconstrained
    because themes arrive in an arbitrary order and a missing parent should not block the insert."""

    __tablename__ = "themes"

    id: int = Field(primary_key=True)
    parent_id: int | None = Field(default=None, index=True)
    name: str
    updated_at: datetime = Field(default_factory=utcnow)


class SetPartTable(SQLModel, table=True):
    __tablename__ = "set_parts"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: int | None = Field(default=None, primary_key=True)
    set_num: str = Field(foreign_key="sets.set_num", index=True)
    part_num: str = Field(index=True)
    color_id: int
    color_name: str
    part_name: str
    element_id: str | None = None
    quantity_required: int
    quantity_found: int = 0
    quantity_broken: int = 0
    is_spare: bool = False
    img_local_path: str | None = None
    source_img_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MinifigTable(SQLModel, table=True):
    __tablename__ = "minifigs"

    fig_num: str = Field(primary_key=True)
    name: str
    num_parts: int | None = None
    img_local_path: str | None = None
    source_img_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    last_synced_at: datetime = Field(default_factory=utcnow)


class MinifigPartTable(SQLModel, table=True):
    __tablename__ = "minifig_parts"

    id: int | None = Field(default=None, primary_key=True)
    fig_num: str = Field(foreign_key="minifigs.fig_num", index=True)
    part_num: str = Field(index=True)
    color_id: int
    color_name: str
    part_name: str
    element_id: str | None = None
    quantity_required: int
    img_local_path: str | None = None
    source_img_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MinifigInstanceTable(SQLModel, table=True):
    __tablename__ = "minifig_instances"

    id: str = Field(primary_key=True)
    fig_num: str = Field(foreign_key="minifigs.fig_num", index=True)
    fig_name: str
    img_local_path: str | None = None
    source_set_num: str | None = Field(default=None, foreign_key="sets.set_num", index=True)
    """Null for a loose minifig that no owned set introduced."""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    sorting_finished_at: datetime | None = None


class MinifigInstancePartTable(SQLModel, table=True):
    __tablename__ = "minifig_instance_parts"

    id: int | None = Field(default=None, primary_key=True)
    instance_id: str = Field(foreign_key="minifig_instances.id", index=True)
    part_num: str = Field(index=True)
    color_id: int
    color_name: str
    part_name: str
    element_id: str | None = None
    quantity_required: int
    quantity_found: int = 0
    quantity_broken: int = 0
    img_local_path: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MissingHistoryTable(SQLModel, table=True):
    __tablename__ = "missing_history"

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    part_num: str
    color_id: int
    action: str
    quantity_before: int
    quantity_after: int
    timestamp: datetime = Field(default_factory=utcnow)
