// Color de cada lote. El color ES el dato (lote = color del vértice), así que la paleta es lo único vivo de la UI.

export const PALETTE = [
  "#3B82F6", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6", "#EAB308",
  "#06B6D4", "#EC4899", "#84CC16", "#F97316", "#6366F1", "#14B8A6",
] as const;

const GOLDEN_ANGLE = 137.508;
const DARK_TEXT = "#0F172A";
const LIGHT_TEXT = "#FFFFFF";
const LUMINANCE_THRESHOLD = 0.42;

/** Color del lote (1-indexado). Después de la paleta, tonos repartidos por el ángulo áureo. */
export function batchColor(batch: number): string {
  if (batch >= 1 && batch <= PALETTE.length) return PALETTE[batch - 1];
  return `hsl(${Math.round((batch * GOLDEN_ANGLE) % 360)} 62% 48%)`;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Texto legible encima del color del lote. */
export function textOnBatch(batch: number): string {
  const color = batchColor(batch);
  if (!color.startsWith("#")) return LIGHT_TEXT;
  return luminance(color) > LUMINANCE_THRESHOLD ? DARK_TEXT : LIGHT_TEXT;
}
