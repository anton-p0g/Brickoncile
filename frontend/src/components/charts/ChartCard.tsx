import type { ReactNode } from "react";

interface ChartCardProps {
  title: string;
  /** One line saying what the figure answers, so the chart does not rely on being self-evident. */
  subtitle?: string;
  /** Legend, ramp key or a control, laid out opposite the title. */
  aside?: ReactNode;
  /** Spans two columns on wide screens, for the charts that need the width. */
  wide?: boolean;
  children: ReactNode;
}

export function ChartCard({ title, subtitle, aside, wide = false, children }: ChartCardProps) {
  return (
    // min-w-0 stops a wide row inside one card from sizing the whole grid column, which would
    // stretch every other card with it and push the page into a horizontal scroll.
    <section
      className={`min-w-0 rounded-lg border border-gray-200 bg-white p-3 ${wide ? "lg:col-span-2" : ""}`}
    >
      <header className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
        {aside && <div className="ml-auto">{aside}</div>}
      </header>
      {children}
    </section>
  );
}

/** Placeholder for a chart with nothing to draw yet, keeping the card's height stable. */
export function ChartEmpty({ children }: { children: ReactNode }) {
  return (
    <p className="flex h-32 items-center justify-center text-center text-xs text-gray-400">{children}</p>
  );
}
