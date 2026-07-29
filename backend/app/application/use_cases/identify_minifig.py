import asyncio
import logging
import re
from difflib import SequenceMatcher

from pydantic import BaseModel

from app.domain.repositories import (
    MinifigInstanceRepository,
    MinifigRecognizer,
    PartsCatalogClient,
)
from app.domain.repositories.dtos import MinifigRecognitionDTO, MinifigSearchResultDTO

logger = logging.getLogger(__name__)

MAX_RECOGNITIONS_CONSIDERED = 3
"""Guesses from the recogniser worth resolving. Each one costs catalog searches, and anything past
the third is far enough down the confidence list that it is noise rather than a real alternative."""

MAX_QUERIES_PER_RECOGNITION = 6
"""Queries stop at the first one that answers, so this budget is only ever spent in full on a name
that resolves late — which is exactly the case worth paying for."""

SEARCH_PAGE_SIZE = 20
MAX_MATCHES = 12

_RECOGNITION_WEIGHT = 0.4
_NAME_SIMILARITY_WEIGHT = 0.6
"""Within one guess every catalog hit shares the recogniser's score, so name similarity is what
separates them; across guesses the recogniser's score is what says which photo reading to trust."""

_PARENTHETICAL = re.compile(r"\([^)]*\)")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9 ]+")

_GENERIC_TERMS = frozenset(
    {"female", "male", "minifigure", "minifig", "series", "the", "with", "and", "of", "a"}
)
"""Words that describe every second minifig. Searching one on its own returns hundreds of unrelated
figures, so a query that reduces to just these is skipped rather than run."""

_TRUNCATION_LENGTHS = (4, 3, 2, 1)
"""Rebrickable's names are terser than the recogniser's ("Toy Store Employee" against "Female, Toy
Store Worker (LEGO Logo on Reverse of Torso)"), so when a full name finds nothing the fallback is
its opening words. Down to one, because a named character is often the whole catalog name:
"Sebulba - Dark Bluish Gray, Movable Arms" is catalogued as plain "Sebulba"."""

_SEGMENT_SEPARATOR = re.compile(r"\s+-\s+|,")
"""The recogniser reports BrickLink names, which qualify a figure with a dash before listing
variants after commas — "Sebulba - Dark Bluish Gray, Movable Arms". Both marks separate the name
proper from description, so both start a new segment."""


class OwnedInstanceRef(BaseModel):
    """An instance of this minifig already in the collection.

    A set can list the same fig_num more than once, so these are reported one per physical copy
    rather than one per set. `is_complete` is what tells them apart: it says which copies are
    already accounted for and which are still waiting to be found, so the figure in hand can be
    matched to a specific copy rather than to "a Sebulba somewhere in that set".
    """

    instance_id: str
    source_set_num: str | None
    source_set_name: str | None
    is_complete: bool
    quantity_found_total: int
    quantity_required_total: int


class MinifigMatch(BaseModel):
    fig_num: str
    name: str
    num_parts: int | None
    image_url: str | None
    """Rebrickable's picture of the catalog entry, for comparing against the photo."""
    score: float
    recognized_as: str
    """What the recogniser called it, which is usually the BrickLink name and worth showing when it
    differs from the catalog name — that difference is why a match needs confirming."""
    recognition_image_url: str | None
    reference_url: str | None
    """Where to check this guess by hand when the two catalogs' names disagree."""
    owned_instances: list[OwnedInstanceRef]
    """Non-empty when this minifig is already tracked, which turns "add it" into "here it is"."""


class IdentifyMinifigResult(BaseModel):
    recognitions: list[MinifigRecognitionDTO]
    """Every guess the recogniser returned, kept even when none resolved to a catalog entry so the
    UI can say what it thought it saw rather than only that it failed."""
    matches: list[MinifigMatch]


def normalize(name: str) -> str:
    without_parens = _PARENTHETICAL.sub(" ", name.lower())
    return " ".join(_NON_ALPHANUMERIC.sub(" ", without_parens).split())


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def build_queries(name: str, limit: int = MAX_QUERIES_PER_RECOGNITION) -> list[str]:
    """Catalog searches for a recogniser name, narrowest first.

    The two catalogs name the same figure differently, and the catalog's search wants every word to
    match, so the full name usually finds nothing. The recogniser's segments are the useful unit —
    "Female, Toy Store Worker" hides "Toy Store" inside it — and each is also tried shortened, since
    the surviving overlap between the two names tends to be its first word or two.

    Segments stay in the order they were written. BrickLink names lead with the figure and follow
    with description, so the earliest segment is the likeliest catalog name and deserves the budget
    before "Dark Bluish Gray" gets a turn.
    """
    cleaned = _clean(name)
    segments = [
        segment
        for segment in (_clean(part) for part in _SEGMENT_SEPARATOR.split(cleaned))
        if segment
    ]

    queries: list[str] = []
    _append(queries, cleaned)
    for segment in segments:
        _append(queries, segment)
    for segment in segments:
        words = segment.split()
        for length in _TRUNCATION_LENGTHS:
            if length < len(words):
                _append(queries, " ".join(words[:length]))
    return queries[:limit]


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", _PARENTHETICAL.sub(" ", name)).strip(" ,-")


