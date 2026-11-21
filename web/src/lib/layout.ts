// Posiciones de los vértices del grafo de conflictos.
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, type SimulationNodeDatum } from "d3-force";
import type { PlanView } from "../engine/types";

export type Point = { x: number; y: number };
export type Layout = Map<string, Point>;

const LINK_DISTANCE = 120;
const CHARGE = -520;
const COLLIDE_RADIUS = 58;
const TICKS = 320;
const COLUMN_GAP = 210;
const ROW_GAP = 92;

type SimNode = SimulationNodeDatum & { id: string };

/** Layout de fuerzas determinista (d3 arranca en una espiral fija, sin aleatoriedad). */
export function forceLayout(view: Pick<PlanView, "tasks" | "conflicts">): Layout {
  const nodes: SimNode[] = view.tasks.map((t) => ({ id: t.id }));
  const links = view.conflicts.map((c) => ({ source: c.source, target: c.target }));
  const sim = forceSimulation(nodes)
    .force("link", forceLink<SimNode, { source: string; target: string }>(links).id((d) => d.id).distance(LINK_DISTANCE))
    .force("charge", forceManyBody().strength(CHARGE))
    .force("collide", forceCollide(COLLIDE_RADIUS))
    .force("center", forceCenter(0, 0))
    .stop();
  sim.tick(TICKS);
  return new Map(nodes.map((n) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }]));
}

/**
 * Una columna por lote. Cada lote es un conjunto independiente, así que ninguna arista queda dentro
 * de una columna: la vista muestra a simple vista que la coloración es válida.
 */
export function batchLayout(view: Pick<PlanView, "batches">): Layout {
  const tallest = Math.max(1, ...view.batches.map((b) => b.tasks.length));
  const layout: Layout = new Map();
  view.batches.forEach((b, col) => {
    const offset = ((tallest - b.tasks.length) * ROW_GAP) / 2;
    b.tasks.forEach((t, row) => layout.set(t, { x: col * COLUMN_GAP, y: offset + row * ROW_GAP }));
  });
  return layout;
}
