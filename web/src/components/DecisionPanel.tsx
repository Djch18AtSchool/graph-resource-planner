// Explica la decisión del algoritmo en el paso actual y muestra la tabla con la que decide.
import clsx from "clsx";
import { CheckCircle2 } from "lucide-react";
import { motion } from "motion/react";
import { useMemo } from "react";
import type { PlanView } from "../engine/types";
import { adjacency, dsaturCandidates, welshPowellOrder } from "../lib/decisions";
import { ALGORITHM_NAMES, plural } from "../lib/format";
import { BatchDot } from "./ui";

const WP_VISIBLE = 8;

function LastDecision({ view, step }: { view: PlanView; step: number }) {
  if (step === 0) {
    return (
      <p className="text-sm leading-relaxed text-ink-soft">
        {view.algorithm === "dsatur"
          ? "Ninguna tarea tiene lote todavía. DSatur empieza por la tarea con más conflictos y después elige siempre la más acorralada."
          : "Ninguna tarea tiene lote todavía. Welsh-Powell ordena las tareas de más a menos conflictos y llena un lote a la vez."}
      </p>
    );
  }
  const s = view.steps[step - 1];
  const degree = view.tasks.find((t) => t.id === s.task)?.degree ?? 0;
  const why = view.algorithm === "dsatur"
    ? `Era la más acorralada: sus vecinas ya ocupaban ${plural(s.saturation ?? 0, "lote distinto", "lotes distintos")} (y tiene ${plural(degree, "conflicto", "conflictos")}). Recibe el primer lote libre.`
    : `En la ronda del lote ${s.batch}, es la siguiente en el orden por grado (${plural(degree, "conflicto", "conflictos")}) que no choca con nadie de ese lote.`;
  return (
    <motion.div key={step} initial={{ opacity: 0.4, y: 3 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
        <p className="flex items-center gap-2 text-[15px] font-semibold text-ink">
          <span className="truncate">{s.task}</span>
          <span className="text-faint">→</span>
          <span className="flex shrink-0 items-center gap-1.5"><BatchDot batch={s.batch} size={11} />Lote {s.batch}</span>
        </p>
        <p className="mt-1 text-sm leading-relaxed text-ink-soft">{why}</p>
    </motion.div>
  );
}

function DsaturTable({ view, step }: { view: PlanView; step: number }) {
  const adj = useMemo(() => adjacency(view), [view]);
  const rows = dsaturCandidates(view, adj, step);
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-muted">
          <th className="pb-1.5 font-medium">Tarea sin lote</th>
          <th className="pb-1.5 text-right font-medium" title="Lotes distintos entre sus vecinas ya asignadas">Saturación</th>
          <th className="pb-1.5 text-right font-medium" title="Cantidad de conflictos">Grado</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.task} className={clsx(r.chosen && "bg-accent-soft")}>
            <td className={clsx("max-w-0 truncate py-1.5 pl-2", r.chosen ? "font-semibold text-accent" : "text-ink-soft")}>
              {r.task}{r.chosen && <span className="ml-1.5 text-xs font-normal">siguiente</span>}
            </td>
            <td className="py-1.5 text-right tabular-nums">{r.saturation}</td>
            <td className="py-1.5 pr-2 text-right tabular-nums">{r.degree}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function WelshPowellList({ view, step }: { view: PlanView; step: number }) {
  const adj = useMemo(() => adjacency(view), [view]);
  const order = welshPowellOrder(view, adj, step);
  const chosenAt = Math.max(0, order.findIndex((e) => e.chosen));
  const start = Math.max(0, Math.min(chosenAt - 2, order.length - WP_VISIBLE));
  return (
    <ol className="space-y-1 text-sm">
      {order.slice(start, start + WP_VISIBLE).map((e) => (
        <li key={e.task} className={clsx("flex items-center gap-2 rounded-md px-2 py-1", e.chosen && "bg-accent-soft")}>
          <span className={clsx("min-w-0 flex-1 truncate", e.chosen ? "font-semibold text-accent" : e.batch ? "text-faint" : "text-ink-soft")}>{e.task}</span>
          <span className="w-6 text-right text-xs tabular-nums text-muted">{e.degree}</span>
          <span className="w-20 text-right text-xs">
            {e.chosen ? <span className="text-accent">siguiente</span>
              : e.batch ? <span className="inline-flex items-center gap-1 text-muted"><BatchDot batch={e.batch} size={8} />lote {e.batch}</span>
              : e.blocked ? <span className="text-danger/80">choca</span>
              : <span className="text-faint">espera</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function DecisionPanel({ view, step }: { view: PlanView; step: number }) {
  const total = view.steps.length;
  const done = step >= total;
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line p-4">
        <div className="mb-3 flex items-center justify-between text-xs text-muted">
          <span>{ALGORITHM_NAMES[view.algorithm]}</span>
          <span className="tabular-nums">{step} de {total} tareas con lote</span>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-sunken">
          <div className="h-full rounded-full bg-ink transition-all duration-300" style={{ width: `${(step / Math.max(total, 1)) * 100}%` }} />
        </div>
      </div>
      <div className="border-b border-line p-4"><LastDecision view={view} step={step} /></div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {done ? (
          <div className="flex gap-3 rounded-lg bg-ok-soft p-3.5 text-sm text-ok">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            <p><strong className="font-semibold">{plural(view.metrics.colors, "lote", "lotes")}.</strong> Ninguna línea une dos tareas del mismo color, así que cada lote puede correr completo en paralelo.</p>
          </div>
        ) : (
          <>
            <p className="mb-2 text-xs font-medium text-muted">
              {view.algorithm === "dsatur" ? "Próxima decisión: la de mayor saturación (empate: mayor grado)" : "Orden por grado (de más a menos conflictos)"}
            </p>
            {view.algorithm === "dsatur" ? <DsaturTable view={view} step={step} /> : <WelshPowellList view={view} step={step} />}
          </>
        )}
      </div>
    </div>
  );
}
