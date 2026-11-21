// Reconstruye, para un paso k del algoritmo, la tabla de decisión que vería un estudiante:
// DSatur -> candidatas ordenadas por saturación y grado; Welsh-Powell -> orden por grado y ronda actual.
import type { PlanView } from "../engine/types";

export interface Candidate {
  task: string;
  saturation: number;
  degree: number;
  chosen: boolean;
}

export interface WpEntry {
  task: string;
  degree: number;
  batch: number | null;     // lote ya asignado antes del paso k
  blocked: boolean;         // choca con una tarea ya puesta en el lote de esta ronda
  chosen: boolean;
}

export type Adjacency = Map<string, Set<string>>;

export function adjacency(view: Pick<PlanView, "tasks" | "conflicts">): Adjacency {
  const adj: Adjacency = new Map(view.tasks.map((t) => [t.id, new Set<string>()]));
  view.conflicts.forEach((c) => {
    adj.get(c.source)?.add(c.target);
    adj.get(c.target)?.add(c.source);
  });
  return adj;
}

/** Lote de cada tarea después de los primeros k pasos. */
export function colorsAfter(view: Pick<PlanView, "steps">, k: number): Map<string, number> {
  return new Map(view.steps.slice(0, k).map((s) => [s.task, s.batch]));
}

/** Candidatas de DSatur antes del paso k+1, en el orden en que el algoritmo las considera. */
export function dsaturCandidates(view: Pick<PlanView, "tasks" | "steps">, adj: Adjacency, k: number, limit = 6): Candidate[] {
  const colored = colorsAfter(view, k);
  const next = view.steps[k]?.task;
  const order = new Map(view.tasks.map((t, i) => [t.id, i]));
  return view.tasks
    .filter((t) => !colored.has(t.id))
    .map((t) => {
      const seen = new Set<number>();
      adj.get(t.id)?.forEach((u) => { const c = colored.get(u); if (c !== undefined) seen.add(c); });
      return { task: t.id, saturation: seen.size, degree: adj.get(t.id)?.size ?? 0, chosen: t.id === next };
    })
    .sort((a, b) => b.saturation - a.saturation || b.degree - a.degree || order.get(a.task)! - order.get(b.task)!)
    .slice(0, limit);
}

/** Orden de Welsh-Powell (grado decreciente, estable) con el estado de cada tarea en el paso k. */
export function welshPowellOrder(view: Pick<PlanView, "tasks" | "steps">, adj: Adjacency, k: number): WpEntry[] {
  const colored = colorsAfter(view, k);
  const next = view.steps[k];
  const round = next?.batch ?? null;
  const inRound = new Set([...colored].filter(([, b]) => b === round).map(([t]) => t));
  return [...view.tasks]
    .sort((a, b) => (adj.get(b.id)?.size ?? 0) - (adj.get(a.id)?.size ?? 0))
    .map((t) => ({
      task: t.id,
      degree: adj.get(t.id)?.size ?? 0,
      batch: colored.get(t.id) ?? null,
      blocked: !colored.has(t.id) && [...(adj.get(t.id) ?? [])].some((u) => inRound.has(u)),
      chosen: t.id === next?.task,
    }));
}
