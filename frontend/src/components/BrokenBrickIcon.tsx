interface BrokenBrickIconProps {
  className?: string;
}

/** A brick split by a high-contrast crack, used consistently for damaged pieces. */
export function BrokenBrickIcon({ className = "h-4 w-4" }: BrokenBrickIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 8h7l2 3-2 2 2 2-2 4H3z" />
      <path d="M14 8h7v11h-7l-2-4 2-2-2-2z" />
      <path d="M6 8V5h4v3M14 8V5h4v3" />
    </svg>
  );
}
