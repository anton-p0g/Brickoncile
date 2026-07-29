from app.application.use_cases.fetch_minifig import FetchMinifigUseCase
from app.domain.repositories import (
    MinifigInstanceRepository,
    PartsCatalogClient,
)


class SyncMinifigRosterUseCase:
    """Gives a set one tracked instance per minifig it contains.

    Idempotent and resumable: existing instances are counted and only the shortfall is created,
    so a roster that half-landed (a throttled catalog, a dropped connection) is completed by
    running this again rather than needing the set removed and re-added.
    """

    def __init__(
        self,
        instance_repo: MinifigInstanceRepository,
        catalog: PartsCatalogClient,
        fetch_minifig: FetchMinifigUseCase,
    ):
        self.instance_repo = instance_repo
        self.catalog = catalog
        self.fetch_minifig = fetch_minifig

    async def execute(self, set_num: str) -> None:
        roster = await self.catalog.fetch_set_minifigs(set_num)
        for entry in roster:
            minifig = await self.fetch_minifig.execute(entry.fig_num)
            owned = self.instance_repo.count_by_fig_and_set(entry.fig_num, set_num)
            for _ in range(entry.quantity - owned):
                self.instance_repo.create(
                    fig_num=minifig.fig_num,
                    fig_name=minifig.name,
                    image_path=minifig.image_path,
                    source_set_num=set_num,
                    parts_template=minifig.parts,
                )
