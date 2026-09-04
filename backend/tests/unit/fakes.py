from datetime import datetime
from uuid import uuid4

from app.domain.entities import (
    EntityType,
    LegoSet,
    Minifig,
    MinifigInstance,
    MissingPartRecord,
    Part,
    Theme,
)
from app.domain.errors import (
    EntityNotFoundError,
    ImageRecognitionUnavailableError,
    PartsCatalogNotFoundError,
)
from app.domain.repositories.dtos import (
    MinifigMetadataDTO,
    MinifigRecognitionDTO,
    MinifigRosterEntryDTO,
    MinifigSearchResultDTO,
    PartDTO,
    PartFoundUpdate,
    SetMetadataDTO,
    ThemeDTO,
)


class FakeImageCache:
    """No real I/O: pretends every remote_url downloads instantly to a deterministic path."""

    def __init__(self):
        self.deleted: list[str] = []

    async def get_or_download(self, remote_url: str | None, category: str, key: str) -> str | None:
        if remote_url is None:
            return None
        return f"{category}/{key}.jpg"

    def delete(self, relative_path: str) -> None:
        self.deleted.append(relative_path)


class FakePartsCatalogClient:
    def __init__(
        self,
        sets: dict[str, SetMetadataDTO] | None = None,
        set_parts: dict[str, list[PartDTO]] | None = None,
        set_minifigs: dict[str, list[MinifigRosterEntryDTO]] | None = None,
        minifigs: dict[str, MinifigMetadataDTO] | None = None,
        minifig_parts: dict[str, list[PartDTO]] | None = None,
        themes: list[ThemeDTO] | None = None,
        minifig_search: dict[str, list[MinifigSearchResultDTO]] | None = None,
    ):
        self.sets = sets or {}
        self.set_parts = set_parts or {}
        self.set_minifigs = set_minifigs or {}
        self.minifigs = minifigs or {}
        self.minifig_parts = minifig_parts or {}
        self.themes = themes or []
        self.theme_fetches = 0
        self.minifig_search = minifig_search or {}
        self.search_queries: list[str] = []

    async def fetch_set_metadata(self, set_num: str) -> SetMetadataDTO:
        if set_num not in self.sets:
            raise PartsCatalogNotFoundError(set_num)
        return self.sets[set_num]

    async def fetch_set_parts(self, set_num: str) -> list[PartDTO]:
        return self.set_parts.get(set_num, [])

    async def fetch_set_minifigs(self, set_num: str) -> list[MinifigRosterEntryDTO]:
        return self.set_minifigs.get(set_num, [])

    async def fetch_minifig_metadata(self, fig_num: str) -> MinifigMetadataDTO:
        if fig_num not in self.minifigs:
            raise PartsCatalogNotFoundError(fig_num)
        return self.minifigs[fig_num]

    async def fetch_minifig_parts(self, fig_num: str) -> list[PartDTO]:
        return self.minifig_parts.get(fig_num, [])

    async def fetch_themes(self) -> list[ThemeDTO]:
        self.theme_fetches += 1
        return list(self.themes)

    async def search_minifigs(self, query: str, limit: int) -> list[MinifigSearchResultDTO]:
        # Queries are recorded so tests can assert how a name was narrowed, not just what it found.
        self.search_queries.append(query)
        return self.minifig_search.get(query, [])[:limit]


class FakeMinifigRecognizer:
    def __init__(
        self,
        recognitions: list[MinifigRecognitionDTO] | None = None,
        unavailable: bool = False,
    ):
        self.recognitions = recognitions or []
        self.unavailable = unavailable
        self.calls: list[tuple[bytes, str]] = []

    async def identify(
        self, image_bytes: bytes, filename: str, content_type: str | None = None
    ) -> list[MinifigRecognitionDTO]:
        if self.unavailable:
            raise ImageRecognitionUnavailableError("recogniser is down")
        self.calls.append((image_bytes, filename))
        return list(self.recognitions)


class FakeThemeRepository:
    def __init__(self, themes: list[Theme] | None = None):
        self._themes: dict[int, Theme] = {t.id: t for t in (themes or [])}

    def list_all(self) -> list[Theme]:
        return [t.model_copy() for t in self._themes.values()]

    def get_by_id(self) -> dict[int, Theme]:
        return {t.id: t.model_copy() for t in self._themes.values()}

    def upsert_many(self, themes: list[Theme]) -> None:
        for theme in themes:
            self._themes[theme.id] = theme.model_copy()

    def count(self) -> int:
        return len(self._themes)


