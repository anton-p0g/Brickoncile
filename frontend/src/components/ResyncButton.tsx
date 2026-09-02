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
      className="flex flex-shrink-0 items-center gap-1.5 rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 transition hover:border-gray-400 disabled:opacity-50"
    >
      <RefreshIcon spinning={isPending} />
      Resync
    </button>
  );
}
