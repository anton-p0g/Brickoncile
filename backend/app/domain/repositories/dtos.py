from pydantic import BaseModel


class PartDTO(BaseModel):
    part_num: str
    color_id: int
    color_name: str
    part_name: str
    element_id: str | None = None
    quantity: int
    is_spare: bool = False
    image_url: str | None = None


class SetMetadataDTO(BaseModel):
    set_num: str
    name: str
    year: int | None = None
    theme_id: int | None = None
    num_parts: int
    image_url: str | None = None


class MinifigRosterEntryDTO(BaseModel):
    fig_num: str
    quantity: int
    image_url: str | None = None


class PartFoundUpdate(BaseModel):
    """One part's target found count, for updating many parts in a single transaction."""

    part_num: str
    color_id: int
    quantity_found: int


class ThemeDTO(BaseModel):
    id: int
    parent_id: int | None = None
    name: str


class MinifigMetadataDTO(BaseModel):
    fig_num: str
    name: str
    num_parts: int | None = None
    image_url: str | None = None


class MinifigSearchResultDTO(BaseModel):
    """One hit from a catalog name search — the same shape as metadata, kept separate because a
    search result is a guess to be confirmed rather than a resolved identity."""

    fig_num: str
    name: str
    num_parts: int | None = None
    image_url: str | None = None


class MinifigRecognitionDTO(BaseModel):
    """One guess from the image recogniser.

    `external_id` and `name` come from the recogniser's own catalog (BrickLink's, in the case of
    Brickognize) and do not match Rebrickable's `fig_num`/name, so neither can be used as an
    identifier here. They are carried for display and to seed the catalog search that does the
    actual resolution.
    """

    external_id: str
    name: str
    score: float
    """Recogniser confidence in [0, 1]."""
    image_url: str | None = None
    category: str | None = None
    reference_url: str | None = None
    """Link to the recogniser's own catalog entry (BrickLink). The one place the two catalogs can be
    compared side by side, since nothing maps their identifiers automatically — so it is what an
    owner clicks to settle an uncertain match by hand."""
