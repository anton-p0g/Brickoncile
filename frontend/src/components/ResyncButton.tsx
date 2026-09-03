function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={`h-4 w-4 ${spinning ? "animate-spin" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9" />
      <path d="M13.5 2.5v3h-3" />
    </svg>
  );
}

interface ResyncButtonProps {
  onClick: () => void;
  isPending: boolean;
}

export function ResyncButton({ onClick, isPending }: ResyncButtonProps) {
  return (
    <button
      type="button"
      title="Resync from Rebrickable"
      onClick={onClick}
      disabled={isPending}
      className="ui-control ui-control-secondary ui-control-md flex-shrink-0 gap-1.5"
    >
      <RefreshIcon spinning={isPending} />
      Resync
    </button>
  );
}
