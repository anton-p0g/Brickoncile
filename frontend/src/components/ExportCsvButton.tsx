import { exportMissingPartsCsvUrl } from "../api/client";
import type { GroupBy } from "../api/types";

export function ExportCsvButton({ groupBy }: { groupBy: GroupBy }) {
  return (
    <a
      href={exportMissingPartsCsvUrl(groupBy)}
      className="rounded border border-gray-300 bg-white px-3 py-1 text-xs hover:border-gray-500"
    >
      Export CSV
    </a>
  );
}
