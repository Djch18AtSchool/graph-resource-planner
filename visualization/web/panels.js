// Paneles de resultados. Todo texto del usuario se inserta con textContent (nunca innerHTML).
import { batchColor } from "./graph-view.js";

const GANTT_MAX_TASKS = 80;
const CHIPS_PER_BATCH = 40;
const LEGEND_MAX_BATCHES = 12;
const LONG_METRIC_CHARS = 9;
const NAMES = { dsatur: "DSatur", welsh_powell: "Welsh-Powell" };
const STAGES = {
  conflict_graph: "Construir el grafo de conflictos", coloring: "Coloración (algoritmo elegido)",
  alternative: "Coloración (el otro algoritmo)", bounds: "Cotas de χ(G) y χ exacto (branch & bound)",
};

/** Crea un elemento con clase y texto. */
export function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "") node.textContent = text;
  return node;
}

const fmt = (x) => (Number.isInteger(x) ? String(x) : x.toFixed(2).replace(/\.?0+$/, ""));
export const algorithmName = (key) => NAMES[key] || key;

function swatch(batch) {
  const sw = el("span", "sw");
  sw.style.background = batchColor(batch);
  return sw;
}

function metric(key, k, v, s = "") {
  const box = el("div", "metric");
  box.dataset.metric = key;
  box.append(el("div", "k", k), el("div", String(v).length > LONG_METRIC_CHARS ? "v long" : "v", String(v)));
  if (s) box.append(el("div", "s", s));
  return box;
}

export function chiText(m) {
  return m.exact !== null ? `χ(G) = ${m.exact}` : `${m.lower} ≤ χ(G) ≤ ${m.upper}`;
}

export function renderMetrics(container, view) {
  const m = view.metrics;
  const optimal = m.exact !== null && m.colors === m.exact;
  const proven = { clique: "óptimo: la clique iguala a la heurística", branch_and_bound: "exacto (branch & bound)" };
  const chiSub = proven[m.exact_method] || `cota: clique ≤ χ ≤ mejor heurística · Δ+1 = ${m.greedy_bound}`;
  container.replaceChildren(
    metric("tasks", "Tareas", m.tasks, `${m.conflicts} conflictos · Δ = ${m.max_degree}`),
    metric("colors", "Lotes", m.colors, `${algorithmName(view.algorithm)}${optimal ? " · óptimo" : ""}`),
    metric("chi", "Número cromático", chiText(m), chiSub),
    metric("alternative", "Comparación", view.alternative.colors, `lotes con ${algorithmName(view.alternative.algorithm)}`),
    metric("workers", "Ejecutores", m.workers, "tareas en el lote más grande"),
    metric("makespan", "Tiempo total", fmt(m.makespan), `secuencial ${fmt(m.sequential)} · ${m.speedup}× más rápido`),
  );
}

// ------------------------------------------------------------------------------------- plan
function gantt(view) {
  const total = view.metrics.makespan || 1;
  const batchOf = new Map(view.tasks.map((t) => [t.id, t]));
  const chart = el("div", "gantt");
  view.batches.forEach((b) => {
    const group = el("div", "gantt-batch");
    const head = el("div", "gantt-head");
    head.append(swatch(b.index), document.createTextNode(`Lote ${b.index} · t = ${fmt(b.start)} → ${fmt(b.start + b.duration)}`));
    group.append(head);
    b.tasks.forEach((id) => {
      const task = batchOf.get(id);
      const row = el("div", "gantt-row");
      const track = el("div", "gantt-track");
      const bar = el("div", "gantt-bar");
      bar.style.left = `${(b.start / total) * 100}%`;
      bar.style.width = `${Math.max((task.duration / total) * 100, 0.8)}%`;
      bar.style.background = batchColor(b.index);
      bar.title = `${id}: ${fmt(task.duration)}`;
      track.append(bar);
      row.append(el("span", "gantt-name", id), track);
      group.append(row);
    });
    chart.append(group);
  });
  return chart;
}

