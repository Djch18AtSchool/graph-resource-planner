// Controlador de la interfaz: lee el formulario, habla con el Web Worker (Python) y pinta resultados.
import { FORCE_MAX_NODES, GraphView } from "./graph-view.js";
import { batchText, el, renderMatrix, renderPlan, renderResources, renderTimes, renderVerdict, stepText } from "./panels.js";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const THEME_STORAGE = "grp.theme";
const PLAY_TOTAL_MS = 9000;                 // la animación completa dura ~9 s
const PLAY_MIN_MS = 25;
const PLAY_MAX_MS = 750;
const ERROR_LINE = /línea (\d+)/;

const state = {
  layout: "force", algorithm: "dsatur", view: null, meta: null, busy: false, timer: null, lastRequest: null,
};

// localStorage puede no existir (modo privado, iframes): toda lectura/escritura va protegida.
const store = {
  get(key) { try { return window.localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { window.localStorage.setItem(key, value); } catch { /* no disponible */ } },
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
  pill.className = `status status-${kind}`;
}

function alertBox(text, kind) {
  $("#alerts").append(el("div", `alert alert-${kind}`, text));
}

function selectTab(groupAttr, value, paneAttr) {
  $$(`[${groupAttr}]`).forEach((b) => b.setAttribute("aria-selected", String(b.getAttribute(groupAttr) === value)));
  if (paneAttr) $$(`[${paneAttr}]`).forEach((p) => { p.hidden = p.getAttribute(paneAttr) !== value; });
}

function checkRadio(groupAttr, value) {
  $$(`[${groupAttr}]`).forEach((b) => b.setAttribute("aria-checked", String(b.getAttribute(groupAttr) === value)));
}

const narrate = (text) => { $("#inspector").textContent = text; };
const graph = new GraphView($("#cy"), narrate);

// ------------------------------------------------------------------------------- editor
function syncGutter(errorLine = null) {
  const lines = $("#problem").value.split("\n").length;
  const gutter = $("#gutter");
  if (gutter.childElementCount !== lines || errorLine !== null || gutter.querySelector(".err")) {
    gutter.replaceChildren(...Array.from({ length: lines }, (_, i) => el("span", i + 1 === errorLine ? "err" : "", String(i + 1))));
  }
  gutter.scrollTop = $("#problem").scrollTop;
}

// ----------------------------------------------------------------------------- análisis
function setBusy(busy) {
  state.busy = busy;
  ["#run", "#run-random", "#example"].forEach((sel) => { $(sel).disabled = busy; });
  $$("[data-n]").forEach((b) => { b.disabled = busy; });
  $("#run").textContent = busy ? "Calculando…" : "Asignar lotes";
}

async function analyze(request) {
  if (state.busy || !state.meta) return;            // Python cargando o un análisis en curso
  $("#alerts").replaceChildren();
  state.lastRequest = request;
  setBusy(true);
  setStatus("Calculando…", "loading");
  try {
    const { result } = await call("analyze", { request: { ...request, algorithm: state.algorithm } });
    if (result.ok) {
      syncGutter();
      await showView(result.view);
    } else {
      alertBox(result.error, "error");
      const line = ERROR_LINE.exec(result.error);
      if (request.mode === "text" && line) syncGutter(Number(line[1]));
    }
    setStatus("Listo", "ready");
  } catch (err) {
    alertBox(err.message, "error");
    setStatus("Error", "error");
  } finally {
    setBusy(false);
  }
}

function analyzeText() {
  if (state.busy || !state.meta) return;
  const text = $("#problem").value;
  if (!text.trim()) { alertBox("Escriba al menos una tarea, una por línea.", "error"); return; }
  if (text.length > state.meta.limits.max_text_chars) {
    alertBox(`El texto excede ${state.meta.limits.max_text_chars} caracteres.`, "error");
    return;
  }
  analyze({ mode: "text", text });
}

function analyzeRandom() {
  if (state.busy || !state.meta) return;
  const n = Number($("#rand-n").value);
  const p = Number($("#rand-p").value);
  const seed = Number($("#rand-seed").value || 0);
  if (!Number.isInteger(n) || n < 1 || n > state.meta.limits.max_tasks) {
    alertBox(`n debe ser un entero entre 1 y ${state.meta.limits.max_tasks}.`, "error");
    return;
  }
  if (!(p >= 0 && p <= 1)) { alertBox("p debe estar entre 0 y 1.", "error"); return; }
  analyze({ mode: "random", n, p, seed: Number.isInteger(seed) && seed >= 0 ? seed : 0 });
}

// -------------------------------------------------------------------------------- resultados
function focusBatch(batch) {
  graph.setBatchFocus(batch);
  narrate(batch === null ? stepText(state.view, Number($("#step").value)) : batchText(state.view, batch));
}

async function showView(view) {
  stopPlaying();
  state.view = view;
  $("#loading").hidden = true;
  $("#output").hidden = false;
  renderVerdict(view, focusBatch);
  renderPlan($("#plan"), view);
  renderResources($("#resources"), view);
  renderMatrix($("#matrix"), view);
  renderTimes($("#times"), view);
  const tooBigForForce = view.tasks.length > FORCE_MAX_NODES;
  const forceButton = $("[data-layout=force]");
  forceButton.disabled = tooBigForForce;
  forceButton.title = tooBigForForce ? `Disponible hasta ${FORCE_MAX_NODES} tareas` : "";
  if (tooBigForForce) setLayout("batches", false);
  const slider = $("#step");
  slider.max = String(view.steps.length);
  slider.value = slider.max;
  $("#clique").checked = false;
  $("#clique").disabled = view.clique.length < 2;
  graph.clique = false;
  graph.focusBatch = null;
  await drawGraph();
}

async function drawGraph() {
  const view = state.view;
  $("#no-draw").hidden = view.drawable;
  $("#cy").hidden = !view.drawable;
  $("#stepper").hidden = !view.drawable;
  if (!view.drawable) { graph.clear(); narrate(""); return; }
  await graph.render(view, state.layout);
  showStep(Number($("#step").value));
}

function showStep(k) {
  graph.setStep(k);
  $("#step-label").textContent = `Paso ${k}/${state.view.steps.length}`;
  narrate(stepText(state.view, k));
}

function setLayout(layout, redraw = true) {
  state.layout = layout;
  checkRadio("data-layout", layout);
  if (redraw && state.view) drawGraph();
}

function setAlgorithm(algorithm) {
  if (state.busy || algorithm === state.algorithm) return;
  state.algorithm = algorithm;
  checkRadio("data-algorithm", algorithm);
  if (state.lastRequest) analyze(state.lastRequest);   // recalcula lo que está en pantalla
}

// --------------------------------------------------------------------------- paso a paso
function stopPlaying() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  const play = $("#step-play");
  play.classList.remove("playing");
  play.setAttribute("aria-label", "Reproducir el algoritmo");
}