class FakeSetRepository:
    def __init__(self):
        self._sets: dict[str, LegoSet] = {}

    def get(self, set_num: str) -> LegoSet | None:
        existing = self._sets.get(set_num)
        return existing.model_copy(deep=True) if existing else None

    def list_all(self) -> list[LegoSet]:
        return [s.model_copy(deep=True) for s in self._sets.values()]

    def save(self, set_: LegoSet) -> None:
        existing = self._sets.get(set_.set_num)
        if existing is None:
            self._sets[set_.set_num] = set_.model_copy(deep=True)
            return

        existing.name = set_.name
        existing.year = set_.year
        existing.theme_id = set_.theme_id
        existing.num_parts = set_.num_parts
        existing.image_path = set_.image_path or existing.image_path
        existing.last_synced_at = set_.last_synced_at

        by_key = {(p.part_num, p.color_id, p.is_spare): p for p in existing.parts}
        for incoming in set_.parts:
            key = (incoming.part_num, incoming.color_id, incoming.is_spare)
            current = by_key.get(key)
            if current is None:
                existing.parts.append(incoming.model_copy())
            else:
                current.color_name = incoming.color_name
                current.name = incoming.name
                current.element_id = incoming.element_id
                current.quantity_required = incoming.quantity_required
                current.image_path = incoming.image_path or current.image_path

    def delete(self, set_num: str) -> None:
        self._sets.pop(set_num, None)

    def list_referenced_image_paths(self) -> set[str]:
        paths = set()
        for s in self._sets.values():
            paths |= {p for p in (s.image_path, *(part.image_path for part in s.parts)) if p}
        return paths

    def get_part(self, set_num: str, part_num: str, color_id: int) -> Part | None:
        s = self._sets.get(set_num)
        if s is None:
            return None
        for p in s.parts:
            # Spares are skipped: they can duplicate a build part's part/colour, and only the
            # build part is tracked. Mirrors SqliteSetRepository.
            if p.part_num == part_num and p.color_id == color_id and not p.is_spare:
                return p.model_copy()
        return None

    def update_part_found(self, set_num: str, part_num: str, color_id: int, quantity_found: int) -> Part:
        s = self._sets.get(set_num)
        if s is None:
            raise EntityNotFoundError(set_num)
        for p in s.parts:
            if p.part_num == part_num and p.color_id == color_id and not p.is_spare:
                p.quantity_found = max(0, min(p.quantity_required, quantity_found))
                p.quantity_broken = min(p.quantity_broken, p.quantity_found)
                return p.model_copy()
        raise EntityNotFoundError(f"{part_num}/{color_id}")

    def update_part_condition(
        self,
        set_num: str,
        part_num: str,
        color_id: int,
        quantity_found: int,
        quantity_broken: int,
    ) -> Part:
        s = self._sets.get(set_num)
        if s is None:
            raise EntityNotFoundError(set_num)
        for p in s.parts:
            if p.part_num == part_num and p.color_id == color_id and not p.is_spare:
                p.quantity_found = max(0, min(p.quantity_required, quantity_found))
                p.quantity_broken = max(0, min(p.quantity_found, quantity_broken))
                return p.model_copy()
        raise EntityNotFoundError(f"{part_num}/{color_id}")

    def update_parts_found(self, set_num: str, updates: list[PartFoundUpdate]) -> list[Part]:
        s = self._sets.get(set_num)
        if s is None:
            raise EntityNotFoundError(set_num)
        by_key = {(p.part_num, p.color_id): p for p in s.parts if not p.is_spare}
        written = []
        for update in updates:
            part = by_key.get((update.part_num, update.color_id))
            if part is None:
                continue
            part.quantity_found = max(0, min(part.quantity_required, update.quantity_found))
            part.quantity_broken = min(part.quantity_broken, part.quantity_found)
            written.append(part.model_copy())
        return written

    def set_sorting_finished(self, set_num: str, finished_at: datetime | None) -> None:
        s = self._sets.get(set_num)
        if s is None:
            raise EntityNotFoundError(set_num)
        s.sorting_finished_at = finished_at

    def prune_parts_not_in(self, set_num: str, keep_keys: set[tuple[str, int, bool]]) -> None:
        s = self._sets.get(set_num)
        if s is None:
            return
        for p in s.parts:
            if (p.part_num, p.color_id, p.is_spare) not in keep_keys:
                p.quantity_required = 0


