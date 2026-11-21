// Web Worker: carga Pyodide (CPython en WebAssembly) y ejecuta el motor de graph_core fuera del hilo de la UI.
//
// Mensajes:  {id, type: "init", baseUrl}  -> {id, ok, meta}
//            {id, type: "analyze", request} -> {id, ok, result}
import type { PyodideAPI } from "pyodide";

const PYODIDE_VERSION = "314.0.8";
const PYODIDE_INDEX = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const APP_DIR = "/home/pyodide/app";

type Incoming = { id: number; type: "init"; baseUrl: string } | { id: number; type: "analyze"; request: unknown };
type PyCallable = (arg?: string) => string;

const scope = self as unknown as Worker;
let handle: PyCallable | null = null;

async function init(baseUrl: string): Promise<unknown> {
  const { loadPyodide } = (await import(/* @vite-ignore */ `${PYODIDE_INDEX}pyodide.mjs`)) as {
    loadPyodide: (opts: { indexURL: string }) => Promise<PyodideAPI>;
  };
  const pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX });
  const pyBase = new URL("py/", baseUrl);
  const manifest = (await (await fetch(new URL("manifest.json", pyBase), { cache: "no-store" })).json()) as { version: string };
  const bundle = await fetch(new URL(`bundle.zip?v=${manifest.version}`, pyBase));
  if (!bundle.ok) throw new Error(`No se pudo descargar el motor (${bundle.status})`);
  pyodide.unpackArchive(await bundle.arrayBuffer(), "zip", { extractDir: APP_DIR });
  pyodide.runPython(`import sys\nsys.path.insert(0, "${APP_DIR}")\nfrom visualization.web_api import handle, metadata`);
  handle = pyodide.globals.get("handle") as PyCallable;
  const metadata = pyodide.globals.get("metadata") as PyCallable;
  return JSON.parse(metadata());
}

scope.onmessage = async (event: MessageEvent<Incoming>) => {
  const msg = event.data;
  try {
    if (msg.type === "init") {
      scope.postMessage({ id: msg.id, ok: true, meta: await init(msg.baseUrl) });
    } else if (handle) {
      scope.postMessage({ id: msg.id, ok: true, result: JSON.parse(handle(JSON.stringify(msg.request))) });
    } else {
      throw new Error("El motor todavía no está listo");
    }
  } catch (err) {
    scope.postMessage({ id: msg.id, ok: false, error: err instanceof Error ? err.message : String(err) });
  }
};
