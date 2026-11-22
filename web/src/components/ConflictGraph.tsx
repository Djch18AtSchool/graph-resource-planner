// Grafo de conflictos interactivo (React Flow). Vértice = tarea; arista = no pueden ir en el mismo lote.
// El color de cada vértice muestra el lote asignado hasta el paso k del algoritmo.
import {
  Background, Controls, Handle, Position, ReactFlow, useInternalNode, useNodesState,
  type Edge, type EdgeProps, type Node, type NodeProps,
} from "@xyflow/react";
import clsx from "clsx";
import { memo, useEffect, useMemo, useRef } from "react";
import type { PlanView } from "../engine/types";
import { batchColor, textOnBatch } from "../lib/colors";
import { colorsAfter } from "../lib/decisions";
import { batchLayout, forceLayout, type Layout } from "../lib/layout";

export type GraphLayout = "free" | "batches";
const NODE_SIZE = 40;
// Margen proporcional al lienzo: deja lugar a las etiquetas, que se dibujan fuera de la caja del vértice.
const FIT_VIEW = { padding: { top: "6%", bottom: "10%", x: "11%" } } as const;

type TaskData = { label: string; batch: number | null; current: boolean; dimmed: boolean };
type ConflictData = { resources: string[]; explicit: boolean; active: boolean; dimmed: boolean };
type TaskNode = Node<TaskData, "task">;
type ConflictEdgeType = Edge<ConflictData, "conflict">;

const HIDDEN_HANDLE = { opacity: 0, pointerEvents: "none" as const, top: "50%", left: "50%" };

const TaskNodeView = memo(function TaskNodeView({ data }: NodeProps<TaskNode>) {
  const colored = data.batch !== null;
  return (
    <div className={clsx("relative transition-opacity duration-300", data.dimmed && "opacity-25")} style={{ width: NODE_SIZE, height: NODE_SIZE }}>
      <Handle type="target" position={Position.Top} style={HIDDEN_HANDLE} isConnectable={false} />
      <Handle type="source" position={Position.Top} style={HIDDEN_HANDLE} isConnectable={false} />
      {data.current && <span className="absolute -inset-2 animate-ping rounded-full bg-accent/25" aria-hidden />}
      <div
        className={clsx(
          "relative grid size-full place-items-center rounded-full border-2 text-xs font-semibold transition-colors duration-300",
          data.current ? "border-accent ring-4 ring-accent/20" : colored ? "border-white shadow-card" : "border-line-strong bg-surface",
        )}
        style={colored ? { background: batchColor(data.batch!), color: textOnBatch(data.batch!) } : undefined}
      >
        {colored ? data.batch : ""}
      </div>
      <span className="pointer-events-none absolute left-1/2 top-full mt-1.5 -translate-x-1/2 whitespace-nowrap rounded bg-surface/90 px-1 text-[11.5px] font-medium text-ink-soft">
        {data.label}
      </span>
    </div>
  );
});

function center(node: ReturnType<typeof useInternalNode>) {
  if (!node) return null;
  return {
    x: node.internals.positionAbsolute.x + (node.measured.width ?? NODE_SIZE) / 2,
    y: node.internals.positionAbsolute.y + (node.measured.height ?? NODE_SIZE) / 2,
  };
}

/** Arista recta de centro a centro (el grafo es no dirigido: no hay puertos de entrada/salida). */
function ConflictEdgeView({ source, target, data }: EdgeProps<ConflictEdgeType>) {
  const a = center(useInternalNode(source));
  const b = center(useInternalNode(target));
  if (!a || !b || !data) return null;
  const why = data.resources.length ? `Comparten ${data.resources.join(", ")}` : "Conflicto declarado";
  return (
    <g className={clsx("transition-opacity duration-300", data.dimmed && "opacity-15")}>
      <title>{`${source} — ${target}: ${why}`}</title>
      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth={14} />
      <line
        x1={a.x} y1={a.y} x2={b.x} y2={b.y}
        stroke={data.active ? "var(--color-accent)" : "#b6bfcc"}
        strokeWidth={data.active ? 2.4 : 1.4}
        strokeDasharray={data.explicit ? "6 5" : undefined}
      />
    </g>
  );
}

const nodeTypes = { task: TaskNodeView };
const edgeTypes = { conflict: ConflictEdgeView };

export function ConflictGraph({ view, step, layout, focusBatch = null }: {
  view: PlanView;
  step: number;
  layout: GraphLayout;
  focusBatch?: number | null;
}) {
  // El padre remonta este componente (key) al cambiar de disposición, así fitView ve las posiciones correctas.
  const computed: Layout = useMemo(() => (layout === "batches" ? batchLayout(view) : forceLayout(view)), [view, layout]);
  const colors = useMemo(() => colorsAfter(view, step), [view, step]);
  const current = step > 0 && step < view.steps.length ? view.steps[step - 1].task : null;
  const batchOf = useMemo(() => new Map(view.tasks.map((t) => [t.id, t.batch])), [view]);

  const dataFor = (id: string): TaskData => ({
    label: id,
    batch: colors.get(id) ?? null,
    current: id === current,
    dimmed: focusBatch !== null && batchOf.get(id) !== focusBatch,
  });
  const build = (layoutMap: Layout): TaskNode[] => view.tasks.map((t) => ({
    id: t.id, type: "task", origin: [0.5, 0.5], position: layoutMap.get(t.id) ?? { x: 0, y: 0 }, data: dataFor(t.id),
  }));

  // Estado controlado con useNodesState: aplica TODOS los cambios de React Flow (posición y también las
  // dimensiones medidas). Si se descartan las dimensiones, React Flow oculta y vuelve a medir los vértices
  // en cada cuadro del arrastre y el grafo parpadea.
  const [nodes, setNodes, onNodesChange] = useNodesState<TaskNode>(build(computed));

  // Otro problema u otra disposición: posiciones nuevas.
  const builtFrom = useRef(computed);
  useEffect(() => {
    if (builtFrom.current === computed) return;
    builtFrom.current = computed;
    setNodes(build(computed));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al cambiar el layout calculado
  }, [computed]);

  // Avanza el algoritmo o cambia el lote resaltado: solo cambian los datos; posición y medidas se conservan.
  useEffect(() => {
    setNodes((prev) => prev.map((n) => ({ ...n, data: dataFor(n.id) })));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- dataFor depende de estos valores
  }, [colors, current, focusBatch, batchOf]);

  const edges: ConflictEdgeType[] = useMemo(() => view.conflicts.map((c, i) => ({
    id: `c${i}`,
    source: c.source,
    target: c.target,
    type: "conflict",
    selectable: false,
    data: {
      resources: c.resources,
      explicit: c.explicit,
      active: current !== null && (c.source === current || c.target === current),
      dimmed: focusBatch !== null,
    },
  })), [view, current, focusBatch]);

  return (
    <ReactFlow<TaskNode, ConflictEdgeType>
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodesChange={onNodesChange}
      nodesConnectable={false}
      fitView
      fitViewOptions={FIT_VIEW}
      minZoom={0.15}
      maxZoom={2.5}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={22} size={1.2} color="#d7dce4" />
      <Controls showInteractive={false} position="bottom-right" />
    </ReactFlow>
  );
}
