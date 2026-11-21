// Matriz de adyacencia del grafo de conflictos (solo para grafos chicos).
import type { PlanView } from "../engine/types";
import { BatchDot } from "./ui";

export function Matrix({ view, colored }: { view: PlanView; colored: boolean }) {
  const m = view.matrix;
  if (!m) {
    return <p className="p-8 text-center text-sm text-muted">La matriz se muestra para hasta 40 tareas.</p>;
  }
  const batchOf = new Map(view.tasks.map((t) => [t.id, t.batch]));
  return (
    <div className="h-full overflow-auto p-4">
      <p className="mb-3 max-w-2xl text-sm text-muted">
        A[i][j] = 1 cuando las tareas i y j están en conflicto. Ocupa O(V²) memoria; los algoritmos recorren la lista de
        adyacencia, que ocupa O(V + E).
      </p>
      <table className="border-separate border-spacing-0 text-xs tabular-nums">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-20 bg-surface" />
            {m.labels.map((l, j) => <th key={l} title={l} className="sticky top-0 z-10 w-7 bg-surface pb-1 font-medium text-muted">{j + 1}</th>)}
            <th className="sticky top-0 z-10 bg-surface px-2 pb-1 font-medium text-muted">grado</th>
          </tr>
        </thead>
        <tbody>
          {m.rows.map((row, i) => (
            <tr key={m.labels[i]}>
              <th className="sticky left-0 z-10 bg-surface py-0.5 pr-3 text-left font-medium whitespace-nowrap text-ink-soft">
                <span className="inline-flex items-center gap-2">
                  {colored ? <BatchDot batch={batchOf.get(m.labels[i]) ?? 1} size={8} /> : null}
                  <span className="w-5 text-right text-faint">{i + 1}</span>{m.labels[i]}
                </span>
              </th>
              {row.map((x, j) => (
                <td key={j} className={x ? "size-7 rounded-sm bg-ink text-center font-semibold text-white" : "size-7 text-center text-line-strong"}>{x}</td>
              ))}
              <td className="px-2 text-center text-muted">{m.degrees[i]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
