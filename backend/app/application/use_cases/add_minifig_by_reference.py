from pydantic import BaseModel

from app.application.minifig_reference import parse_minifig_reference
from app.application.use_cases.add_loose_minifig import AddLooseMinifigUseCase
from app.domain.entities import MinifigInstance
from app.domain.errors import UnresolvableMinifigReferenceError
from app.domain.repositories import MinifigInstanceRepository

BRICKLINK_HELP = (
    "BrickLink numbers minifigures separately from Rebrickable and publishes no mapping between "
    "them. Open the figure on rebrickable.com and paste that link instead, or identify it from a "
    "photo."
)

UNRECOGNISED_HELP = (
    "Paste a Rebrickable minifigure link or a fig ID like fig-000068. To find a figure by name, "
    "identify it from a photo instead."
)


class AddMinifigByReferenceResult(BaseModel):
    instance: MinifigInstance
    already_owned_count: int
    """Copies of this fig already in the collection before this one. Owning two is ordinary, so it
    does not block the add — but it is the tell for a list pasted twice, which is worth reporting."""


class AddMinifigByReferenceUseCase:
    """Add a minifig from whatever the owner pasted: a Rebrickable link, a fig ID, a BrickLink link.

    The manual route in, for when a photo cannot be identified. Reading the reference is kept apart
    from adding it — `parse_minifig_reference` decides what was pasted, this decides what that means
    — so a BrickLink id fails saying it cannot be converted, rather than being sent to Rebrickable
    as a fig id it would never recognise and coming back as a bare "not found".
    """

    def __init__(self, instance_repo: MinifigInstanceRepository, add_loose: AddLooseMinifigUseCase):
        self.instance_repo = instance_repo
        self.add_loose = add_loose

    async def execute(self, raw_reference: str) -> AddMinifigByReferenceResult:
        reference = parse_minifig_reference(raw_reference)
        if reference.kind == "bricklink":
            raise UnresolvableMinifigReferenceError(f"{reference.value} is a BrickLink ID. {BRICKLINK_HELP}")
        if reference.kind == "unrecognised":
            raise UnresolvableMinifigReferenceError(f"Could not read a minifigure ID from that. {UNRECOGNISED_HELP}")

        # Counted before the add, so the new instance is not counted as a copy of itself.
        already_owned = len(self.instance_repo.list_by_fig_num(reference.value))
        instance = await self.add_loose.execute(reference.value)
        return AddMinifigByReferenceResult(instance=instance, already_owned_count=already_owned)
