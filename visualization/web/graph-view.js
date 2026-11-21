// Dibujo interactivo del grafo de conflictos con Cytoscape.js.
// Color del nodo = lote asignado por el algoritmo. Dos disposiciones:
//   "force"   : layout de fuerzas (cose) incluido en Cytoscape.
//   "batches" : una columna por lote; como cada lote es un conjunto independiente, todas las
//               aristas cruzan entre columnas: se "ve" que la coloración es válida.

export const PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2", "#72B7B2",
  "#EECA3B", "#9D755D", "#FF9DA6", "#79706E", "#439894", "#D67195"];
export const FORCE_MAX_NODES = 250;          // más allá, cose tarda demasiado en el navegador
const LABEL_MAX_NODES = 80;
const GOLDEN_ANGLE = 137.508;
const COLUMN_GAP = 170;
const ROW_GAP = 46;

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** Color del lote (1-indexado). Los primeros 12 son de la paleta; después, tonos por ángulo áureo. */
export function batchColor(batch) {
  if (batch <= PALETTE.length) return PALETTE[batch - 1];
  return `hsl(${Math.round((batch * GOLDEN_ANGLE) % 360)}, 55%, 55%)`;
}

/**
 * Posiciones "por lotes": cada lote ocupa una franja; si un lote es muy alto se parte en sub-columnas.
 * @param {{batches: {index:number, tasks:string[]}[], tasks: object[]}} view
 * @returns {Map<string, {x:number, y:number}>}
 */
function batchPositions(view) {
  const maxRows = Math.max(8, Math.ceil(Math.sqrt(view.tasks.length) * 1.5));
  const pos = new Map();
  let x = 0;
  view.batches.forEach((b) => {
    const cols = Math.ceil(b.tasks.length / maxRows);
    const rows = Math.ceil(b.tasks.length / cols);
    b.tasks.forEach((t, i) => {
      pos.set(t, { x: x + Math.floor(i / rows) * (COLUMN_GAP / 2), y: (i % rows) * ROW_GAP });
    });
    x += (cols - 1) * (COLUMN_GAP / 2) + COLUMN_GAP;
  });
  return pos;
}

function elements(view) {
  const nodes = view.tasks.map((t) => ({
    group: "nodes",
    data: { id: t.id, label: t.id, batch: t.batch, color: batchColor(t.batch), duration: t.duration,
      degree: t.degree, resources: t.resources },
  }));
  // Sin id: Cytoscape genera uno único (un id "e0" chocaría con una tarea llamada "e0").
  const edges = view.conflicts.map((c) => ({
    group: "edges",
    data: { source: c.source, target: c.target, resources: c.resources, explicit: c.explicit },
  }));
  return [...nodes, ...edges];
}

// Tamaños en píxeles de pantalla divididos por el zoom tras ajustar: se ven igual en grafos grandes y chicos.
function style(nodeCount, zoom) {
  const px = (v) => v / zoom;
  const size = px(nodeCount <= 20 ? 28 : nodeCount <= 60 ? 20 : nodeCount <= 300 ? 12 : 8);
  const showLabels = nodeCount <= LABEL_MAX_NODES;
  return [
    { selector: "node", style: {
      width: size, height: size, "background-color": "data(color)", "border-width": px(1.5),
      "border-color": "#20242a", label: showLabels ? "data(label)" : "", "font-size": px(11),
      "font-family": "Inter, sans-serif", color: cssVar("--text"), "text-valign": "bottom", "text-margin-y": px(3),
      "text-wrap": "wrap", "text-max-width": px(120), "text-background-color": cssVar("--graph-bg"),
      "text-background-opacity": 0.8, "text-background-padding": px(1) } },
    { selector: "edge", style: { width: px(nodeCount <= 300 ? 1.4 : 0.6), "line-color": cssVar("--edge"),
      "curve-style": "straight", opacity: nodeCount <= 300 ? 0.85 : 0.35 } },
    { selector: "edge[?explicit]", style: { "line-style": "dashed", "line-dash-pattern": [px(6), px(4)] } },
    { selector: "node.pending", style: { "background-color": cssVar("--free"), "border-color": cssVar("--edge") } },
    { selector: "node.current", style: { "border-color": cssVar("--accent"), "border-width": px(5) } },
    { selector: "node.faded, edge.faded", style: { opacity: 0.12 } },
    { selector: "node.in-clique", style: { "border-color": cssVar("--clique"), "border-width": px(4) } },
    { selector: "edge.in-clique", style: { "line-color": cssVar("--clique"), width: px(3), opacity: 1, "z-index": 5 } },
    { selector: ":selected", style: { "overlay-color": cssVar("--accent"), "overlay-opacity": 0.18 } },
  ];
}

