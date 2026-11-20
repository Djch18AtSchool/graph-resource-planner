// Controlador de la interfaz: lee el formulario, habla con el Web Worker (Python) y pinta resultados.
import { GraphView } from "./graph-view.js";
import { el, renderLegend, renderMatrix, renderMetrics, renderPlan, renderReport, renderTimes } from "./panels.js";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const KEY_STORAGE = "grp.anthropicKey";
const THEME_STORAGE = "grp.theme";

const state = { mode: "text", layout: "planar", view: null, meta: null };

// --------------------------------------------------------------------------- almacenamiento
// sessionStorage puede no existir (modo privado, iframes): toda lectura/escritura va protegida.
const store = {
  get(area, key) { try { return window[area].getItem(key); } catch { return null; } },
  set(area, key, value) { try { window[area].setItem(key, value); } catch { /* no disponible */ } },
  del(area, key) { try { window[area].removeItem(key); } catch { /* no disponible */ } },
};

// ------------------------------------------------------------------------------- worker
const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
const pending = new Map();
let nextId = 1;

worker.onmessage = (event) => {
  const msg = event.data;
  if (msg.type === "status") { setStatus(msg.text, "loading"); return; }
  const entry = pending.get(msg.id);
  if (!entry) return;
  pending.delete(msg.id);
  if (msg.ok) entry.resolve(msg); else entry.reject(new Error(msg.error));
};
worker.onerror = (event) => setStatus(`Error del worker: ${event.message || "desconocido"}`, "error");

function call(type, payload = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, type, ...payload });
  });
}

// ---------------------------------------------------------------------------------- UI util
function setStatus(text, kind) {
  const pill = $("#status");
  pill.textContent = text;
  pill.className = `pill pill-${kind}`;
}

function alertBox(text, kind) {
  $("#alerts").append(el("div", `alert alert-${kind}`, text));
}

function selectTab(groupAttr, value, paneAttr) {
  $$(`[${groupAttr}]`).forEach((b) => b.setAttribute("aria-selected", String(b.getAttribute(groupAttr) === value)));
  if (paneAttr) $$(`[${paneAttr}]`).forEach((p) => { p.hidden = p.getAttribute(paneAttr) !== value; });
}

const graph = new GraphView($("#cy"), (text) => { $("#inspector").textContent = text; });

// ----------------------------------------------------------------------------- formulario
function readRequest() {
  const provider = $("#provider").value;
  const request = {
    mode: state.mode, provider, algorithm: $("#algorithm").value, with_report: $("#with-report").checked,
    text: $("#text").value, example: $("#example").value, spec_json: $("#spec-json").value,
  };
  const secrets = {};
  if (provider === "anthropic") {
    Object.assign(request, { model: $("#model").value.trim(), effort: $("#effort").value });
    secrets.apiKey = $("#api-key").value.trim();
  } else if (provider === "ollama") {
    request.model = $("#ollama-model").value.trim();
    secrets.ollamaHost = $("#ollama-host").value.trim();
  }
  return { request, secrets };
}

function validate({ request, secrets }) {
  if (request.mode === "text" && !request.text.trim()) return "Escriba un requerimiento.";
  if (request.mode === "text" && request.text.length > state.meta.max_input_chars) {
    return `El requerimiento excede ${state.meta.max_input_chars} caracteres.`;
  }
  if (request.mode === "json" && !request.spec_json.trim()) return "Pegue un GraphSpec en JSON.";
  if (request.provider === "anthropic" && !secrets.apiKey) return "Ingrese su API key de Anthropic (o use el modo offline).";
  return null;
}

async function analyze() {
  if ($("#run").disabled || !state.meta) return;   // Python cargando o un análisis en curso
  $("#alerts").replaceChildren();
  const input = readRequest();
  const problem = validate(input);
  if (problem) { alertBox(problem, "error"); return; }
  if (input.request.provider === "anthropic" && $("#remember-key").checked) {
    store.set("sessionStorage", KEY_STORAGE, input.secrets.apiKey);
  }
  const button = $("#run");
  button.disabled = true;
  button.textContent = input.request.provider === "offline" ? "Analizando…" : "Consultando al LLM…";
  setStatus("Analizando…", "loading");
  try {
    const { result } = await call("analyze", input);
    if (!result.ok) { alertBox(result.error, "error"); setStatus("Listo", "ready"); return; }
    result.view.warnings.forEach((w) => alertBox(w, "warn"));
    showView(result.view);
    setStatus("Listo", "ready");
  } catch (err) {
    alertBox(err.message, "error");
    setStatus("Error", "error");
  } finally {
    button.disabled = false;
    button.textContent = "Analizar";
  }
}

// -------------------------------------------------------------------------------- resultados
function labeler(view) {
  const map = new Map(view.spec.nodes.map((n) => [n.id, n.label]));
  return (id) => map.get(id) || id;
}

