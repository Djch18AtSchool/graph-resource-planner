// Paneles de resultados. Todo texto del usuario se inserta con textContent (nunca innerHTML).
import { batchColor, textOnBatch } from "./graph-view.js";

const GANTT_MAX_TASKS = 80;
const CHIPS_PER_BATCH = 40;
const CLAIM_MAX_NAMES = 4;
const STRIP_DENSE_BATCHES = 40;       // con más lotes la franja quita separaciones y rótulos
const STRIP_LABEL_MIN_SHARE = 0.07;   // un segmento más angosto no lleva texto
const AXIS_LABEL_MIN_SHARE = 0.06;
const AXIS_MAX_BOUNDARIES = 10;
const GANTT_TICKS = 10;
const NAMES = { dsatur: "DSatur", welsh_powell: "Welsh-Powell" };
const STAGES = {
  conflict_graph: "Construir el grafo de conflictos", coloring: "Coloración con el algoritmo elegido",
  alternative: "Coloración con el otro algoritmo", bounds: "Cotas de χ(G) y búsqueda exacta",
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

function dot(batch) {
  const d = el("span", "dot");
  d.style.setProperty("--c", batchColor(batch));
  return d;
}

function listNames(names) {
  const shown = names.slice(0, CLAIM_MAX_NAMES).map((n) => `«${n}»`);
  const rest = names.length - shown.length;
  if (rest > 0) return `${shown.join(", ")} y ${rest} más`;
  return shown.length > 1 ? `${shown.slice(0, -1).join(", ")} y ${shown.at(-1)}` : shown.join("");
}

// ------------------------------------------------------------------------------ veredicto
function chiFormula(m) {
  const p = el("span");
  const part = (text, cls = "") => p.append(el("span", cls, text));
  if (m.exact !== null) {
    part("χ(G)"); part(" = ", "rel"); part(String(m.exact), "rel");
  } else {
    part(String(m.lower), "rel"); part(" ≤ ", "rel"); part("χ(G)"); part(" ≤ ", "rel"); part(String(m.upper), "rel");
  }
  return p;
}

function claimText(view) {
  const m = view.metrics;
  const alg = algorithmName(view.algorithm);
  const other = algorithmName(view.alternative.algorithm);
  const k = m.colors;
  if (m.conflicts === 0) return `No hay conflictos: las ${m.tasks} tareas pueden correr juntas en un solo lote.`;
  if (m.exact !== null && k > m.exact) {
    return `${alg} usa ${k} lotes, pero bastan ${m.exact}: ${other} encuentra el mínimo en este caso.`;
  }
  if (m.exact_method === "clique") {
    return `${alg} usa ${k} lotes y no se puede hacer mejor: ${listNames(view.clique)} chocan todas entre sí, `
      + `así que cada una necesita su propio lote.`;
  }
  if (m.exact_method === "branch_and_bound") {
    return `${alg} usa ${k} lotes. Una búsqueda exhaustiva (branch & bound) confirma que es el mínimo posible.`;
  }
  return `${alg} usa ${k} lotes. El mínimo está entre ${m.lower} y ${m.upper}; calcularlo exacto en un grafo `
    + "de este tamaño es NP-difícil, así que se acota con una clique y la mejor heurística.";
}

function renderStrip(strip, axis, view, onFocus) {
  const total = view.metrics.makespan || 1;
  const dense = view.batches.length > STRIP_DENSE_BATCHES;
  strip.style.gap = dense ? "1px" : "";
  const lots = view.batches.map((b) => {
    const share = b.duration / total;
    const lot = el("button", `lot${share < STRIP_LABEL_MIN_SHARE || dense ? " tight" : ""}`);
    lot.type = "button";
    lot.style.flex = `${b.duration} 1 0`;
    lot.style.minWidth = dense ? "0" : "";
    lot.style.setProperty("--c", batchColor(b.index));
    lot.style.setProperty("--on", textOnBatch(b.index));
    lot.dataset.batch = String(b.index);
    lot.setAttribute("aria-label", `Lote ${b.index}: ${b.tasks.length} tareas, de t = ${fmt(b.start)} a t = ${fmt(b.start + b.duration)}`);
    lot.append(el("b", "", `Lote ${b.index}`), el("small", "", `${b.tasks.length} ${b.tasks.length === 1 ? "tarea" : "tareas"}`));
    return lot;
  });
  strip.replaceChildren(...lots);

  let pinned = null;
  const show = (batch) => {
    strip.classList.toggle("has-focus", batch !== null);
    lots.forEach((l) => l.classList.toggle("on", Number(l.dataset.batch) === batch));
    onFocus(batch);
  };
  lots.forEach((lot) => {
    const batch = Number(lot.dataset.batch);
    lot.addEventListener("mouseenter", () => show(batch));
    lot.addEventListener("focus", () => show(batch));
    lot.addEventListener("mouseleave", () => show(pinned));
    lot.addEventListener("blur", () => show(pinned));
    lot.addEventListener("click", () => { pinned = pinned === batch ? null : batch; show(pinned); });
  });

  const marks = [el("span", "", "0")];
  if (view.batches.length <= AXIS_MAX_BOUNDARIES) {
    view.batches.slice(1).forEach((b, i) => {
      const prev = view.batches[i];
      if (prev.duration / total < AXIS_LABEL_MIN_SHARE) return;
      const mark = el("span", "", fmt(b.start));
      mark.style.left = `${(b.start / total) * 100}%`;
      marks.push(mark);
    });
  }
  const end = el("span", "", `t = ${fmt(total)}`);
  end.style.left = "100%";
  marks.push(end);
  axis.replaceChildren(...marks);
}

function fact(key, label, value, unit = "") {
  const box = el("div", "fact");
  box.dataset.metric = key;
  const dd = el("dd");
  dd.append(el("span", "v", String(value)));
  if (unit) dd.append(el("span", "unit", unit));
  box.append(el("dt", "", label), dd);
  return box;
}

/** Encabezado de resultados: χ(G), afirmación demostrada, franja de lotes y datos. */
export function renderVerdict(view, onFocus) {
  const m = view.metrics;
  document.querySelector("#chi").replaceChildren(chiFormula(m));
  document.querySelector("#claim").textContent = claimText(view);
  renderStrip(document.querySelector("#strip"), document.querySelector("#strip-axis"), view, onFocus);
  document.querySelector("#facts").replaceChildren(
    fact("colors", `Lotes con ${algorithmName(view.algorithm)}`, m.colors),
    fact("alternative", `Lotes con ${algorithmName(view.alternative.algorithm)}`, view.alternative.colors),
    fact("tasks", "Tareas", m.tasks),
    fact("conflicts", "Conflictos", m.conflicts),
    fact("degree", "Grado máximo Δ", m.max_degree),
    fact("workers", "Ejecutores en paralelo", m.workers),
    fact("makespan", "Tiempo total", fmt(m.makespan), `de ${fmt(m.sequential)} en secuencia`),
  );
}

/** Texto de la narración al enfocar un lote en la franja. */
export function batchText(view, batch) {
  const b = view.batches.find((x) => x.index === batch);
  if (!b) return "";
  const names = b.tasks.length > 12 ? `${b.tasks.slice(0, 12).join(", ")} y ${b.tasks.length - 12} más` : b.tasks.join(", ");
  return `Lote ${b.index}, de t = ${fmt(b.start)} a t = ${fmt(b.start + b.duration)}: ${names}. `
    + "Ninguna de estas tareas comparte un recurso con otra del mismo lote.";
}

// ------------------------------------------------------------------------------ cronograma
function gantt(view) {
  const total = view.metrics.makespan || 1;
  const byId = new Map(view.tasks.map((t) => [t.id, t]));
  const chart = el("div", "gantt");
  chart.style.setProperty("--tick", `${100 / GANTT_TICKS}%`);
  view.batches.forEach((b) => {
    const head = el("div", "gantt-group");
    head.append(dot(b.index), document.createTextNode(`Lote ${b.index} `),
      el("small", "", `de t = ${fmt(b.start)} a t = ${fmt(b.start + b.duration)}`));
    chart.append(head);
    b.tasks.forEach((id) => {
      const task = byId.get(id);
      const track = el("div", "gantt-track");
      const bar = el("div", "gantt-bar");
      bar.style.left = `${(b.start / total) * 100}%`;
      bar.style.width = `${Math.max((task.duration / total) * 100, 0.8)}%`;
      bar.style.setProperty("--c", batchColor(b.index));
      bar.title = `${id}: dura ${fmt(task.duration)}`;
      track.append(bar);
      chart.append(el("span", "gantt-name", id), track);
    });
  });
  const axis = el("div", "gantt-axis");
  for (let i = 0; i <= 4; i += 1) axis.append(el("span", "", fmt((total * i) / 4)));
  chart.append(axis);
  return chart;
}

function batchList(view) {
  const list = el("div", "batches");
  view.batches.forEach((b) => {
    const row = el("div", "batch-row");
    const head = el("header");
    const title = el("span", "", `Lote ${b.index}`);
    title.append(el("small", "", `${b.tasks.length} en paralelo`));
    head.append(dot(b.index), title);
    const chips = el("div", "chips");
    b.tasks.slice(0, CHIPS_PER_BATCH).forEach((t) => chips.append(el("span", "chip", t)));
    if (b.tasks.length > CHIPS_PER_BATCH) chips.append(el("span", "chip more", `y ${b.tasks.length - CHIPS_PER_BATCH} más`));
    row.append(head, chips);
    list.append(row);
  });
  return list;
}

export function renderPlan(container, view) {
  const intro = el("p", "lede",
    "Los lotes corren uno detrás de otro; dentro de un lote todas las tareas arrancan a la vez. "
    + "Cada lote termina cuando acaba su tarea más larga.");
  const body = view.tasks.length <= GANTT_MAX_TASKS ? gantt(view) : batchList(view);
  container.replaceChildren(intro, body);
}

// --------------------------------------------------------------------------------- recursos
export function renderResources(container, view) {
  if (!view.resources.length) {
    container.replaceChildren(el("p", "lede", "Este problema solo tiene conflictos declarados entre tareas, sin recursos."));
    return;
  }
  const batchOf = new Map(view.tasks.map((t) => [t.id, t.batch]));
  const table = el("table", "resources-table");
  const head = el("tr");
  head.append(el("th", "", "Recurso"), el("th", "", "Tareas que lo usan (con el color de su lote)"), el("th", "", "Clique"));
  table.append(head);
  view.resources.forEach((r) => {
    const tr = el("tr");
    const chips = el("div", "chips");
    r.tasks.forEach((t) => {
      const chip = el("span", "chip");
      chip.append(dot(batchOf.get(t)), document.createTextNode(t));
      chips.append(chip);
    });
    const cell = el("td");
    cell.append(chips);
    tr.append(el("td", "", r.name), cell, el("td", "k", `K${r.tasks.length}`));
    table.append(tr);
  });
  const wrap = el("div", "table-wrap");
  wrap.append(table);
  container.replaceChildren(
    el("p", "lede", "Las tareas que comparten un recurso chocan todas entre sí: forman una clique, y por eso cada una "
      + `lleva un color distinto. El recurso más disputado lo usan ${view.metrics.max_resource_usage} tareas, así que `
      + `ningún plan puede tener menos de ${view.metrics.max_resource_usage} lotes.`),
    wrap,
  );
}

// ---------------------------------------------------------------------------------- matriz
export function renderMatrix(container, view) {
  const m = view.matrix;
  if (!m) {
    container.replaceChildren(el("p", "lede", "La matriz se muestra para grafos de hasta 40 tareas; más grande no se puede leer en pantalla."));
    return;
  }
  const batchOf = new Map(view.tasks.map((t) => [t.id, t.batch]));
  const table = el("table", "matrix");
  const head = el("tr");
  head.append(el("th", "row", ""));
  m.labels.forEach((l, j) => { const th = el("th", "", String(j + 1)); th.title = l; head.append(th); });
  head.append(el("th", "", "grado"));
  table.append(head);
  m.rows.forEach((row, i) => {
    const tr = el("tr");
    const th = el("th", "row");
    th.append(dot(batchOf.get(m.labels[i])), document.createTextNode(`${i + 1}. ${m.labels[i]}`));
    tr.append(th);
    row.forEach((x) => tr.append(el("td", x ? "one" : "", String(x))));
    tr.append(el("td", "", String(m.degrees[i])));
    table.append(tr);
  });
  const wrap = el("div", "table-wrap");
  wrap.append(table);
  container.replaceChildren(
    el("p", "lede", "A[i][j] = 1 cuando las tareas i y j están en conflicto. La matriz ocupa O(V²) memoria; "
      + "los algoritmos recorren la lista de adyacencia, que ocupa O(V + E)."),
    wrap,
  );
}

export function renderTimes(container, view) {
  const entries = Object.entries(view.timings_ms);
  const max = Math.max(...entries.map(([, v]) => v), 0.001);
  const grid = el("div", "timebars");
  entries.forEach(([k, v]) => {
    const bar = el("div", "bar");
    bar.style.width = `${(v / max) * 100}%`;
    const track = el("div");
    track.append(bar);
    grid.append(el("span", "", STAGES[k] || k), track, el("span", "ms", `${v.toFixed(2)} ms`));
  });
  container.replaceChildren(el("p", "lede", "Medido dentro de su navegador: el mismo Python del repositorio, compilado a WebAssembly."), grid);
}

/** Explicación del paso `k` (0..n) del algoritmo. */
export function stepText(view, k) {
  const n = view.steps.length;
  if (k === 0) return "Ninguna tarea tiene lote todavía. Presione reproducir para ver al algoritmo decidir, una tarea a la vez.";
  if (k === n) {
    return `Listo: ${view.metrics.colors} lotes y ninguna arista une dos tareas del mismo color. `
      + "Toque una tarea o una arista para ver por qué está ahí.";
  }
  const s = view.steps[k - 1];
  const degree = view.tasks.find((t) => t.id === s.task)?.degree ?? 0;
  if (view.algorithm === "dsatur") {
    return `«${s.task}» va al lote ${s.batch}. DSatur elige la tarea más acorralada: sus vecinos ya ocupan `
      + `${s.saturation} lote(s) distinto(s) (si hay empate, gana la de más conflictos; esta tiene ${degree}). `
      + "Le da el primer lote libre.";
  }
  return `«${s.task}» va al lote ${s.batch}. Welsh-Powell recorre las tareas de más a menos conflictos (esta tiene `
    + `${degree}) y mete en el lote ${s.batch} toda tarea que no choque con las que ya están ahí.`;
}