export class GraphView {
  /** @param {HTMLElement} container @param {(text:string)=>void} onInspect */
  constructor(container, onInspect) {
    this.container = container;
    this.onInspect = onInspect;
    this.cy = null;
    this.view = null;
  }

  /** Dibuja la vista. Devuelve una promesa que se resuelve cuando termina el layout. */
  render(view, layout) {
    if (this.cy) this.cy.destroy();
    this.view = view;
    const positions = layout === "batches" ? batchPositions(view) : null;
    this.cy = cytoscape({
      container: this.container, elements: elements(view), wheelSensitivity: 0.25, minZoom: 0.02, maxZoom: 6,
      layout: { name: "preset", positions: positions ? (n) => positions.get(n.id()) : undefined },
    });
    this.bindTaps();
    const done = new Promise((resolve) => {
      const finish = () => {
        this.cy.fit(undefined, 40);
        this.cy.style(style(view.tasks.length, this.cy.zoom() || 1));
        resolve();
      };
      if (positions) { finish(); return; }
      const run = this.cy.layout({ name: "cose", animate: false, randomize: true, nodeRepulsion: () => 60000,
        idealEdgeLength: () => 110, nodeOverlap: 40, componentSpacing: 90, gravity: 0.6, numIter: 2500 });
      run.one("layoutstop", finish);
      run.run();
    });
    return done;
  }

  bindTaps() {
    this.cy.on("tap", "node", (ev) => {
      const d = ev.target.data();
      const res = d.resources.length ? ` · recursos: ${d.resources.join(", ")}` : "";
      this.onInspect(`${d.label} · lote ${d.batch} · duración ${d.duration} · grado ${d.degree}${res}`);
    });
    this.cy.on("tap", "edge", (ev) => {
      const d = ev.target.data();
      const why = [d.resources.length ? `comparten ${d.resources.join(", ")}` : "", d.explicit ? "conflicto declarado" : ""]
        .filter(Boolean).join(" · ");
      this.onInspect(`${d.source} — ${d.target} · ${why}`);
    });
  }

  /** Muestra el estado tras `k` pasos del algoritmo (k = total -> coloración completa). */
  setStep(k) {
    if (!this.cy) return;
    const steps = this.view.steps;
    const done = new Set(steps.slice(0, k).map((s) => s.task));
    const current = k > 0 && k < steps.length ? steps[k - 1].task : null;
    this.cy.batch(() => {
      this.cy.nodes().forEach((n) => {
        n.toggleClass("pending", !done.has(n.id()));
        n.toggleClass("current", n.id() === current);
      });
    });
  }

  /** Resalta la clique que justifica la cota inferior de χ(G). */
  setClique(on) {
    if (!this.cy) return;
    const members = new Set(on ? this.view.clique : []);
    this.cy.batch(() => {
      this.cy.nodes().forEach((n) => {
        const inside = members.has(n.id());
        n.toggleClass("in-clique", inside);
        n.toggleClass("faded", on && !inside);
      });
      this.cy.edges().forEach((e) => {
        const inside = members.has(e.data("source")) && members.has(e.data("target"));
        e.toggleClass("in-clique", inside);
        e.toggleClass("faded", on && !inside);
      });
    });
  }

  fit() { if (this.cy) this.cy.fit(undefined, 40); }

  clear() {
    if (this.cy) this.cy.destroy();
    this.cy = null;
  }

  png() {
    if (!this.cy) return null;
    return this.cy.png({ full: true, scale: 2, bg: cssVar("--graph-bg") });
  }
}
