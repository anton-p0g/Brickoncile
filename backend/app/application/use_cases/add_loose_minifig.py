from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.domain.entities import MinifigInstance
from app.domain.repositories import MinifigInstanceRepository


class AddLooseMinifigUseCase:
    """Take a confirmed fig_num into the collection as a minifig owned without a set.

    Deliberately the same MinifigInstance every set roster produces, with no source set rather than
    a special kind of record: a loose figure is sorted, resynced and searched exactly like one that
    arrived in a box, and the only thing not known about it is where it came from.
    """

    def __init__(self, instance_repo: MinifigInstanceRepository, fetch_minifig: FetchMinifigUseCase):
        self.instance_repo = instance_repo
        self.fetch_minifig = fetch_minifig

    async def execute(self, fig_num: str) -> MinifigInstance:
        minifig = await self.fetch_minifig.execute(fig_num)
        return self.instance_repo.create(
            fig_num=minifig.fig_num,
            fig_name=minifig.name,
            image_path=minifig.image_path,
            source_set_num=None,
            parts_template=minifig.parts,
        )
