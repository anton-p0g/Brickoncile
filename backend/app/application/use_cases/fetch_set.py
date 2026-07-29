import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.use_cases._shared import build_parts_from_dtos
from app.application.use_cases.sync_minifig_roster import SyncMinifigRosterUseCase
from app.application.use_cases.sync_themes import SyncThemesUseCase
from app.domain.entities import LegoSet
from app.domain.errors import PartsCatalogNotFoundError, PartsCatalogUnavailableError
from app.domain.repositories import (
    ImageCache,
    PartsCatalogClient,
    SetRepository,
)

_VARIANT_SUFFIX_RE = re.compile(r"-\d+$")


@dataclass(frozen=True)
class FetchSetOutcome:
    lego_set: LegoSet
    """True when the set was already in the collection, so nothing was fetched or changed.
    Lets callers distinguish "added" from "you already own this" instead of reporting both
    as a successful add."""
    already_owned: bool
    warnings: tuple[str, ...] = ()
    """What did not land, for a set that did. Everything fetched after the set is saved (its
    theme names, its minifig roster) is reported this way rather than raised: the set and its
    parts are in the collection and usable, and a resync fills in the rest."""


class FetchSetUseCase:
    """Cache-once-fetch-forever for a set: metadata, parts, and its minifig roster."""

    def __init__(
        self,
        set_repo: SetRepository,
        catalog: PartsCatalogClient,
        images: ImageCache,
        sync_roster: SyncMinifigRosterUseCase,
        sync_themes: SyncThemesUseCase,
    ):
        self.set_repo = set_repo
        self.catalog = catalog
        self.images = images
        self.sync_roster = sync_roster
        self.sync_themes = sync_themes

    async def execute(self, set_num: str) -> LegoSet:
        return (await self.execute_with_outcome(set_num)).lego_set

    async def execute_with_outcome(self, set_num: str) -> FetchSetOutcome:
        set_num = self._normalize_set_num(set_num)

        cached = self.set_repo.get(set_num)
        if cached is not None:
            return FetchSetOutcome(lego_set=cached, already_owned=True)

        metadata = await self.catalog.fetch_set_metadata(set_num)
        part_dtos = await self.catalog.fetch_set_parts(set_num)

        image_path = await self.images.get_or_download(metadata.image_url, "sets", set_num)
        parts = await build_parts_from_dtos(self.images, part_dtos)

        lego_set = LegoSet(
            set_num=metadata.set_num,
            name=metadata.name,
            year=metadata.year,
            theme_id=metadata.theme_id,
            num_parts=metadata.num_parts,
            image_path=image_path,
            last_synced_at=datetime.now(UTC),
            parts=parts,
        )
        self.set_repo.save(lego_set)

        # Everything past this point is a follow-up fetch against a set that is already stored, so
        # a failure is collected and reported rather than raised. Throwing here would report the
        # set as failed while it sits on the dashboard, and would throw away the parts list —
        # the expensive half of the fetch — over a detail that a resync can fill in later.
        warnings: list[str] = []

        # The set carries only a theme_id; the dashboard groups by theme name, so make sure the
        # theme tree can resolve it before the set shows up ungrouped.
        try:
            await self.sync_themes.ensure_known(metadata.theme_id)
        except (PartsCatalogNotFoundError, PartsCatalogUnavailableError) as exc:
            warnings.append(f"theme names could not be refreshed ({self._reason(exc)})")

        try:
            await self.sync_roster.execute(set_num)
        except (PartsCatalogNotFoundError, PartsCatalogUnavailableError) as exc:
            warnings.append(
                f"minifigures could not be fetched ({self._reason(exc)}) — resync the set to finish"
            )

        return FetchSetOutcome(lego_set=lego_set, already_owned=False, warnings=tuple(warnings))

    @staticmethod
    def _reason(exc: Exception) -> str:
        return str(exc) or type(exc).__name__

    def _normalize_set_num(self, set_num: str) -> str:
        """LEGO manuals/boxes print the bare set number (e.g. "70202"), but Rebrickable's API
        requires the variant suffix (e.g. "70202-1"). Default to "-1", the correct variant
        for the vast majority of sets, when the user didn't type one."""
        set_num = set_num.strip()
        return set_num if _VARIANT_SUFFIX_RE.search(set_num) else f"{set_num}-1"
