// Dibujo interactivo del grafo con Cytoscape.js. Las POSICIONES no se calculan aquí: llegan de
// Python (embedding plano de Tutte refinado, o layout de fuerzas de networkx) y se usan tal cual
// (layout "preset"). Así lo que se ve es exactamente lo que verificó count_crossings.

export const PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2", "#72B7B2",
  "#EECA3B", "#9D755D", "#FF9DA6", "#79706E", "#439894", "#D67195"];

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** Color de un lote (1-indexado); null = sin restricciones. */
export const batchColor = (batch) => (batch ? PALETTE[(batch - 1) % PALETTE.length] : cssVar("--free"));

/**
 * @param {{source:string,target:string,kinds:string[],original:string[]}} e
 * @returns {"source"|"target"|"none"} extremo donde va la flecha de la dependencia
 */
function arrowSide(e) {
  if (!e.kinds.includes("dependency")) return "none";
  if (e.target === e.original[1]) return "target";
  if (e.source === e.original[1]) return "source";
  return "none";                       // tramo intermedio de una arista partida por nodos virtuales
}

function elements(drawing) {
  const nodes = drawing.nodes.map((n) => ({
    group: "nodes",
    data: { ...n, color: batchColor(n.batch) },
    position: { x: n.x, y: n.y },
    classes: [n.virtual ? "virtual" : "real", n.kuratowski ? "kura-node" : ""].join(" "),
  }));
  const edges = drawing.edges.map((e) => ({
    group: "edges",
    data: { ...e, arrow: arrowSide(e) },
    classes: [e.kinds.includes("conflict") ? "conflict" : "dependency", e.kuratowski ? "kura-edge" : "",
      `arrow-${arrowSide(e)}`].join(" "),
  }));
  return [...nodes, ...edges];
}

// Tamaños en PÍXELES DE PANTALLA; se dividen por el zoom inicial (fit) para que se vean igual
// sin importar la extensión del dibujo (las coordenadas de Python van de 0 a 1000).
function style(nodeCount, zoom) {
  const text = cssVar("--text");
  const px = (v) => v / zoom;
  const size = px(nodeCount <= 20 ? 26 : nodeCount <= 45 ? 18 : 11);
  return [
    { selector: "node.real", style: {
      width: size, height: size, "background-color": "data(color)", "border-width": px(1.5),
      "border-color": "#20242a", label: "data(label)", "font-size": px(nodeCount <= 45 ? 11.5 : 9),
      "font-family": "Inter, sans-serif", color: text, "text-valign": "bottom", "text-margin-y": px(3),
      "text-wrap": "wrap", "text-max-width": px(120), "text-background-color": cssVar("--graph-bg"),
      "text-background-opacity": 0.8, "text-background-padding": px(1) } },
    { selector: "node.virtual", style: {
      shape: "diamond", width: size * 0.55, height: size * 0.55, "background-color": cssVar("--surface"),
      "border-width": px(2), "border-color": text } },
    { selector: "edge", style: { width: px(1.6), "line-color": cssVar("--edge"), "curve-style": "straight",
      "target-arrow-color": cssVar("--edge"), "source-arrow-color": cssVar("--edge"), "arrow-scale": 1 } },
    { selector: "edge.arrow-target", style: { "target-arrow-shape": "triangle" } },
    { selector: "edge.arrow-source", style: { "source-arrow-shape": "triangle" } },
    { selector: "edge.conflict", style: { "line-color": cssVar("--conflict"), "line-style": "dashed",
      width: px(2), "line-dash-pattern": [px(6), px(4)] } },
    { selector: "edge.kura-active.kura-edge", style: { "line-color": cssVar("--kura"), width: px(4), "line-style": "solid", "z-index": 5 } },
    { selector: "edge.kura-active[!kuratowski]", style: { opacity: 0.2 } },
    { selector: "node.kura-active.kura-node", style: { "border-color": cssVar("--kura"), "border-width": px(4) } },
    { selector: ":selected", style: { "overlay-color": cssVar("--accent"), "overlay-opacity": 0.18 } },
  ];
}

export class GraphView {
  /** @param {HTMLElement} container @param {(text:string)=>void} onInspect */
  constructor(container, onInspect) {
    this.container = container;
    this.onInspect = onInspect;
    this.cy = null;
  }

  render(drawing, labels) {
    if (this.cy) this.cy.destroy();
    const nReal = drawing.nodes.filter((n) => !n.virtual).length;
    this.cy = cytoscape({
      container: this.container, elements: elements(drawing),
      layout: { name: "preset", fit: true, padding: 48 }, wheelSensitivity: 0.25, minZoom: 0.05, maxZoom: 6,
    });
    this.cy.style(style(nReal, this.cy.zoom() || 1));
    this.cy.on("tap", "node.real", (ev) => {
      const d = ev.target.data();
      const lote = d.batch ? `lote ${d.batch}` : "sin conflictos (cualquier lote)";
      this.onInspect(`${d.label} · ${d.type} · grado ${d.degree} · ${lote}${d.description ? ` — ${d.description}` : ""}`);
    });
    this.cy.on("tap", "node.virtual", () =>
      this.onInspect("Nodo virtual: reemplaza un cruce de dos aristas para que el dibujo sea plano."));
    this.cy.on("tap", "edge", (ev) => {
      const d = ev.target.data();
      const [a, b] = d.original;
      const tipo = d.kinds.join(" + ");
      this.onInspect(`${labels(a)} — ${labels(b)} · ${tipo}${d.reason ? ` — ${d.reason}` : ""}`);
    });
    this.cy.on("tap", (ev) => { if (ev.target === this.cy) this.onInspect("Toque un nodo o una arista para ver el detalle."); });
  }

  /** Resalta (o no) la subdivisión de K5 / K3,3 que certifica la NO planaridad. */
  setKuratowski(on) {
    if (this.cy) this.cy.elements().toggleClass("kura-active", on);
  }

  fit() { if (this.cy) this.cy.fit(undefined, 48); }

  png() {
    if (!this.cy) return null;
    return this.cy.png({ full: true, scale: 2, bg: cssVar("--graph-bg") });
  }
}