class FakeMinifigRepository:
    def __init__(self):
        self._minifigs: dict[str, Minifig] = {}

    def get(self, fig_num: str) -> Minifig | None:
        existing = self._minifigs.get(fig_num)
        return existing.model_copy(deep=True) if existing else None

    def delete(self, fig_num: str) -> None:
        self._minifigs.pop(fig_num, None)

    def list_referenced_image_paths(self) -> set[str]:
        paths = set()
        for m in self._minifigs.values():
            paths |= {p for p in (m.image_path, *(part.image_path for part in m.parts)) if p}
        return paths

    def save(self, minifig: Minifig) -> None:
        existing = self._minifigs.get(minifig.fig_num)
        if existing is None:
            self._minifigs[minifig.fig_num] = minifig.model_copy(deep=True)
            return

        existing.name = minifig.name
        existing.num_parts = minifig.num_parts
        existing.image_path = minifig.image_path or existing.image_path
        existing.last_synced_at = minifig.last_synced_at

        by_key = {(p.part_num, p.color_id): p for p in existing.parts}
        for incoming in minifig.parts:
            key = (incoming.part_num, incoming.color_id)
            current = by_key.get(key)
            if current is None:
                existing.parts.append(incoming.model_copy())
            else:
                current.color_name = incoming.color_name
                current.name = incoming.name
                current.element_id = incoming.element_id
                current.quantity_required = incoming.quantity_required
                current.image_path = incoming.image_path or current.image_path


class FakeMinifigInstanceRepository:
    def __init__(self):
        self._instances: dict[str, MinifigInstance] = {}

    def get(self, instance_id: str) -> MinifigInstance | None:
        existing = self._instances.get(instance_id)
        return existing.model_copy(deep=True) if existing else None

    def list_all(self) -> list[MinifigInstance]:
        return [i.model_copy(deep=True) for i in self._instances.values()]

    def list_by_source_set(self, set_num: str) -> list[MinifigInstance]:
        return [i.model_copy(deep=True) for i in self._instances.values() if i.source_set_num == set_num]

    def list_by_fig_num(self, fig_num: str) -> list[MinifigInstance]:
        return [i.model_copy(deep=True) for i in self._instances.values() if i.fig_num == fig_num]

    def count_by_fig_and_set(self, fig_num: str, source_set_num: str) -> int:
        return sum(
            1 for i in self._instances.values() if i.fig_num == fig_num and i.source_set_num == source_set_num
        )

    def create(
        self,
        fig_num: str,
        fig_name: str,
        image_path: str | None,
        source_set_num: str | None,
        parts_template: list[Part],
    ) -> MinifigInstance:
        instance = MinifigInstance(
            id=str(uuid4()),
            fig_num=fig_num,
            fig_name=fig_name,
            image_path=image_path,
            source_set_num=source_set_num,
            parts=[p.model_copy(update={"quantity_found": 0, "quantity_broken": 0}) for p in parts_template],
        )
        self._instances[instance.id] = instance
        return instance.model_copy(deep=True)

    def delete(self, instance_id: str) -> None:
        self._instances.pop(instance_id, None)

    def list_referenced_image_paths(self) -> set[str]:
        paths = set()
        for i in self._instances.values():
            paths |= {p for p in (i.image_path, *(part.image_path for part in i.parts)) if p}
        return paths

    def get_part(self, instance_id: str, part_num: str, color_id: int) -> Part | None:
        instance = self._instances.get(instance_id)
        if instance is None:
            return None
        for p in instance.parts:
            if p.part_num == part_num and p.color_id == color_id:
                return p.model_copy()
        return None

    def update_part_found(self, instance_id: str, part_num: str, color_id: int, quantity_found: int) -> Part:
        instance = self._instances.get(instance_id)
        if instance is None:
            raise EntityNotFoundError(instance_id)
        for p in instance.parts:
            if p.part_num == part_num and p.color_id == color_id:
                p.quantity_found = max(0, min(p.quantity_required, quantity_found))
                p.quantity_broken = min(p.quantity_broken, p.quantity_found)
                return p.model_copy()
        raise EntityNotFoundError(f"{part_num}/{color_id}")

    def update_part_condition(
        self,
        instance_id: str,
        part_num: str,
        color_id: int,
        quantity_found: int,
        quantity_broken: int,
    ) -> Part:
        instance = self._instances.get(instance_id)
        if instance is None:
            raise EntityNotFoundError(instance_id)
        for p in instance.parts:
            if p.part_num == part_num and p.color_id == color_id:
                p.quantity_found = max(0, min(p.quantity_required, quantity_found))
                p.quantity_broken = max(0, min(p.quantity_found, quantity_broken))
                return p.model_copy()
        raise EntityNotFoundError(f"{part_num}/{color_id}")

    def update_parts_found(self, instance_id: str, updates: list[PartFoundUpdate]) -> list[Part]:
        instance = self._instances.get(instance_id)
        if instance is None:
            raise EntityNotFoundError(instance_id)
        by_key = {(p.part_num, p.color_id): p for p in instance.parts}
        written = []
        for update in updates:
            part = by_key.get((update.part_num, update.color_id))
            if part is None:
                continue
            part.quantity_found = max(0, min(part.quantity_required, update.quantity_found))
            part.quantity_broken = min(part.quantity_broken, part.quantity_found)
            written.append(part.model_copy())
        return written

    def set_sorting_finished(self, instance_id: str, finished_at: datetime | None) -> None:
        instance = self._instances.get(instance_id)
        if instance is None:
            raise EntityNotFoundError(instance_id)
        instance.sorting_finished_at = finished_at

    def sync_parts_template(self, fig_num: str, template_parts: list[Part]) -> None:
        template_keys = {(p.part_num, p.color_id) for p in template_parts}
        for instance in self._instances.values():
            if instance.fig_num != fig_num:
                continue
            by_key = {(p.part_num, p.color_id): p for p in instance.parts}
            for template_part in template_parts:
                key = (template_part.part_num, template_part.color_id)
                current = by_key.get(key)
                if current is None:
                    instance.parts.append(
                        template_part.model_copy(update={"quantity_found": 0, "quantity_broken": 0})
                    )
                else:
                    current.color_name = template_part.color_name
                    current.name = template_part.name
                    current.element_id = template_part.element_id
                    current.quantity_required = template_part.quantity_required
                    current.image_path = template_part.image_path or current.image_path
            for p in instance.parts:
                if (p.part_num, p.color_id) not in template_keys:
                    p.quantity_required = 0


