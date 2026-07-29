import { useState } from "react";

export function CopyListButton({ getText }: { getText: () => string }) {
  const [copied, setCopied] = useState(false);

  async function handleClick() {
    await navigator.clipboard.writeText(getText());
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="rounded border border-gray-300 bg-white px-3 py-1 text-xs hover:border-gray-500"
    >
      {copied ? "Copied!" : "Copy list"}
    </button>
  );
}