function drawGraph() {
  const view = state.view;
  const drawing = view[state.layout];
  graph.render(drawing, labeler(view));
  graph.setKuratowski($("#kura").checked);
  const badge = $("#crossings");
  badge.textContent = `${drawing.crossings} cruce(s) en el dibujo`;
  badge.className = `badge ${drawing.crossings === 0 ? "good" : "bad"}`;
  renderLegend($("#legend"), view, state.layout);
  $("#inspector").textContent = state.layout === "planar"
    ? "Dibujo plano: embedding de Tutte + refinamiento por fuerzas que nunca crea cruces."
    : "Layout de fuerzas (networkx.spring_layout) sobre el grafo original: puede cruzar aristas.";
}

function showView(view) {
  state.view = view;
  $("#empty").hidden = true;
  $("#output").hidden = false;
  const p = view.facts.planarity;
  $("#kura-wrap").hidden = p.is_planar;
  $("#kura-kind").textContent = p.witness ? `${p.witness} (Kuratowski)` : "Kuratowski";
  renderMetrics($("#metrics"), view);
  renderPlan($("#plan"), view);
  renderReport($("#report"), view);
  renderMatrix($("#matrix"), view);
  renderTimes($("#times"), view);
  $("#json").textContent = JSON.stringify(view.spec, null, 2);
  $("#json-meta").textContent = view.attempts
    ? `Generado por ${view.provider} en ${view.attempts} intento(s) (validado con Pydantic).`
    : "Especificación cargada directamente (sin LLM).";
  drawGraph();
}

// ------------------------------------------------------------------------------- eventos
function bindEvents() {
  $$("[data-mode]").forEach((b) => b.addEventListener("click", () => {
    state.mode = b.dataset.mode;
    selectTab("data-mode", state.mode, "data-pane");
  }));
  $$("[data-layout]").forEach((b) => b.addEventListener("click", () => {
    state.layout = b.dataset.layout;
    selectTab("data-layout", state.layout);
    if (state.view) drawGraph();
  }));
  $$("[data-tab]").forEach((b) => b.addEventListener("click", () => selectTab("data-tab", b.dataset.tab, "data-tabpane")));
  $$(".chip").forEach((c) => c.addEventListener("click", () => { $("#text").value = c.dataset.prompt; }));
  $("#provider").addEventListener("change", syncProvider);
  $("#remember-key").addEventListener("change", (e) => { if (!e.target.checked) store.del("sessionStorage", KEY_STORAGE); });
  $("#run").addEventListener("click", analyze);
  $("#text").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) analyze(); });
  $("#kura").addEventListener("change", (e) => graph.setKuratowski(e.target.checked));
  $("#fit").addEventListener("click", () => graph.fit());
  $("#png").addEventListener("click", downloadPng);
  $("#copy-json").addEventListener("click", copyJson);
  $("#edit-json").addEventListener("click", () => {
    $("#spec-json").value = $("#json").textContent;
    state.mode = "json";
    selectTab("data-mode", "json", "data-pane");
    $("#spec-json").focus();
  });
  $("#theme-toggle").addEventListener("click", toggleTheme);
}

function syncProvider() {
  const provider = $("#provider").value;
  $$("[data-provider]").forEach((p) => { p.hidden = p.dataset.provider !== provider; });
  $("#offline-hint").hidden = provider !== "offline";
}

function downloadPng() {
  const uri = graph.png();
  if (!uri) return;
  const a = document.createElement("a");
  a.href = uri;
  a.download = `grafo-${state.layout}.png`;
  a.click();
}

async function copyJson() {
  try {
    await navigator.clipboard.writeText($("#json").textContent);
    $("#copy-json").textContent = "Copiado";
  } catch {
    $("#copy-json").textContent = "No se pudo copiar";
  }
  setTimeout(() => { $("#copy-json").textContent = "Copiar"; }, 1500);
}

function toggleTheme() {
  const root = document.documentElement;
  const current = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  store.set("localStorage", THEME_STORAGE, next);
  if (state.view) drawGraph();                     // los colores del grafo salen de las variables CSS
}

// ---------------------------------------------------------------------------------- inicio
async function main() {
  const theme = store.get("localStorage", THEME_STORAGE);
  if (theme) document.documentElement.dataset.theme = theme;
  const savedKey = store.get("sessionStorage", KEY_STORAGE);
  if (savedKey) { $("#api-key").value = savedKey; $("#remember-key").checked = true; }
  $("#ollama-cmd").textContent = `OLLAMA_ORIGINS=${location.origin} ollama serve`;
  bindEvents();
  syncProvider();
  try {
    const { meta, version } = await call("init");
    state.meta = meta;
    $("#example").replaceChildren(...meta.examples.map((e) => {
      const o = el("option", "", e.title);
      o.value = e.key;
      return o;
    }));
    $("#spec-json").value = JSON.stringify(meta.example_specs.pipeline, null, 2);
    $("#build-version").textContent = `código Python ${version}`;
    setStatus("Python listo", "ready");
    $("#run").disabled = false;
  } catch (err) {
    setStatus("No se pudo iniciar Python", "error");
    alertBox(`No se pudo cargar Pyodide: ${err.message}. Revise la conexión y recargue la página.`, "error");
  }
}

main();