class FakeMissingHistoryRepository:
    def __init__(self):
        self.records: list[MissingPartRecord] = []

    def append(self, record: MissingPartRecord) -> None:
        self.records.append(record)

    def list_for_entity(
        self, entity_type: EntityType, entity_id: str, part_num: str | None = None, color_id: int | None = None
    ) -> list[MissingPartRecord]:
        return [
            r
            for r in self.records
            if r.entity_type == entity_type
            and r.entity_id == entity_id
            and (part_num is None or r.part_num == part_num)
            and (color_id is None or r.color_id == color_id)
        ]

    def list_all(self) -> list[MissingPartRecord]:
        return sorted(self.records, key=lambda r: r.timestamp)

    def delete_for_entity(self, entity_type: EntityType, entity_id: str) -> None:
        self.records = [
            r for r in self.records if not (r.entity_type == entity_type and r.entity_id == entity_id)
        ]

    def exists_for_part(self, entity_type: EntityType, entity_id: str, part_num: str, color_id: int) -> bool:
        return any(
            r.entity_type == entity_type and r.entity_id == entity_id and r.part_num == part_num and r.color_id == color_id
            for r in self.records
        )


def make_set_metadata_dto(set_num: str = "75192-1", **overrides) -> SetMetadataDTO:
    defaults = {
        "set_num": set_num,
        "name": "Millennium Falcon",
        "year": 2017,
        "theme_id": 1,
        "num_parts": 2,
        "image_url": "https://example.com/set.jpg",
    }
    defaults.update(overrides)
    return SetMetadataDTO(**defaults)


def make_part_dto(part_num: str = "3001", color_id: int = 0, **overrides) -> PartDTO:
    defaults = {
        "part_num": part_num,
        "color_id": color_id,
        "color_name": "Black",
        "part_name": "Brick 2x4",
        "element_id": "300101",
        "quantity": 4,
        "is_spare": False,
        "image_url": "https://example.com/part.jpg",
    }
    defaults.update(overrides)
    return PartDTO(**defaults)


def make_theme_dtos() -> list[ThemeDTO]:
    """A two-level slice of the real tree: "Constraction" sits under "Legends of Chima", the shape
    that makes root resolution necessary."""
    return [
        ThemeDTO(id=571, parent_id=None, name="Legends of Chima"),
        ThemeDTO(id=573, parent_id=571, name="Constraction"),
        ThemeDTO(id=435, parent_id=None, name="Ninjago"),
    ]


def make_minifig_metadata_dto(fig_num: str = "sw0001", **overrides) -> MinifigMetadataDTO:
    defaults = {
        "fig_num": fig_num,
        "name": "Luke Skywalker",
        "num_parts": 7,
        "image_url": "https://example.com/fig.jpg",
    }
    defaults.update(overrides)
    return MinifigMetadataDTO(**defaults)
