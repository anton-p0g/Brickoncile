import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.dependencies import get_missing_summary_use_case
from app.api.schemas import PartAggregateOut, SourceAggregateOut
from app.application.use_cases.get_missing_summary import (
    GetMissingSummaryUseCase,
    PartAggregate,
    SourceAggregate,
)

router = APIRouter(prefix="/api/missing-parts", tags=["missing-parts"])

UseCaseDep = Annotated[GetMissingSummaryUseCase, Depends(get_missing_summary_use_case)]


@router.get("")
def get_missing_summary(
    use_case: UseCaseDep, group_by: Literal["part", "set"] = "part"
) -> list[PartAggregateOut] | list[SourceAggregateOut]:
    result = use_case.execute(group_by=group_by)
    if group_by == "part":
        return [PartAggregateOut.from_use_case(a) for a in result]
    return [SourceAggregateOut.from_use_case(a) for a in result]


@router.get("/export.csv")
def export_missing_parts_csv(use_case: UseCaseDep, group_by: Literal["part", "set"] = "part") -> Response:
    result = use_case.execute(group_by=group_by)
    csv_text = _build_csv(result, group_by)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=missing-parts.csv"},
    )


def _build_csv(result: list[PartAggregate] | list[SourceAggregate], group_by: Literal["part", "set"]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    if group_by == "part":
        writer.writerow(["part_num", "color_id", "part_name", "color_name", "total_missing", "contributors"])
        for aggregate in result:
            contributors = "; ".join(f"{c.label} x{c.quantity}" for c in aggregate.contributors)
            writer.writerow(
                [aggregate.part_num, aggregate.color_id, aggregate.part_name, aggregate.color_name, aggregate.total_missing, contributors]
            )
    else:
        writer.writerow(["source_type", "source_id", "label", "part_num", "color_id", "part_name", "color_name", "quantity_missing"])
        for aggregate in result:
            for item in aggregate.items:
                writer.writerow(
                    [
                        aggregate.source_type,
                        aggregate.source_id,
                        aggregate.label,
                        item.part_num,
                        item.color_id,
                        item.part_name,
                        item.color_name,
                        item.quantity_missing,
                    ]
                )

    return output.getvalue()
