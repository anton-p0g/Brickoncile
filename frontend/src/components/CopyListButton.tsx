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
      className="ui-control ui-control-secondary px-3 py-1 text-xs"
    >
      {copied ? "Copied!" : "Copy list"}
    </button>
  );
}
