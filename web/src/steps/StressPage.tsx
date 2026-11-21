// Prueba de estrés: grafos aleatorios de 10, 100 y 1000 tareas, coloreados en el navegador.
import { Play, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { Button, Card, Segmented } from "../components/ui";
import { engine } from "../engine/engine";
import { num } from "../lib/format";

const SIZES = [10, 100, 1000] as const;
const SEED = 1;
type Degree = "3" | "6" | "12";

interface Row {
  n: number;
  conflicts: number;
  dsaturMs: number;
  dsaturColors: number;
  wpMs: number;
  wpColors: number;
  lower: number;
  exact: number | null;
}

/** Probabilidad de conflicto para que cada tarea choque en promedio con `degree` otras. */
const probability = (n: number, degree: number) => Math.min(1, degree / Math.max(n - 1, 1));

function Bar({ value, max, tone }: { value: number; max: number; tone: string }) {
  return <div className={`h-2 rounded-full ${tone}`} style={{ width: `${Math.max((value / max) * 100, 1.5)}%` }} />;
}

export function StressPage() {
  const [degree, setDegree] = useState<Degree>("6");
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setRows([]);
    setError(null);
    try {
      for (const n of SIZES) {
        const result = await engine.analyze({ mode: "random", n, p: probability(n, Number(degree)), seed: SEED, algorithm: "dsatur" });
        if (!result.ok) throw new Error(result.error);
        const v = result.view;
        const row: Row = {
          n, conflicts: v.metrics.conflicts, dsaturMs: v.timings_ms.coloring, dsaturColors: v.metrics.colors,
          wpMs: v.timings_ms.alternative, wpColors: v.alternative.colors, lower: v.metrics.lower, exact: v.metrics.exact,
        };
        setRows((r) => [...r, row]);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  }

  const maxMs = Math.max(0.001, ...rows.flatMap((r) => [r.dsaturMs, r.wpMs]));
  return (
    <section>
      <div className="mb-6 max-w-3xl">
        <h1 className="text-[28px] font-semibold leading-tight tracking-tight">Prueba de estrés</h1>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          Genera grafos de conflictos aleatorios de 10, 100 y 1000 tareas y los colorea con los dos algoritmos, aquí mismo
          en su navegador. Cada tarea choca, en promedio, con la cantidad de tareas que elija.
        </p>
      </div>

      <Card className="mb-6 flex flex-wrap items-center gap-4 p-4">
        <span className="text-sm font-medium">Conflictos por tarea</span>
        <Segmented<Degree> label="Conflictos promedio por tarea" value={degree} onChange={setDegree}
          options={[{ value: "3", label: "Pocos (3)" }, { value: "6", label: "Normal (6)" }, { value: "12", label: "Muchos (12)" }]} />
        <Button variant="primary" className="ml-auto" onClick={run} disabled={running}>
          {running ? <LoaderCircle className="size-4 animate-spin" /> : <Play className="size-4" />}
          {running ? "Ejecutando…" : "Ejecutar prueba"}
        </Button>
      </Card>

      {error && <p className="mb-4 rounded-lg bg-danger-soft p-3 text-sm text-danger" role="alert">{error}</p>}

      {rows.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm" data-testid="stress-table">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">Tareas</th>
                <th className="px-4 py-3 text-right font-medium">Conflictos</th>
                <th className="px-4 py-3 font-medium">Tiempo de coloración</th>
                <th className="px-4 py-3 text-right font-medium">DSatur</th>
                <th className="px-4 py-3 text-right font-medium">Welsh-Powell</th>
                <th className="px-4 py-3 text-right font-medium" title="Lotes mínimos posibles">χ(G)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.n} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 font-semibold tabular-nums">{r.n}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.conflicts}</td>
                  <td className="w-[38%] px-4 py-3">
                    <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 text-xs tabular-nums text-muted">
                      <Bar value={r.dsaturMs} max={maxMs} tone="bg-ink" /><span>DSatur {num(Number(r.dsaturMs.toFixed(2)))} ms</span>
                      <Bar value={r.wpMs} max={maxMs} tone="bg-faint" /><span>W-P {num(Number(r.wpMs.toFixed(2)))} ms</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.dsaturColors} lotes</td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.wpColors} lotes</td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.exact ?? `${r.lower} a ${Math.min(r.dsaturColors, r.wpColors)}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-line px-4 py-3 text-xs text-muted">
            Tiempos medidos dentro del navegador (Python compilado a WebAssembly). Cuando χ(G) aparece como rango, el
            valor exacto es demasiado costoso de calcular: es un problema NP-difícil.
          </p>
        </Card>
      )}
    </section>
  );
}
