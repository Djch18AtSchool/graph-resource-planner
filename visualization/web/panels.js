// Paneles de resultados. Todo texto que viene del LLM o del usuario se inserta con textContent;
// el reporte Markdown se convierte con marked y se SANITIZA con DOMPurify antes de insertarlo.
import { batchColor } from "./graph-view.js";

// Solo el subconjunto de HTML que produce Markdown. Sin enlaces, imágenes ni formularios: el reporte
// lo redacta un LLM y una inyección de prompt podría intentar dibujar un "formulario de API key".
const REPORT_SANITIZE = {
  ALLOWED_TAGS: ["h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote",
    "br", "hr", "table", "thead", "tbody", "tr", "th", "td", "del"],
  ALLOWED_ATTR: [],
};

/** Crea un elemento con clase y texto (sin innerHTML). */
export function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "") node.textContent = text;
  return node;
}

const STAGES = {
  coloring: "Coloración (algoritmo elegido)", coloring_welsh_powell: "Welsh-Powell (comparación)",
  chromatic_bounds: "Cotas de χ(G) + χ exacto (B&B)", planarity: "Test de planaridad + Kuratowski",
  planarization: "Planarización (nodos virtuales)", drawing: "Dibujo plano (Tutte + refinamiento)",
};

function metric(k, v, s = "") {
  const box = el("div", "metric");
  box.append(el("div", "k", k), el("div", "v", String(v)));
  if (s) box.append(el("div", "s", s));
  return box;
}

export function renderMetrics(container, view) {
  const f = view.facts;
  const c = f.chromatic;
  const p = f.planarity;
  const chi = c.exact !== null ? `χ(G) = ${c.exact} (exacto)` : `${c.lower} ≤ χ(G) ≤ ${c.upper}`;
  container.replaceChildren(
    metric("Componentes", f.nodes, `${f.dependency_edges} dependencias · ${f.conflict_edges} conflictos`),
    metric("Lotes de ejecución", c.colors_used, chi),
    metric("Paralelismo máximo", f.max_parallel_tasks, "tareas en el lote más grande"),
    metric("¿Plano?", p.is_planar ? "Sí" : "No", p.is_planar ? "dibujable sin cruces" : `contiene subdivisión de ${p.witness}`),
    metric("Nodos virtuales", p.virtual_nodes, p.is_planar ? "no hicieron falta" : `${p.crossings} cruce(s) resueltos`),
  );
}

export function renderPlan(container, view) {
  const f = view.facts;
  const list = el("div", "batches");
  f.schedule.forEach((slot) => {
    const row = el("div", "batch");
    const head = el("div", "head");
    const sw = el("span", "sw");
    Object.assign(sw.style, { display: "inline-block", width: "12px", height: "12px", borderRadius: "50%", background: batchColor(slot.slot) });
    const title = el("span", "", `Lote ${slot.slot}`);
    title.append(el("small", "", `${slot.tasks.length} en paralelo`));
    head.append(sw, title);
    const tags = el("div", "tags");
    slot.tasks.forEach((t) => tags.append(el("span", "tag", t)));
    row.append(head, tags);
    list.append(row);
  });
  const parts = [el("p", "hint", "Los lotes se ejecutan en secuencia; dentro de un lote todo corre en paralelo sin conflictos de recursos.")];
  parts.push(list);
  if (f.unconstrained.length) {
    parts.push(el("p", "hint", `Sin restricciones (pueden ir en cualquier lote): ${f.unconstrained.join(", ")}.`));
  }
  if (f.forcing_clique.length > 1) {
    parts.push(el("p", "hint", `Clique que fuerza ${f.forcing_clique.length} lotes (ω(G) ≤ χ(G)): ${f.forcing_clique.join(", ")}.`));
  }
  container.replaceChildren(...parts);
}

export function renderReport(container, view) {
  if (!view.report) {
    container.replaceChildren(el("p", "hint", "Reporte desactivado."));
    return;
  }
  const html = window.DOMPurify.sanitize(window.marked.parse(view.report), REPORT_SANITIZE);
  const source = view.report_source === "llm" ? `Redactado por el LLM (${view.provider})` : "Plantilla determinista (sin LLM)";
  const wrap = el("div");
  wrap.innerHTML = html;                       // sanitizado con DOMPurify
  container.replaceChildren(el("p", "hint", `${source}. El bloque «Datos verificados» lo genera el código, no el LLM.`), wrap);
}

export function renderMatrix(container, view) {
  const m = view.conflict_matrix;
  if (!m) {
    container.replaceChildren(el("p", "hint", "La matriz se muestra para grafos de hasta 40 vértices."));
    return;
  }
  const table = el("table");
  const head = el("tr");
  head.append(el("th", "row", "v \\ w"));
  m.labels.forEach((l, j) => { const th = el("th", "", String(j + 1)); th.title = l; head.append(th); });
  head.append(el("th", "", "grado"));
  table.append(head);
  m.rows.forEach((row, i) => {
    const tr = el("tr");
    tr.append(el("th", "row", `${i + 1}. ${m.labels[i]}`));
    row.forEach((x) => tr.append(el("td", x ? "one" : "", String(x))));
    tr.append(el("td", "", String(m.degrees[i])));
    table.append(tr);
  });
  const wrap = el("div", "table-wrap");
  wrap.append(table);
  container.replaceChildren(
    el("p", "hint", "Grafo de conflictos (el que se colorea). A[i][j] = 1 si las tareas i y j comparten un recurso exclusivo. Espacio O(V²); la lista de adyacencia usa O(V + E)."),
    wrap,
  );
}

export function renderTimes(container, view) {
  const table = el("table", "times");
  const head = el("tr");
  head.append(el("th", "", "Etapa (Python en el navegador)"), el("th", "", "ms"));
  table.append(head);
  Object.entries(view.timings_ms).forEach(([k, v]) => {
    const tr = el("tr");
    tr.append(el("td", "", STAGES[k] || k), el("td", "", v.toFixed(2)));
    table.append(tr);
  });
  container.replaceChildren(table);
}

export function renderLegend(container, view, layout) {
  const used = [...new Set(view.facts.schedule.map((s) => s.slot))];
  const items = used.map((b) => {
    const span = el("span");
    const sw = el("span", "sw");
    sw.style.background = batchColor(b);
    span.append(sw, document.createTextNode(`Lote ${b}`));
    return span;
  });
  const free = el("span");
  const sw = el("span", "sw");
  sw.style.background = batchColor(null);
  free.append(sw, document.createTextNode("Sin conflictos"));
  const dep = el("span");
  dep.append(el("span", "ln"), document.createTextNode("Dependencia (→ depende de)"));
  const con = el("span");
  con.append(el("span", "ln conflict"), document.createTextNode("Conflicto de recurso"));
  items.push(free, dep, con);
  if (layout === "planar" && view.facts.planarity.virtual_nodes > 0) {
    const v = el("span");
    v.append(el("span", "dm"), document.createTextNode("Nodo virtual (cruce)"));
    items.push(v);
  }
  if (!view.facts.planarity.is_planar) {
    const k = el("span");
    k.append(el("span", "ln kura"), document.createTextNode(`Certificado ${view.facts.planarity.witness}`));
    items.push(k);
  }
  container.replaceChildren(...items);
}
