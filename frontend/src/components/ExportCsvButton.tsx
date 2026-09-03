import { exportMissingPartsCsvUrl } from "../api/client";
import type { GroupBy } from "../api/types";

export function ExportCsvButton({ groupBy }: { groupBy: GroupBy }) {
  return (
    <a
      href={exportMissingPartsCsvUrl(groupBy)}
      className="ui-control ui-control-secondary px-3 py-1 text-xs"
    >
      Export CSV
    </a>
  );
}
