import { useState } from "react";
import { CopyListButton } from "../components/CopyListButton";
import { ExportCsvButton } from "../components/ExportCsvButton";
import { GroupToggle } from "../components/GroupToggle";
import { useMissingSummary } from "../hooks/useMissingParts";
import type { GroupBy, PartAggregateOut, SourceAggregateOut } from "../api/types";

export function ShoppingListPage() {
  const [groupBy, setGroupBy] = useState<GroupBy>("part");
  const { data, isLoading } = useMissingSummary(groupBy);

  function buildCopyText(): string {
    if (!data) return "";
    if (groupBy === "part") {
      return (data as PartAggregateOut[])
        .map(
          (a) =>
            `${a.part_num} ${a.color_name} ${a.part_name} — needs ${a.total_missing} (${a.contributors
              .map((c) => `${c.label} x${c.quantity}`)
              .join(", ")})`,
        )
        .join("\n");
    }
    return (data as SourceAggregateOut[])
      .map(
        (s) =>
          `${s.label} — ${s.total_missing} missing\n` +
          s.items.map((i) => `  ${i.part_num} ${i.color_name} ${i.part_name} x${i.quantity_missing}`).join("\n"),
      )
      .join("\n\n");
  }

  return (
    <div className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <GroupToggle value={groupBy} onChange={setGroupBy} />
        <div className="ml-auto flex gap-2">
          <CopyListButton getText={buildCopyText} />
          <ExportCsvButton groupBy={groupBy} />
        </div>
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-gray-500">Loading...</p>
      ) : !data || data.length === 0 ? (
        <div className="mt-4 text-sm text-gray-500">
          <p>Nothing missing.</p>
          <p className="mt-1 text-xs text-gray-400">
            Only sets and minifigures you have marked &quot;Finish sorting&quot; appear here, since pieces you have
            not checked off yet may still be in the pile.
          </p>
        </div>
      ) : groupBy === "part" ? (
        <div className="mt-4 flex flex-col divide-y divide-dashed divide-gray-300">
          {(data as PartAggregateOut[]).map((a) => (
            <div key={`${a.part_num}-${a.color_id}`} className="flex flex-wrap items-center gap-3 py-2">
              <div className="h-9 w-9 flex-shrink-0 overflow-hidden rounded bg-gray-100">
                {a.image_url && <img src={a.image_url} alt={a.part_name} className="h-full w-full object-contain" />}
              </div>
              <span className="min-w-0 flex-1 font-semibold">
                {a.part_num} {a.color_name} {a.part_name}
              </span>
              <span className="text-sm text-gray-500">needs {a.total_missing} total</span>
              <div className="flex flex-wrap gap-1">
                {a.contributors.map((c) => (
                  <span
                    key={`${c.source_type}-${c.source_id}`}
                    className={`rounded-full border px-2 py-0.5 text-xs ${
                      c.source_type === "minifig_instance" ? "border-blue-300 text-blue-700" : "border-gray-300 text-gray-700"
                    }`}
                  >
                    {c.label} x{c.quantity}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          {(data as SourceAggregateOut[]).map((s) => (
            <div key={`${s.source_type}-${s.source_id}`} className="rounded border border-gray-200">
              <div
                className={`flex items-center gap-2 border-b border-gray-200 px-3 py-2 text-sm font-semibold ${
                  s.source_type === "minifig_instance" ? "bg-blue-50" : "bg-gray-50"
                }`}
              >
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white ${
                    s.source_type === "minifig_instance" ? "bg-blue-600" : "bg-gray-600"
                  }`}
                >
                  {s.source_type === "minifig_instance" ? "Minifig" : "Set"}
                </span>
                {s.label}
                <span className="ml-auto text-xs font-normal text-gray-500">{s.total_missing} missing</span>
              </div>
              <div className="divide-y divide-dashed divide-gray-200 px-3">
                {s.items.map((i) => (
                  <div key={`${i.part_num}-${i.color_id}`} className="flex items-center gap-3 py-1.5 text-sm">
                    <span className="flex-1">
                      {i.part_num} {i.color_name} {i.part_name}
                    </span>
                    <span className="text-gray-500">x{i.quantity_missing}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
