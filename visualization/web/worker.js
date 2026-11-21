// Web Worker: ejecuta graph_core (Python) con Pyodide / WebAssembly fuera del hilo de la interfaz.
//
// Protocolo de mensajes (main <-> worker):
//   main -> worker  {id, type: "init"}              -> {id, ok, meta, version}
//   main -> worker  {id, type: "analyze", request}  -> {id, ok, result}
//   worker -> main  {type: "status", text}          (progreso de carga)

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE_INDEX = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const APP_DIR = "/home/pyodide/app";

let pyodide = null;
let handle = null;

const status = (text) => self.postMessage({ type: "status", text });

async function init() {
  status("Descargando Python (Pyodide)…");
  pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX });
  status("Cargando graph_core…");
  const manifest = await (await fetch("py/manifest.json", { cache: "no-store" })).json();
  const bundle = await fetch(`py/bundle.zip?v=${manifest.version}`);
  if (!bundle.ok) throw new Error(`No se pudo descargar el código Python (${bundle.status})`);
  pyodide.unpackArchive(await bundle.arrayBuffer(), "zip", { extractDir: APP_DIR });
  pyodide.runPython(`
import sys
sys.path.insert(0, "${APP_DIR}")
from visualization.web_api import handle, metadata
`);
  handle = pyodide.globals.get("handle");
  return { meta: JSON.parse(pyodide.globals.get("metadata")()), version: manifest.version };
}

self.onmessage = async (event) => {
  const { id, type, request } = event.data;
  try {
    if (type === "init") {
      self.postMessage({ id, ok: true, ...(await init()) });
    } else if (type === "analyze") {
      self.postMessage({ id, ok: true, result: JSON.parse(handle(JSON.stringify(request))) });
    } else {
      throw new Error(`Mensaje desconocido: ${type}`);
    }
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message ? err.message : err) });
  }
};
