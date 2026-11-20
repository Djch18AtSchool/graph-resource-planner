// Web Worker: ejecuta el motor en Python (Pyodide / WebAssembly) fuera del hilo de la interfaz.
//
// Protocolo de mensajes (main <-> worker):
//   main -> worker  {id, type: "init"}                       -> {id, ok, meta}
//   main -> worker  {id, type: "analyze", request, secrets}  -> {id, ok, result}
//   worker -> main  {type: "status", text}                   (progreso de carga)
//
// La API key llega en `secrets` solo para la llamada en curso y nunca se entrega a Python:
// Python arma el cuerpo de la peticion y este puente solo la transporta (SDK oficial / fetch).

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE_INDEX = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const ANTHROPIC_SDK = "https://cdn.jsdelivr.net/npm/@anthropic-ai/sdk@1.6.0/+esm";
const PACKAGES = ["networkx", "pydantic", "numpy"];
const DEFAULT_OLLAMA_HOST = "http://localhost:11434";

let pyodide = null;
let anthropicModule = null;

const status = (text) => self.postMessage({ type: "status", text });

async function init() {
  status("Descargando Python (Pyodide)…");
  pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX });
  status("Instalando networkx, pydantic y numpy…");
  await pyodide.loadPackage(PACKAGES);
  status("Cargando graph_core y ai_agent…");
  const manifest = await (await fetch("py/manifest.json", { cache: "no-store" })).json();
  const bundle = await fetch(`py/bundle.zip?v=${manifest.version}`);
  if (!bundle.ok) throw new Error(`No se pudo descargar el código Python (${bundle.status})`);
  pyodide.unpackArchive(await bundle.arrayBuffer(), "zip", { extractDir: "/home/pyodide/app" });
  pyodide.runPython(`
import sys
sys.path.insert(0, "/home/pyodide/app")
from visualization.web_api import handle, metadata
`);
  return { meta: JSON.parse(pyodide.globals.get("metadata")()), version: manifest.version };
}

// ------------------------------------------------------------------ puente LLM (solo transporte)
function makeBridge(secrets) {
  return {
    async request(provider, payloadJson) {
      const payload = JSON.parse(payloadJson);
      if (provider === "anthropic") return JSON.stringify(await callAnthropic(payload, secrets));
      if (provider === "ollama") return JSON.stringify(await callOllama(payload, secrets));
      throw new Error(`Proveedor no soportado: ${provider}`);
    },
  };
}

async function callAnthropic(params, secrets) {
  if (!secrets.apiKey) throw new Error("Ingrese su API key de Anthropic");
  if (!anthropicModule) anthropicModule = await import(ANTHROPIC_SDK);
  const Anthropic = anthropicModule.default;
  const client = new Anthropic({ apiKey: secrets.apiKey, dangerouslyAllowBrowser: true, maxRetries: 2 });
  try {
    return await client.beta.messages.create(params);
  } catch (err) {
    if (err instanceof Anthropic.AuthenticationError) throw new Error("API key de Anthropic inválida");
    if (err instanceof Anthropic.RateLimitError) throw new Error("Límite de uso alcanzado; intente en unos segundos");
    if (err instanceof Anthropic.APIConnectionError) throw new Error("No se pudo conectar con la API de Anthropic");
    if (err instanceof Anthropic.APIError) throw new Error(`API de Anthropic (${err.status}): ${err.message}`);
    throw err;
  }
}

async function callOllama(payload, secrets) {
  const host = (secrets.ollamaHost || DEFAULT_OLLAMA_HOST).replace(/\/+$/, "");
  let res;
  try {
    res = await fetch(`${host}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(`No se pudo conectar con Ollama en ${host} (¿está corriendo y con OLLAMA_ORIGINS configurado?)`);
  }
  if (!res.ok) throw new Error(`Ollama respondió ${res.status}: ${await res.text()}`);
  return res.json();
}

// ---------------------------------------------------------------------------- despacho
async function analyze(request, secrets) {
  const handle = pyodide.globals.get("handle");
  try {
    return JSON.parse(await handle(JSON.stringify(request), makeBridge(secrets || {})));
  } finally {
    handle.destroy();
  }
}

self.onmessage = async (event) => {
  const { id, type, request, secrets } = event.data;
  try {
    if (type === "init") {
      self.postMessage({ id, ok: true, ...(await init()) });
    } else if (type === "analyze") {
      self.postMessage({ id, ok: true, result: await analyze(request, secrets) });
    } else {
      throw new Error(`Mensaje desconocido: ${type}`);
    }
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message ? err.message : err) });
  }
};
