// Estado compartido: ruta (en el hash de la URL), motor de Python y plan calculado.
import { useCallback, useEffect, useRef, useState } from "react";
import { engine } from "./engine/engine";
import type { Algorithm, Meta, PlanView } from "./engine/types";

export type Route = "tareas" | "conflictos" | "plan" | "estres";
const ROUTES: Route[] = ["tareas", "conflictos", "plan", "estres"];
const ANALYZE_DEBOUNCE_MS = 300;

function readRoute(): Route {
  const hash = window.location.hash.replace("#", "") as Route;
  return ROUTES.includes(hash) ? hash : "tareas";
}

export function useRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = useState<Route>(readRoute);
  useEffect(() => {
    const onHash = () => { setRoute(readRoute()); window.scrollTo({ top: 0 }); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = useCallback((next: Route) => { window.location.hash = next; }, []);
  return [route, go];
}

export function useEngineMeta(): { meta: Meta | null; failure: string | null } {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  useEffect(() => {
    engine.start().then(setMeta).catch((err: Error) => setFailure(err.message));
  }, []);
  return { meta, failure };
}

export interface PlanState {
  view: PlanView | null;      // último plan válido
  error: string | null;       // error del texto actual (con "línea N" si aplica)
  pending: boolean;
}

/** Recalcula el plan cuando cambian el texto o el algoritmo (con debounce e ignorando respuestas viejas). */
export function usePlan(text: string, algorithm: Algorithm, ready: boolean): PlanState {
  const [state, setState] = useState<PlanState>({ view: null, error: null, pending: true });
  const seq = useRef(0);
  useEffect(() => {
    if (!ready) return;
    const id = ++seq.current;
    if (!text.trim()) {                       // editor vacío: no es un error, es el estado inicial
      setState({ view: null, error: null, pending: false });
      return;
    }
    setState((s) => ({ ...s, pending: true }));
    const timer = window.setTimeout(async () => {
      try {
        const result = await engine.analyze({ mode: "text", text, algorithm });
        if (id !== seq.current) return;
        setState((s) => result.ok
          ? { view: result.view, error: null, pending: false }
          : { view: s.view, error: result.error, pending: false });
      } catch (err) {
        if (id === seq.current) setState((s) => ({ ...s, error: (err as Error).message, pending: false }));
      }
    }, ANALYZE_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [text, algorithm, ready]);
  return state;
}
