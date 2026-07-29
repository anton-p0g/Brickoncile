import { colorHex, needsSwatchOutline } from "../lib/colors";

interface ColorSwatchProps {
  colorId: number;
  colorName: string;
  className?: string;
}

/** The colour as a dot. Renders nothing for a colour outside the table, so the name carries it. */
export function ColorSwatch({ colorId, colorName, className = "" }: ColorSwatchProps) {
  const hex = colorHex(colorId);
  if (!hex) return null;

  return (
    <span
      aria-hidden="true"
      title={colorName}
      style={{ backgroundColor: hex }}
      className={`inline-block h-3 w-3 flex-shrink-0 rounded-full ${
        needsSwatchOutline(hex) ? "border border-gray-400" : "border border-black/20"
      } ${className}`}
    />
  );
}
