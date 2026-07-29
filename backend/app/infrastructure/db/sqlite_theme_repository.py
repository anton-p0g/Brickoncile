from sqlmodel import Session, select

from app.domain.entities import Theme
from app.infrastructure.db.models import ThemeTable, utcnow


class SqliteThemeRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[Theme]:
        rows = self.session.exec(select(ThemeTable)).all()
        return [self._to_entity(row) for row in rows]

    def get_by_id(self) -> dict[int, Theme]:
        return {theme.id: theme for theme in self.list_all()}

    def upsert_many(self, themes: list[Theme]) -> None:
        for theme in themes:
            row = self.session.get(ThemeTable, theme.id)
            if row is None:
                row = ThemeTable(id=theme.id, parent_id=theme.parent_id, name=theme.name)
            else:
                row.parent_id = theme.parent_id
                row.name = theme.name
                row.updated_at = utcnow()
            self.session.add(row)
        self.session.commit()

    def count(self) -> int:
        return len(self.session.exec(select(ThemeTable.id)).all())

    def _to_entity(self, row: ThemeTable) -> Theme:
        return Theme(id=row.id, parent_id=row.parent_id, name=row.name)
