export const ALGORITHM_NAMES = { dsatur: "DSatur", welsh_powell: "Welsh-Powell" } as const;

/** 3 -> "3", 2.5 -> "2.5", 1.25 -> "1.25" (sin ceros de sobra). */
export function num(x: number): string {
  return Number.isInteger(x) ? String(x) : x.toFixed(2).replace(/\.?0+$/, "");
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** «A», «B» y «C» (hasta `max` nombres; el resto se resume). */
export function listNames(names: string[], max = 4): string {
  const shown = names.slice(0, max).map((n) => `«${n}»`);
  const rest = names.length - shown.length;
  if (rest > 0) return `${shown.join(", ")} y ${rest} más`;
  if (shown.length <= 1) return shown.join("");
  return `${shown.slice(0, -1).join(", ")} y ${shown[shown.length - 1]}`;
}

const ERROR_LINE = /línea (\d+)/;

/** Número de línea mencionado en un error del motor ("línea 3: …"), o null. */
export function errorLine(message: string): number | null {
  const m = ERROR_LINE.exec(message);
  return m ? Number(m[1]) : null;
}
