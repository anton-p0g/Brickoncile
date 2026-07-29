/**
 * Rebrickable colour id to hex, for the swatch on a part card.
 *
 * The API sends only `color_id` and `color_name`, and names alone are hard to scan: "Light Bluish
 * Gray" and "Dark Bluish Gray" differ by one word and describe most of a grey Star Wars set. A
 * swatch makes the pile sortable at a glance.
 *
 * Rebrickable's ids follow LDraw's, so these hexes are the LDraw values. The table is deliberately
 * partial — the couple of hundred colours in the catalog are mostly pearl, chrome and glitter
 * variants that never appear in a normal inventory. Anything unlisted falls back to no swatch,
 * which is why every caller must handle null rather than assume a colour.
 */
const COLOR_HEX: Record<number, string> = {
  [-1]: "#808080", // Unknown, as sent for a part whose colour Rebrickable does not record
  0: "#05131D", // Black
  1: "#0055BF", // Blue
  2: "#237841", // Green
  3: "#008F9B", // Dark Turquoise
  4: "#C91A09", // Red
  5: "#C870A0", // Dark Pink
  6: "#583927", // Brown
  7: "#9BA19D", // Light Gray
  8: "#6D6E5C", // Dark Gray
  9: "#B4D2E3", // Light Blue
  10: "#4B9F4A", // Bright Green
  11: "#55A5AF", // Light Turquoise
  12: "#F2705E", // Salmon
  13: "#FC97AC", // Pink
  14: "#F2CD37", // Yellow
  15: "#FFFFFF", // White
  17: "#C2DAB8", // Light Green
  18: "#FBE696", // Light Yellow
  19: "#E4CD9E", // Tan
  20: "#C9CAE2", // Light Violet
  21: "#D4D5C9", // Glow In Dark Opaque
  22: "#81007B", // Purple
  23: "#2032B0", // Dark Blue-Violet
  25: "#FE8A18", // Orange
  26: "#923978", // Magenta
  27: "#BBE90B", // Lime
  28: "#958A73", // Dark Tan
  29: "#E4ADC8", // Bright Pink
  30: "#AC78BA", // Medium Lavender
  31: "#E1D5ED", // Lavender
  33: "#0020A0", // Trans-Dark Blue
  34: "#84B68D", // Trans-Green
  36: "#C91A09", // Trans-Red
  40: "#635F52", // Trans-Black
  41: "#AEEFEC", // Trans-Light Blue
  42: "#F8F184", // Trans-Neon Green
  43: "#C1DFF0", // Trans-Very Light Blue
  47: "#FCFCFC", // Trans-Clear
  52: "#A5A5CB", // Trans-Purple
  54: "#DAB000", // Trans-Neon Yellow
  57: "#FF800D", // Trans-Neon Orange
  68: "#F3CF9B", // Very Light Orange
  69: "#CD6298", // Light Purple
  70: "#582A12", // Reddish Brown
  71: "#A0A5A9", // Light Bluish Gray
  72: "#6C6E68", // Dark Bluish Gray
  73: "#5A93DB", // Medium Blue
  74: "#73DCA1", // Medium Green
  77: "#FECCCF", // Light Pink
  78: "#F6D7B3", // Light Nougat
  84: "#AA7D55", // Medium Nougat
  85: "#3F3691", // Dark Purple
  86: "#7C503A", // Dark Flesh
  89: "#4C61DB", // Blue-Violet
  92: "#D09168", // Nougat
  100: "#FEBABD", // Light Salmon
  110: "#4354A3", // Violet
  112: "#6874CA", // Medium Violet
  115: "#C7D23C", // Medium Lime
  118: "#B3D7D1", // Aqua
  120: "#D9E4A7", // Light Lime
  125: "#F9BA61", // Light Orange
  143: "#CFE2F7", // Trans-Medium Blue
  151: "#E6E3E0", // Very Light Bluish Gray
  179: "#898788", // Flat Silver
  182: "#F08F1C", // Trans-Orange
  191: "#F8BB3D", // Bright Light Orange
  212: "#9FC3E9", // Bright Light Blue
  216: "#B31004", // Rust
  226: "#FFF03A", // Bright Light Yellow
  232: "#7DBFDD", // Sky Blue
  272: "#0A3463", // Dark Blue
  297: "#AA7F2E", // Pearl Gold
  288: "#184632", // Dark Green
  308: "#352100", // Dark Brown
  313: "#3592C3", // Maersk Blue
  320: "#720E0F", // Dark Red
  321: "#078BC9", // Dark Azure
  322: "#36AEBF", // Medium Azure
  323: "#ADC3C0", // Light Aqua
  326: "#DFEEA5", // Yellowish Green
  330: "#9B9A5A", // Olive Green
  335: "#D67572", // Sand Red
  351: "#F785B1", // Medium Dark Pink
  366: "#FA9C1C", // Earth Orange
  373: "#845E84", // Sand Purple
  378: "#A0BCAC", // Sand Green
  379: "#6074A1", // Sand Blue
  450: "#B67B50", // Fabuland Brown
  462: "#FFA70B", // Medium Orange
  484: "#A95500", // Dark Orange
  503: "#E6E3DA", // Very Light Gray
  1103: "#3E3C39", // Pearl Titanium
};
// Note: id 9999 is Rebrickable's "[No Color/Any Color]" placeholder rather than a colour, so it is
// deliberately absent — a swatch would invent an appearance the part does not have.

/** Null for a colour outside the table, which the caller renders as a name with no swatch. */
export function colorHex(colorId: number): string | null {
  return COLOR_HEX[colorId] ?? null;
}

/** Very light colours vanish against a white card, so the swatch needs its own outline. */
export function needsSwatchOutline(hex: string): boolean {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  // Rec. 601 luma, which tracks perceived brightness closely enough to pick a border.
  return (r * 299 + g * 587 + b * 114) / 1000 > 200;
}
