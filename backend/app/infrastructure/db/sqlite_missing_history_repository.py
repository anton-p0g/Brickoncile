from datetime import UTC, datetime

from sqlmodel import Session, select

from app.domain.entities import EntityType, MissingPartRecord
from app.infrastructure.db.models import MissingHistoryTable


def _as_utc(timestamp: datetime) -> datetime:
    """SQLite drops tzinfo on the way out. Timestamps are always written as UTC, so restore it
    here rather than letting a naive datetime reach the API and get read as local time."""
    return timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp


class SqliteMissingHistoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def append(self, record: MissingPartRecord) -> None:
        self.session.add(
            MissingHistoryTable(
                entity_type=record.entity_type,
                entity_id=record.entity_id,
                part_num=record.part_num,
                color_id=record.color_id,
                action=record.action,
                quantity_before=record.quantity_before,
                quantity_after=record.quantity_after,
                timestamp=record.timestamp,
            )
        )
        self.session.commit()

    def list_for_entity(
        self, entity_type: EntityType, entity_id: str, part_num: str | None = None, color_id: int | None = None
    ) -> list[MissingPartRecord]:
        stmt = select(MissingHistoryTable).where(
            MissingHistoryTable.entity_type == entity_type,
            MissingHistoryTable.entity_id == entity_id,
        )
        if part_num is not None:
            stmt = stmt.where(MissingHistoryTable.part_num == part_num)
        if color_id is not None:
            stmt = stmt.where(MissingHistoryTable.color_id == color_id)
        stmt = stmt.order_by(MissingHistoryTable.timestamp)

        return [
            MissingPartRecord(
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                part_num=row.part_num,
                color_id=row.color_id,
                action=row.action,
                quantity_before=row.quantity_before,
                quantity_after=row.quantity_after,
                timestamp=_as_utc(row.timestamp),
            )
            for row in self.session.exec(stmt).all()
        ]

    def delete_for_entity(self, entity_type: EntityType, entity_id: str) -> None:
        stmt = select(MissingHistoryTable).where(
            MissingHistoryTable.entity_type == entity_type,
            MissingHistoryTable.entity_id == entity_id,
        )
        for row in self.session.exec(stmt).all():
            self.session.delete(row)
        self.session.commit()

    def exists_for_part(self, entity_type: EntityType, entity_id: str, part_num: str, color_id: int) -> bool:
        stmt = select(MissingHistoryTable).where(
            MissingHistoryTable.entity_type == entity_type,
            MissingHistoryTable.entity_id == entity_id,
            MissingHistoryTable.part_num == part_num,
            MissingHistoryTable.color_id == color_id,
        )
        return self.session.exec(stmt).first() is not None