function batchList(view) {
  const list = el("div", "batches");
  view.batches.forEach((b) => {
    const row = el("div", "batch");
    const head = el("div", "head");
    const title = el("span", "", `Lote ${b.index}`);
    title.append(el("small", "", `${b.tasks.length} en paralelo`));
    head.append(swatch(b.index), title);
    const tags = el("div", "tags");
    b.tasks.slice(0, CHIPS_PER_BATCH).forEach((t) => tags.append(el("span", "tag", t)));
    if (b.tasks.length > CHIPS_PER_BATCH) tags.append(el("span", "tag more", `+${b.tasks.length - CHIPS_PER_BATCH} más`));
    row.append(head, tags);
    list.append(row);
  });
  return list;
}

export function renderPlan(container, view) {
  const intro = el("p", "hint first",
    "Los lotes corren uno tras otro; dentro de un lote todas las tareas corren en paralelo sin compartir recursos. "
    + "Cada lote dura lo que su tarea más larga.");
  const body = view.tasks.length <= GANTT_MAX_TASKS ? gantt(view) : batchList(view);
  container.replaceChildren(intro, body);
}

// --------------------------------------------------------------------------------- recursos
export function renderResources(container, view) {
  if (!view.resources.length) {
    container.replaceChildren(el("p", "hint first", "Este problema solo tiene conflictos declarados (sin recursos)."));
    return;
  }
  const table = el("table", "resources");
  const head = el("tr");
  head.append(el("th", "", "Recurso"), el("th", "", "Tareas que lo usan"), el("th", "", "Clique"));
  table.append(head);
  view.resources.forEach((r) => {
    const tr = el("tr");
    tr.append(el("td", "", r.name), el("td", "left", r.tasks.join(", ")), el("td", "", `K${r.tasks.length}`));
    table.append(tr);
  });
  const wrap = el("div", "table-wrap");
  wrap.append(table);
  container.replaceChildren(
    el("p", "hint first", `Las tareas que comparten un recurso se bloquean todas entre sí: forman una clique. `
      + `Por eso hacen falta al menos tantos lotes como usuarios tenga el recurso más disputado (${view.metrics.max_resource_usage}).`),
    wrap,
  );
}

// ---------------------------------------------------------------------------------- matriz
export function renderMatrix(container, view) {
  const m = view.matrix;
  if (!m) {
    container.replaceChildren(el("p", "hint first", "La matriz se muestra para grafos de hasta 40 vértices."));
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
    el("p", "hint first", "A[i][j] = 1 si las tareas i y j están en conflicto. Ocupa O(V²); los algoritmos recorren la lista de adyacencia, O(V + E)."),
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

export function renderLegend(container, view) {
  const items = view.batches.slice(0, LEGEND_MAX_BATCHES).map((b) => {
    const span = el("span");
    span.append(swatch(b.index), document.createTextNode(`Lote ${b.index}`));
    return span;
  });
  if (view.batches.length > LEGEND_MAX_BATCHES) items.push(el("span", "", `… ${view.batches.length} lotes`));
  const shared = el("span");
  shared.append(el("span", "ln"), document.createTextNode("Comparten recurso"));
  const declared = el("span");
  declared.append(el("span", "ln dashed"), document.createTextNode("Conflicto declarado"));
  items.push(shared, declared);
  container.replaceChildren(...items);
}

/** Explicación del paso `k` (0..n) del algoritmo. */
export function stepText(view, k) {
  const n = view.steps.length;
  if (k === 0) return "Paso 0: ninguna tarea tiene lote. Presione ▶ para ver al algoritmo trabajar.";
  if (k === n) {
    return `Coloración completa: ${view.metrics.colors} lotes. Ninguna arista une dos tareas del mismo lote. `
      + "Toque un nodo o una arista para ver el detalle.";
  }
  const s = view.steps[k - 1];
  const degree = view.tasks.find((t) => t.id === s.task)?.degree ?? 0;
  if (view.algorithm === "dsatur") {
    return `Paso ${k}/${n}: «${s.task}» → lote ${s.batch}. DSatur elige la tarea con mayor saturación `
      + `(${s.saturation} lote(s) distinto(s) entre sus vecinos ya asignados; empate → mayor grado, aquí ${degree}) `
      + "y le da el menor lote libre.";
  }
  return `Paso ${k}/${n}: «${s.task}» → lote ${s.batch}. Welsh-Powell recorre las tareas por grado decreciente `
    + `(grado ${degree}) y llena el lote ${s.batch} con toda tarea que no choque con otra ya puesta en él.`;
}
