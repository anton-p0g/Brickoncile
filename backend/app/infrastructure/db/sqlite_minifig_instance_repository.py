from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, select

from app.domain.entities import MinifigInstance, Part
from app.domain.errors import EntityNotFoundError
from app.domain.repositories.dtos import PartFoundUpdate
from app.infrastructure.db.models import (
    MinifigInstancePartTable,
    MinifigInstanceTable,
    utcnow,
)


def _as_utc(timestamp: datetime) -> datetime:
    """SQLite drops tzinfo on the way out; timestamps are always written as UTC."""
    return timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp


class SqliteMinifigInstanceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, instance_id: str) -> MinifigInstance | None:
        row = self.session.get(MinifigInstanceTable, instance_id)
        if row is None:
            return None
        return self._to_entity(row)

    def list_all(self) -> list[MinifigInstance]:
        rows = self.session.exec(select(MinifigInstanceTable)).all()
        return [self._to_entity(row) for row in rows]

    def list_by_source_set(self, set_num: str) -> list[MinifigInstance]:
        stmt = select(MinifigInstanceTable).where(MinifigInstanceTable.source_set_num == set_num)
        return [self._to_entity(row) for row in self.session.exec(stmt).all()]

    def list_by_fig_num(self, fig_num: str) -> list[MinifigInstance]:
        stmt = select(MinifigInstanceTable).where(MinifigInstanceTable.fig_num == fig_num)
        return [self._to_entity(row) for row in self.session.exec(stmt).all()]

    def count_by_fig_and_set(self, fig_num: str, source_set_num: str) -> int:
        stmt = select(MinifigInstanceTable).where(
            MinifigInstanceTable.fig_num == fig_num,
            MinifigInstanceTable.source_set_num == source_set_num,
        )
        return len(self.session.exec(stmt).all())

    def create(
        self,
        fig_num: str,
        fig_name: str,
        image_path: str | None,
        source_set_num: str | None,
        parts_template: list[Part],
    ) -> MinifigInstance:
        instance_id = str(uuid4())
        self.session.add(
            MinifigInstanceTable(
                id=instance_id,
                fig_num=fig_num,
                fig_name=fig_name,
                img_local_path=image_path,
                source_set_num=source_set_num,
            )
        )
        for part in parts_template:
            self.session.add(
                MinifigInstancePartTable(
                    instance_id=instance_id,
                    part_num=part.part_num,
                    color_id=part.color_id,
                    color_name=part.color_name,
                    part_name=part.name,
                    element_id=part.element_id,
                    quantity_required=part.quantity_required,
                    quantity_found=0,
                    quantity_broken=0,
                    img_local_path=part.image_path,
                )
            )
        self.session.commit()
        entity = self.get(instance_id)
        assert entity is not None
        return entity

    def delete(self, instance_id: str) -> None:
        """Remove one physical instance and its part rows. The shared `minifigs`/`minifig_parts`
        catalog entries stay put, since they are cached upstream data, not ownership."""
        part_rows = self.session.exec(
            select(MinifigInstancePartTable).where(MinifigInstancePartTable.instance_id == instance_id)
        ).all()
        for row in part_rows:
            self.session.delete(row)
        instance_row = self.session.get(MinifigInstanceTable, instance_id)
        if instance_row is not None:
            self.session.delete(instance_row)
        self.session.commit()

    def list_referenced_image_paths(self) -> set[str]:
        instance_images = self.session.exec(select(MinifigInstanceTable.img_local_path)).all()
        part_images = self.session.exec(select(MinifigInstancePartTable.img_local_path)).all()
        return {path for path in (*instance_images, *part_images) if path}

    def get_part(self, instance_id: str, part_num: str, color_id: int) -> Part | None:
        row = self._get_part_row(instance_id, part_num, color_id)
        if row is None:
            return None
        return self._to_part(row)

    def update_part_found(self, instance_id: str, part_num: str, color_id: int, quantity_found: int) -> Part:
        row = self._get_part_row(instance_id, part_num, color_id)
        if row is None:
            raise EntityNotFoundError(f"part {part_num}/{color_id} not found on minifig instance {instance_id}")
        row.quantity_found = max(0, min(row.quantity_required, quantity_found))
        row.quantity_broken = min(row.quantity_broken, row.quantity_found)
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return self._to_part(row)

    def update_part_condition(
        self,
        instance_id: str,
        part_num: str,
        color_id: int,
        quantity_found: int,
        quantity_broken: int,
    ) -> Part:
        row = self._get_part_row(instance_id, part_num, color_id)
        if row is None:
            raise EntityNotFoundError(f"part {part_num}/{color_id} not found on minifig instance {instance_id}")
        row.quantity_found = max(0, min(row.quantity_required, quantity_found))
        row.quantity_broken = max(0, min(row.quantity_found, quantity_broken))
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return self._to_part(row)

    def update_parts_found(self, instance_id: str, updates: list[PartFoundUpdate]) -> list[Part]:
        """See SqliteSetRepository.update_parts_found."""
        rows = self.session.exec(
            select(MinifigInstancePartTable).where(MinifigInstancePartTable.instance_id == instance_id)
        ).all()
        by_key = {(row.part_num, row.color_id): row for row in rows}

        written: list[MinifigInstancePartTable] = []
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

    def set_sorting_finished(self, instance_id: str, finished_at: datetime | None) -> None:
        row = self.session.get(MinifigInstanceTable, instance_id)
        if row is None:
            raise EntityNotFoundError(f"minifig instance {instance_id} not found")
        row.sorting_finished_at = finished_at
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()

    def sync_parts_template(self, fig_num: str, template_parts: list[Part]) -> None:
        instances = self.session.exec(
            select(MinifigInstanceTable).where(MinifigInstanceTable.fig_num == fig_num)
        ).all()
        template_keys = {(p.part_num, p.color_id) for p in template_parts}

        for instance in instances:
            existing_rows = self.session.exec(
                select(MinifigInstancePartTable).where(MinifigInstancePartTable.instance_id == instance.id)
            ).all()
            existing_by_key = {(r.part_num, r.color_id): r for r in existing_rows}

            for part in template_parts:
                key = (part.part_num, part.color_id)
                row = existing_by_key.get(key)
                if row is None:
                    row = MinifigInstancePartTable(
                        instance_id=instance.id,
                        part_num=part.part_num,
                        color_id=part.color_id,
                        color_name=part.color_name,
                        part_name=part.name,
                        element_id=part.element_id,
                        quantity_required=part.quantity_required,
                        quantity_found=0,
                        quantity_broken=0,
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

            for key, row in existing_by_key.items():
                if key not in template_keys:
                    row.quantity_required = 0
                    row.updated_at = utcnow()
                    self.session.add(row)

        self.session.commit()

    def _get_part_row(self, instance_id: str, part_num: str, color_id: int) -> MinifigInstancePartTable | None:
        stmt = select(MinifigInstancePartTable).where(
            MinifigInstancePartTable.instance_id == instance_id,
            MinifigInstancePartTable.part_num == part_num,
            MinifigInstancePartTable.color_id == color_id,
        )
        return self.session.exec(stmt).first()

    def _to_entity(self, row: MinifigInstanceTable) -> MinifigInstance:
        part_rows = self.session.exec(
            select(MinifigInstancePartTable).where(MinifigInstancePartTable.instance_id == row.id)
        ).all()
        return MinifigInstance(
            id=row.id,
            fig_num=row.fig_num,
            fig_name=row.fig_name,
            image_path=row.img_local_path,
            source_set_num=row.source_set_num,
            added_at=_as_utc(row.created_at),
            sorting_finished_at=_as_utc(row.sorting_finished_at) if row.sorting_finished_at else None,
            parts=[self._to_part(p) for p in part_rows],
        )

    def _to_part(self, row: MinifigInstancePartTable) -> Part:
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
            is_spare=False,
        )
