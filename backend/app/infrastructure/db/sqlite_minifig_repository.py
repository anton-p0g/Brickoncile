from sqlmodel import Session, select

from app.domain.entities import Minifig, Part
from app.infrastructure.db.models import MinifigPartTable, MinifigTable, utcnow


class SqliteMinifigRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, fig_num: str) -> Minifig | None:
        row = self.session.get(MinifigTable, fig_num)
        if row is None:
            return None
        return self._to_entity(row)

    def save(self, minifig: Minifig) -> None:
        existing = self.session.get(MinifigTable, minifig.fig_num)
        if existing is None:
            self.session.add(
                MinifigTable(
                    fig_num=minifig.fig_num,
                    name=minifig.name,
                    num_parts=minifig.num_parts,
                    img_local_path=minifig.image_path,
                    last_synced_at=minifig.last_synced_at,
                )
            )
        else:
            existing.name = minifig.name
            existing.num_parts = minifig.num_parts
            existing.img_local_path = minifig.image_path or existing.img_local_path
            existing.last_synced_at = minifig.last_synced_at
            existing.updated_at = utcnow()
            self.session.add(existing)

        for part in minifig.parts:
            self._upsert_part(minifig.fig_num, part)

        self.session.commit()

    def delete(self, fig_num: str) -> None:
        """Drop a catalog entry and its part template. Only sound once no instance references it."""
        part_rows = self.session.exec(select(MinifigPartTable).where(MinifigPartTable.fig_num == fig_num)).all()
        for row in part_rows:
            self.session.delete(row)
        fig_row = self.session.get(MinifigTable, fig_num)
        if fig_row is not None:
            self.session.delete(fig_row)
        self.session.commit()

    def list_referenced_image_paths(self) -> set[str]:
        fig_images = self.session.exec(select(MinifigTable.img_local_path)).all()
        part_images = self.session.exec(select(MinifigPartTable.img_local_path)).all()
        return {path for path in (*fig_images, *part_images) if path}

    def _upsert_part(self, fig_num: str, part: Part) -> None:
        stmt = select(MinifigPartTable).where(
            MinifigPartTable.fig_num == fig_num,
            MinifigPartTable.part_num == part.part_num,
            MinifigPartTable.color_id == part.color_id,
        )
        row = self.session.exec(stmt).first()
        if row is None:
            row = MinifigPartTable(
                fig_num=fig_num,
                part_num=part.part_num,
                color_id=part.color_id,
                color_name=part.color_name,
                part_name=part.name,
                element_id=part.element_id,
                quantity_required=part.quantity_required,
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

    def _to_entity(self, row: MinifigTable) -> Minifig:
        part_rows = self.session.exec(select(MinifigPartTable).where(MinifigPartTable.fig_num == row.fig_num)).all()
        parts = [
            Part(
                part_num=p.part_num,
                color_id=p.color_id,
                color_name=p.color_name,
                name=p.part_name,
                element_id=p.element_id,
                quantity_required=p.quantity_required,
                quantity_found=0,
                image_path=p.img_local_path,
                is_spare=False,
            )
            for p in part_rows
        ]
        return Minifig(
            fig_num=row.fig_num,
            name=row.name,
            num_parts=row.num_parts,
            image_path=row.img_local_path,
            last_synced_at=row.last_synced_at,
            parts=parts,
        )
