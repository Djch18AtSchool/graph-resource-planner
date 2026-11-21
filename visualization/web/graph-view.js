// Dibujo interactivo del grafo de conflictos con Cytoscape.js.
// Color del nodo = lote asignado por el algoritmo. Dos disposiciones:
//   "force"   : layout de fuerzas (cose) incluido en Cytoscape.
//   "batches" : una columna por lote; como cada lote es un conjunto independiente, todas las
//               aristas cruzan entre columnas: se "ve" que la coloración es válida.

// Colores de rotulador: distinguibles entre sí y legibles sobre papel y sobre pizarra.
export const PALETTE = ["#3B6FE0", "#F08A24", "#22A06B", "#E5484D", "#8B5CF6", "#E2B203",
  "#0EA5B7", "#DB4C9A", "#7C8C2A", "#B5651D", "#84CC16", "#0F766E"];
export const FORCE_MAX_NODES = 250;          // más allá, cose tarda demasiado en el navegador
const LABEL_MAX_NODES = 80;
const GOLDEN_ANGLE = 137.508;
const COLUMN_GAP = 170;
const ROW_GAP = 50;
const DARK_TEXT = "#16213A";
const LIGHT_TEXT = "#FFFFFF";

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** Color del lote (1-indexado). Los primeros 12 son de la paleta; después, tonos por ángulo áureo. */
export function batchColor(batch) {
  if (batch <= PALETTE.length) return PALETTE[batch - 1];
  return `hsl(${Math.round((batch * GOLDEN_ANGLE) % 360)}, 58%, 46%)`;
}

/** Texto legible sobre el color de un lote (contraste por luminancia relativa). */
export function textOnBatch(batch) {
  const hex = batchColor(batch);
  if (!hex.startsWith("#")) return LIGHT_TEXT;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance > 0.33 ? DARK_TEXT : LIGHT_TEXT;
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
  const size = px(nodeCount <= 20 ? 30 : nodeCount <= 60 ? 22 : nodeCount <= 300 ? 12 : 8);
  const showLabels = nodeCount <= LABEL_MAX_NODES;
  const ink = cssVar("--ink");
  return [
    { selector: "node", style: {
      width: size, height: size, "background-color": "data(color)", "border-width": px(2), "border-color": ink,
      label: showLabels ? "data(label)" : "", "font-size": px(12), "font-family": "Bricolage Grotesque, sans-serif",
      "font-weight": 500, color: ink, "text-valign": "bottom", "text-margin-y": px(5), "text-wrap": "wrap",
      "text-max-width": px(130), "text-background-color": cssVar("--sheet"), "text-background-opacity": 0.85,
      "text-background-padding": px(2), "text-background-shape": "roundrectangle",
      "transition-property": "background-color, opacity", "transition-duration": "180ms" } },
    { selector: "edge", style: { width: px(nodeCount <= 300 ? 1.6 : 0.6), "line-color": cssVar("--edge"),
      "curve-style": "straight", opacity: nodeCount <= 300 ? 0.9 : 0.35 } },
    { selector: "edge[?explicit]", style: { "line-style": "dashed", "line-dash-pattern": [px(6), px(4)] } },
    { selector: "node.pending", style: { "background-color": cssVar("--pending"), "border-color": cssVar("--edge") } },
    { selector: "node.current", style: { "border-width": px(5), "border-color": cssVar("--focus"),
      "underlay-color": cssVar("--focus"), "underlay-opacity": 0.18, "underlay-padding": px(8), "underlay-shape": "ellipse" } },
    { selector: "node.dim, edge.dim", style: { opacity: 0.12 } },
    { selector: "node.in-clique", style: { "border-width": px(5), "underlay-color": ink, "underlay-opacity": 0.12,
      "underlay-padding": px(7), "underlay-shape": "ellipse" } },
    { selector: "edge.in-clique", style: { "line-color": ink, width: px(3.2), opacity: 1, "z-index": 5 } },
    { selector: ":selected", style: { "overlay-color": cssVar("--focus"), "overlay-opacity": 0.16 } },
  ];
}

export class GraphView {
  /** @param {HTMLElement} container @param {(text:string)=>void} onInspect */
  constructor(container, onInspect) {
    this.container = container;
    this.onInspect = onInspect;
    this.cy = null;
    this.view = null;
    this.clique = false;
    this.focusBatch = null;
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
    return new Promise((resolve) => {
      const finish = () => {
        this.cy.fit(undefined, 44);
        this.cy.style(style(view.tasks.length, this.cy.zoom() || 1));
        this.applyHighlight();
        resolve();
      };
      if (positions) { finish(); return; }
      this.cy.style(style(view.tasks.length, 1));   // etiquetas con tamaño real para que el layout las respete
      const run = this.cy.layout({ name: "cose", animate: false, randomize: true, nodeDimensionsIncludeLabels: true,
        nodeRepulsion: () => 400000, idealEdgeLength: () => 120, edgeElasticity: () => 80, nodeOverlap: 60,
        componentSpacing: 120, gravity: 0.4, numIter: 3000, padding: 40 });
      run.one("layoutstop", finish);
      run.run();
    });
  }

  bindTaps() {
    this.cy.on("tap", "node", (ev) => {
      const d = ev.target.data();
      const res = d.resources.length ? `Usa ${d.resources.join(", ")}.` : "No usa recursos.";
      this.onInspect(`«${d.label}» va en el lote ${d.batch}, dura ${d.duration} y choca con ${d.degree} tarea(s). ${res}`);
    });
    this.cy.on("tap", "edge", (ev) => {
      const d = ev.target.data();
      const why = d.resources.length ? `comparten ${d.resources.join(", ")}` : "se declaró el conflicto";
      this.onInspect(`«${d.source}» y «${d.target}» no pueden ir en el mismo lote: ${why}.`);
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
    this.clique = on;
    this.applyHighlight();
  }

  /** Destaca las tareas de un lote (o ninguno con null). */
  setBatchFocus(batch) {
    this.focusBatch = batch;
    this.applyHighlight();
  }

  applyHighlight() {
    if (!this.cy) return;
    const members = new Set(this.clique ? this.view.clique : []);
    const focus = this.focusBatch;
    this.cy.batch(() => {
      this.cy.nodes().forEach((n) => {
        const inClique = members.has(n.id());
        const keep = focus !== null ? n.data("batch") === focus : !this.clique || inClique;
        n.toggleClass("in-clique", inClique);
        n.toggleClass("dim", !keep);
      });
      this.cy.edges().forEach((e) => {
        const inClique = members.has(e.data("source")) && members.has(e.data("target"));
        e.toggleClass("in-clique", inClique && focus === null);
        e.toggleClass("dim", focus !== null || (this.clique && !inClique));
      });
    });
  }

  fit() { if (this.cy) this.cy.fit(undefined, 44); }

  clear() {
    if (this.cy) this.cy.destroy();
    this.cy = null;
  }

  png() {
    if (!this.cy) return null;
    return this.cy.png({ full: true, scale: 2, bg: cssVar("--paper") });
  }
}
