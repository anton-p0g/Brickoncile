import { COMPLETION_STEPS } from "../../lib/chart";

/** Key for the shading shared by the completion grid and the theme treemap. */
export function CompletionRampLegend() {
  return (
    <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
      <span>0%</span>
      <span className="flex" aria-hidden>
        {COMPLETION_STEPS.map((step) => (
          <span key={step} className="size-2.5" style={{ backgroundColor: step }} />
        ))}
      </span>
      <span>100% found</span>
    </div>
  );
}