def _append(queries: list[str], candidate: str) -> None:
    candidate = candidate.strip(" ,-")
    if not candidate or candidate.lower() in _GENERIC_TERMS:
        return
    # A lone short or numeric word ("1", "of") matches half the catalog and says nothing about
    # which figure this is, so it is not worth a search even as a last resort.
    if " " not in candidate and (len(candidate) < 3 or candidate.isdigit()):
        return
    if candidate not in queries:
        queries.append(candidate)


class IdentifyMinifigUseCase:
    """Turn a photo of a minifig into candidate catalog entries to confirm.

    Two services are involved because neither does the whole job. The recogniser knows what the
    photo looks like but answers in its own catalog's identifiers, which nothing maps onto
    Rebrickable's — there is no public conversion for minifigs. Rebrickable knows the fig_num the
    rest of the app is built on but cannot search by picture. The only bridge between them is the
    name, and the two catalogs word names differently, so this resolves by search and ranking and
    then hands the result to the owner to confirm. Nothing here writes to the collection.
    """

    def __init__(
        self,
        recognizer: MinifigRecognizer,
        catalog: PartsCatalogClient,
        instance_repo: MinifigInstanceRepository,
        set_names: dict[str, str] | None = None,
    ):
        self.recognizer = recognizer
        self.catalog = catalog
        self.instance_repo = instance_repo
        self.set_names = set_names or {}

    async def execute(
        self, image_bytes: bytes, filename: str, content_type: str | None = None
    ) -> IdentifyMinifigResult:
        recognitions = await self.recognizer.identify(image_bytes, filename, content_type)
        if not recognitions:
            return IdentifyMinifigResult(recognitions=[], matches=[])

        considered = recognitions[:MAX_RECOGNITIONS_CONSIDERED]
        searched = await asyncio.gather(*(self._resolve(r) for r in considered))

        best: dict[str, MinifigMatch] = {}
        for recognition, results in zip(considered, searched, strict=True):
            for result in results:
                match = self._to_match(recognition, result)
                current = best.get(match.fig_num)
                if current is None or match.score > current.score:
                    best[match.fig_num] = match

        matches = sorted(best.values(), key=lambda m: (-m.score, m.fig_num))
        return IdentifyMinifigResult(recognitions=recognitions, matches=matches[:MAX_MATCHES])

    async def _resolve(self, recognition: MinifigRecognitionDTO) -> list[MinifigSearchResultDTO]:
        """Widen the query until the catalog answers. The first non-empty result wins: queries run
        narrowest first, so anything broader would only add worse matches."""
        for query in build_queries(recognition.name):
            results = await self.catalog.search_minifigs(query, SEARCH_PAGE_SIZE)
            if results:
                return results
        logger.info("no catalog match for recognised minifig %r", recognition.name)
        return []

    def _to_match(self, recognition: MinifigRecognitionDTO, result: MinifigSearchResultDTO) -> MinifigMatch:
        score = (
            _RECOGNITION_WEIGHT * recognition.score
            + _NAME_SIMILARITY_WEIGHT * similarity(recognition.name, result.name)
        )
        owned = [
            OwnedInstanceRef(
                instance_id=instance.id,
                source_set_num=instance.source_set_num,
                source_set_name=(
                    self.set_names.get(instance.source_set_num) if instance.source_set_num else None
                ),
                is_complete=instance.is_complete,
                quantity_found_total=instance.total_found,
                quantity_required_total=instance.total_required,
            )
            # Copies still waiting to be found come first: those are the ones the photographed
            # figure can be, and with duplicates in a set that ordering is the whole answer.
            for instance in sorted(
                self.instance_repo.list_by_fig_num(result.fig_num),
                key=lambda i: (i.is_complete, i.source_set_num or ""),
            )
        ]
        return MinifigMatch(
            fig_num=result.fig_num,
            name=result.name,
            num_parts=result.num_parts,
            image_url=result.image_url,
            score=score,
            recognized_as=recognition.name,
            recognition_image_url=recognition.image_url,
            reference_url=recognition.reference_url,
            owned_instances=owned,
        )
