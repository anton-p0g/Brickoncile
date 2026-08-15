import { Link } from "react-router-dom";
import { BurnUpChart } from "../components/charts/BurnUpChart";
import { ChartCard, ChartEmpty } from "../components/charts/ChartCard";
import { ColorSpectrum } from "../components/charts/ColorSpectrum";
import { CommonPartsChart } from "../components/charts/CommonPartsChart";
import { CompletionGrid } from "../components/charts/CompletionGrid";
import { CompletionRampLegend } from "../components/charts/CompletionRampLegend";
import { SimpleBarChart } from "../components/charts/SimpleBarChart";
import { SizeCompletionScatter } from "../components/charts/SizeCompletionScatter";
import { StatTile } from "../components/charts/StatTile";
import { StatusFunnel } from "../components/charts/StatusFunnel";
import { ThemeTreemap } from "../components/charts/ThemeTreemap";
import { TopMissingList } from "../components/charts/TopMissingList";
import { formatCount, formatDuration } from "../lib/chart";
import { completionPercent } from "../lib/completion";
import { useCollectionStats } from "../hooks/useStats";

export function DashboardPage() {
  const { data: stats, isLoading, error } = useCollectionStats();

  if (isLoading) return <p className="p-4 text-sm text-gray-500">Loading your collection...</p>;

  if (error) {
    return (
      <p className="p-4 text-sm text-red-700">
        Could not load your statistics: {error instanceof Error ? error.message : "unknown error"}
      </p>
    );
  }

  if (!stats) return null;

  const { totals, sessions, minifigs } = stats;
  const percentFound = completionPercent({
    quantity_required_total: totals.quantity_required,
    quantity_found_total: totals.quantity_found,
  });
  const left = totals.quantity_required - totals.quantity_found;

  if (totals.sets === 0) {
    return (
      <div className="p-4">
        <p className="text-sm text-gray-500">
          Nothing to chart yet.{" "}
          <Link to="/sets" className="underline hover:text-gray-900">
            Add your first set
          </Link>{" "}
          and this page fills in as you sort.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="sets" value={totals.sets} detail={`${minifigs.total} minifigures`} />
        <StatTile
          label="found overall"
          value={`${percentFound}%`}
          detail={`${formatCount(totals.quantity_found)} of ${formatCount(totals.quantity_required)}`}
        />
        <StatTile label="pieces left to check" value={formatCount(left)} />
        <StatTile
          label="confirmed missing"
          value={formatCount(totals.quantity_missing)}
          detail="across finished sets"
        />
        <StatTile label="distinct parts" value={formatCount(totals.distinct_parts)} />
        <StatTile label="colours" value={totals.distinct_colors} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {/* The two plotted charts sit side by side: at full width their fixed aspect ratio made
            them tower over the cards around them. */}
        <ChartCard title="Progress over time" subtitle="Against the collection total">
          <BurnUpChart burnUp={stats.burn_up} target={totals.quantity_required} />
        </ChartCard>

        <ChartCard title="Set size against completion" subtitle="Are the big sets keeping up?">
          <SizeCompletionScatter sets={stats.sets} />
        </ChartCard>

        <ChartCard title="Where your sets stand">
          <StatusFunnel breakdown={stats.status_breakdown} of="sets" unit="sets" />
        </ChartCard>

        <ChartCard title="Where your minifigures stand">
          <StatusFunnel breakdown={stats.status_breakdown} of="minifig_instances" unit="minifigures" />
        </ChartCard>

        <ChartCard
          title="Every set at a glance"
          subtitle="Least complete first"
          aside={<CompletionRampLegend />}
          wide
        >
          <CompletionGrid sets={stats.sets} />
        </ChartCard>

        <ChartCard
          title="Collection by theme"
          subtitle="Size is pieces, shading is completion"
          aside={<CompletionRampLegend />}
          wide
        >
          <ThemeTreemap themes={stats.themes} />
        </ChartCard>

        <ChartCard title="Your palette" subtitle="Pieces by colour">
          <ColorSpectrum colors={stats.colors} />
        </ChartCard>

        <ChartCard title="Parts worth their own bin" subtitle="Wanted by the most sets">
          <CommonPartsChart parts={stats.common_parts} totalSets={totals.sets} />
        </ChartCard>

        <ChartCard title="Most wanted">
          <TopMissingList parts={stats.top_missing} />
        </ChartCard>

        <ChartCard title="When you sort" subtitle="By hour of day">
          {stats.sessions.count === 0 ? (
            <ChartEmpty>No finds logged yet.</ChartEmpty>
          ) : (
            <>
              <SimpleBarChart
                bars={stats.activity_by_hour.map((bucket) => ({
                  label: String(bucket.hour).padStart(2, "0"),
                  value: bucket.events,
                  title: `${bucket.hour}:00 · ${bucket.events} finds, ${formatCount(bucket.pieces)} pieces`,
                }))}
                labelEvery={3}
              />
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
                <Figure label="sessions" value={sessions.count} />
                <Figure label="per session" value={`${formatCount(sessions.pieces_per_session)} pcs`} />
                <Figure label="longest" value={formatDuration(sessions.longest_minutes)} />
                <Figure label="pace" value={`${formatCount(sessions.pieces_per_hour)} pcs/h`} />
              </dl>
            </>
          )}
        </ChartCard>

        <ChartCard title="Collection by release year">
          <SimpleBarChart
            bars={stats.years.map((bucket) => ({
              label: bucket.year === null ? "?" : String(bucket.year),
              value: bucket.sets,
              title: `${bucket.year ?? "Unknown year"} · ${bucket.sets} set${bucket.sets === 1 ? "" : "s"}, ${formatCount(bucket.quantity_required)} pieces`,
            }))}
            height={150}
          />
        </ChartCard>

        <ChartCard title="Minifigures" subtitle="Owned, and duplicates">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
            <Figure label="owned" value={minifigs.total} />
            <Figure label="distinct" value={minifigs.distinct_figs} />
            <Figure label="complete" value={minifigs.complete} />
            <Figure label="loose" value={minifigs.loose} />
          </dl>
          {minifigs.most_duplicated.length > 0 && (
            <ul className="mt-3 flex flex-col gap-1.5">
              {minifigs.most_duplicated.map((fig) => (
                <li key={fig.fig_num} className="flex items-center gap-2 text-xs">
                  {fig.image_url ? (
                    <img
                      src={fig.image_url}
                      alt=""
                      loading="lazy"
                      className="size-7 shrink-0 rounded border border-gray-200 object-contain"
                    />
                  ) : (
                    <span className="size-7 shrink-0 rounded border border-gray-200" />
                  )}
                  <span className="min-w-0 flex-1 truncate text-gray-900" title={fig.fig_name}>
                    {fig.fig_name}
                  </span>
                  <span className="shrink-0 font-mono text-gray-500">×{fig.count}</span>
                </li>
              ))}
            </ul>
          )}
        </ChartCard>
      </div>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-mono text-sm text-gray-900">{value}</dd>
    </div>
  );
}