function togglePlay() {
  if (state.timer) { stopPlaying(); return; }
  const slider = $("#step");
  const n = Number(slider.max);
  if (Number(slider.value) >= n) slider.value = "0";
  const delay = Math.min(PLAY_MAX_MS, Math.max(PLAY_MIN_MS, PLAY_TOTAL_MS / Math.max(n, 1)));
  const play = $("#step-play");
  play.classList.add("playing");
  play.setAttribute("aria-label", "Pausar");
  showStep(Number(slider.value));
  state.timer = setInterval(() => {
    const k = Number(slider.value) + 1;
    slider.value = String(k);
    showStep(k);
    if (k >= n) stopPlaying();
  }, delay);
}

// ------------------------------------------------------------------------------- eventos
function bindEvents() {
  $$("[data-layout]").forEach((b) => b.addEventListener("click", () => { if (!b.disabled) setLayout(b.dataset.layout); }));
  $$("[data-algorithm]").forEach((b) => b.addEventListener("click", () => setAlgorithm(b.dataset.algorithm)));
  $$("[data-tab]").forEach((b) => b.addEventListener("click", () => selectTab("data-tab", b.dataset.tab, "data-tabpane")));
  $$("[data-n]").forEach((b) => b.addEventListener("click", () => {
    $("#rand-n").value = b.dataset.n;
    $("#rand-p").value = b.dataset.p;
    analyzeRandom();
  }));
  $("#example").addEventListener("change", () => {
    const ex = state.meta.examples.find((e) => e.key === $("#example").value);
    if (ex) { $("#problem").value = ex.text; $("#problem").scrollTop = 0; syncGutter(); analyzeText(); }
  });
  $("#run").addEventListener("click", analyzeText);
  $("#run-random").addEventListener("click", analyzeRandom);
  $("#problem").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) analyzeText(); });
  $("#problem").addEventListener("input", () => syncGutter());
  $("#problem").addEventListener("scroll", () => { $("#gutter").scrollTop = $("#problem").scrollTop; });
  $("#step").addEventListener("input", (e) => { stopPlaying(); showStep(Number(e.target.value)); });
  $("#step-first").addEventListener("click", () => { stopPlaying(); $("#step").value = "0"; showStep(0); });
  $("#step-play").addEventListener("click", togglePlay);
  $("#clique").addEventListener("change", (e) => graph.setClique(e.target.checked));
  $("#fit").addEventListener("click", () => graph.fit());
  $("#png").addEventListener("click", downloadPng);
  $("#theme-toggle").addEventListener("click", toggleTheme);
}

function downloadPng() {
  const uri = graph.png();
  if (!uri) return;
  const a = document.createElement("a");
  a.href = uri;
  a.download = `grafo-${state.layout}.png`;
  a.click();
}

function toggleTheme() {
  const root = document.documentElement;
  const current = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  store.set(THEME_STORAGE, next);
  if (state.view?.drawable) drawGraph();           // los colores del grafo salen de las variables CSS
}

// ---------------------------------------------------------------------------------- inicio
async function main() {
  const theme = store.get(THEME_STORAGE);
  if (theme) document.documentElement.dataset.theme = theme;
  bindEvents();
  syncGutter();
  try {
    const { meta, version } = await call("init");
    state.meta = meta;
    $("#example").replaceChildren(...meta.examples.map((e) => {
      const o = el("option", "", e.title);
      o.value = e.key;
      return o;
    }));
    $("#problem").value = meta.examples[0]?.text || "";
    syncGutter();
    $("#build-version").textContent = `código Python ${version}`;
    setStatus("Python listo", "ready");
    setBusy(false);
    analyzeText();
  } catch (err) {
    setStatus("No se pudo iniciar Python", "error");
    $("#loading").hidden = true;
    alertBox(`No se pudo cargar Pyodide: ${err.message}. Revise la conexión y recargue la página.`, "error");
  }
}

main();
