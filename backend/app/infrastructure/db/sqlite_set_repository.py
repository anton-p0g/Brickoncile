from datetime import UTC, datetime

from sqlmodel import Session, select

from app.domain.entities import LegoSet, Part
from app.domain.errors import EntityNotFoundError
from app.domain.repositories.dtos import PartFoundUpdate
from app.infrastructure.db.models import (
    SetPartTable,
    SetTable,
    utcnow,
)


def _as_utc(timestamp: datetime) -> datetime:
    """SQLite drops tzinfo on the way out; timestamps are always written as UTC."""
    return timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp


class SqliteSetRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, set_num: str) -> LegoSet | None:
        row = self.session.get(SetTable, set_num)
        if row is None:
            return None
        return self._to_entity(row)

    def list_all(self) -> list[LegoSet]:
        rows = self.session.exec(select(SetTable)).all()
        return [self._to_entity(row) for row in rows]

    def save(self, set_: LegoSet) -> None:
        existing = self.session.get(SetTable, set_.set_num)
        if existing is None:
            self.session.add(
                SetTable(
                    set_num=set_.set_num,
                    name=set_.name,
                    year=set_.year,
                    theme_id=set_.theme_id,
                    num_parts=set_.num_parts,
                    img_local_path=set_.image_path,
                    last_synced_at=set_.last_synced_at,
                )
            )
        else:
            existing.name = set_.name
            existing.year = set_.year
            existing.theme_id = set_.theme_id
            existing.num_parts = set_.num_parts
            existing.img_local_path = set_.image_path or existing.img_local_path
            existing.last_synced_at = set_.last_synced_at
            existing.updated_at = utcnow()
            self.session.add(existing)

        for part in set_.parts:
            self._upsert_part(set_.set_num, part)

        self.session.commit()

    def delete(self, set_num: str) -> None:
        """Remove the set and its parts. Callers are responsible for the set's minifig instances
        and history rows, which live in other repositories."""
        part_rows = self.session.exec(select(SetPartTable).where(SetPartTable.set_num == set_num)).all()
        for row in part_rows:
            self.session.delete(row)
        set_row = self.session.get(SetTable, set_num)
        if set_row is not None:
            self.session.delete(set_row)
        self.session.commit()

    def list_referenced_image_paths(self) -> set[str]:
        set_images = self.session.exec(select(SetTable.img_local_path)).all()
        part_images = self.session.exec(select(SetPartTable.img_local_path)).all()
        return {path for path in (*set_images, *part_images) if path}

    def get_part(self, set_num: str, part_num: str, color_id: int) -> Part | None:
        row = self._get_part_row(set_num, part_num, color_id)
        if row is None:
            return None
        return self._to_part(row)

    def update_part_found(self, set_num: str, part_num: str, color_id: int, quantity_found: int) -> Part:
        row = self._get_part_row(set_num, part_num, color_id)
        if row is None:
            raise EntityNotFoundError(f"part {part_num}/{color_id} not found on set {set_num}")
        row.quantity_found = max(0, min(row.quantity_required, quantity_found))
        row.quantity_broken = min(row.quantity_broken, row.quantity_found)
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return self._to_part(row)

    def update_part_condition(
        self,
        set_num: str,
        part_num: str,
        color_id: int,
        quantity_found: int,
        quantity_broken: int,
    ) -> Part:
        row = self._get_part_row(set_num, part_num, color_id)
        if row is None:
            raise EntityNotFoundError(f"part {part_num}/{color_id} not found on set {set_num}")
        row.quantity_found = max(0, min(row.quantity_required, quantity_found))
        row.quantity_broken = max(0, min(row.quantity_found, quantity_broken))
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return self._to_part(row)

    def update_parts_found(self, set_num: str, updates: list[PartFoundUpdate]) -> list[Part]:
        # One read of the set's parts and one commit, rather than a round trip per part: confirming
        # a screenful of a 500-part set is a single request and should not be 500 transactions.
        rows = self.session.exec(
            select(SetPartTable).where(
                SetPartTable.set_num == set_num,
                SetPartTable.is_spare == False,
            )
        ).all()
        by_key = {(row.part_num, row.color_id): row for row in rows}

        written: list[SetPartTable] = []
        for update in updates:
            row = by_key.get((update.part_num, update.color_id))
            if row is None:
                continue
            row.quantity_found = max(0, min(row.quantity_required, update.quantity_found))
            row.quantity_broken = min(row.quantity_broken, row.quantity_found)
            row.updated_at = utcnow()
            self.session.add(row)
            written.append(row)

        self.session.commit()
        return [self._to_part(row) for row in written]

    def set_sorting_finished(self, set_num: str, finished_at: datetime | None) -> None:
        row = self.session.get(SetTable, set_num)
        if row is None:
            raise EntityNotFoundError(f"set {set_num} not found in local cache")
        row.sorting_finished_at = finished_at
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()

    def prune_parts_not_in(self, set_num: str, keep_keys: set[tuple[str, int, bool]]) -> None:
        rows = self.session.exec(select(SetPartTable).where(SetPartTable.set_num == set_num)).all()
        for row in rows:
            if (row.part_num, row.color_id, row.is_spare) not in keep_keys and row.quantity_required != 0:
                row.quantity_required = 0
                row.updated_at = utcnow()
                self.session.add(row)
        self.session.commit()

    def _get_part_row(self, set_num: str, part_num: str, color_id: int) -> SetPartTable | None:
        # A set's inventory can hold the same part/colour twice: once as a build part and once as a
        # spare, as separate upstream rows. Only the build row is tracked (spares are excluded from
        # every total and never shown), so it has to be named explicitly here. Without the is_spare
        # filter the lookup picks an arbitrary one of the two and writes land on the wrong row.
        stmt = select(SetPartTable).where(
            SetPartTable.set_num == set_num,
            SetPartTable.part_num == part_num,
            SetPartTable.color_id == color_id,
            SetPartTable.is_spare == False,
        )
        return self.session.exec(stmt).first()

    def _upsert_part(self, set_num: str, part: Part) -> None:
        stmt = select(SetPartTable).where(
            SetPartTable.set_num == set_num,
            SetPartTable.part_num == part.part_num,
            SetPartTable.color_id == part.color_id,
            SetPartTable.is_spare == part.is_spare,
        )
        row = self.session.exec(stmt).first()
        if row is None:
            row = SetPartTable(
                set_num=set_num,
                part_num=part.part_num,
                color_id=part.color_id,
                color_name=part.color_name,
                part_name=part.name,
                element_id=part.element_id,
                quantity_required=part.quantity_required,
                quantity_found=part.quantity_found,
                quantity_broken=part.quantity_broken,
                is_spare=part.is_spare,
                img_local_path=part.image_path,
            )
        else:
            row.color_name = part.color_name
            row.part_name = part.name
            row.element_id = part.element_id
            row.quantity_required = part.quantity_required
            row.img_local_path = part.image_path or row.img_local_path
            row.updated_at = utcnow()
        self.session.add(row)

    def _to_entity(self, row: SetTable) -> LegoSet:
        part_rows = self.session.exec(select(SetPartTable).where(SetPartTable.set_num == row.set_num)).all()
        return LegoSet(
            set_num=row.set_num,
            name=row.name,
            year=row.year,
            theme_id=row.theme_id,
            num_parts=row.num_parts,
            image_path=row.img_local_path,
            last_synced_at=row.last_synced_at,
            added_at=_as_utc(row.created_at),
            sorting_finished_at=_as_utc(row.sorting_finished_at) if row.sorting_finished_at else None,
            parts=[self._to_part(p) for p in part_rows],
        )

    def _to_part(self, row: SetPartTable) -> Part:
        return Part(
            part_num=row.part_num,
            color_id=row.color_id,
            color_name=row.color_name,
            name=row.part_name,
            element_id=row.element_id,
            quantity_required=row.quantity_required,
            quantity_found=row.quantity_found,
            quantity_broken=row.quantity_broken,
            image_path=row.img_local_path,
            is_spare=row.is_spare,
        )
