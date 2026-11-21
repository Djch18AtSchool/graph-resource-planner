import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { Header } from "./components/Header";
import type { Algorithm } from "./engine/types";
import { useEngineMeta, usePlan, useRoute } from "./state";
import { ConflictsStep } from "./steps/ConflictsStep";
import { PlanStep } from "./steps/PlanStep";
import { StressPage } from "./steps/StressPage";
import { TasksStep } from "./steps/TasksStep";

export function App() {
  const [route, go] = useRoute();
  const { meta, failure } = useEngineMeta();
  const [text, setText] = useState("");
  const [algorithm, setAlgorithm] = useState<Algorithm>("dsatur");
  const { view, error } = usePlan(text, algorithm, meta !== null);

  // Primer ejemplo como punto de partida.
  useEffect(() => {
    if (meta && !text) setText(meta.examples[0]?.text ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al cargar el motor
  }, [meta]);

  const canAdvance = view !== null && error === null;
  const needsPlan = route === "conflictos" || route === "plan";

  return (
    <div className="min-h-dvh">
      <Header route={route} go={go} canAdvance={canAdvance} />
      <main className="mx-auto max-w-7xl px-6 pb-16 pt-10">
        {failure && (
          <div className="mb-6 flex gap-3 rounded-xl bg-danger-soft p-4 text-sm text-danger" role="alert">
            <AlertTriangle className="size-4 shrink-0" />
            No se pudo iniciar el motor de grafos ({failure}). Revise la conexión a internet y recargue la página.
          </div>
        )}
        {route === "tareas" && (
          <TasksStep meta={meta} text={text} setText={setText} view={view} error={error} onNext={() => go("conflictos")} />
        )}
        {needsPlan && !canAdvance && (
          <div className="py-24 text-center text-muted">
            <p>Primero hay que definir tareas válidas.</p>
            <button type="button" className="mt-3 font-medium text-accent hover:underline" onClick={() => go("tareas")}>Ir al paso 1</button>
          </div>
        )}
        {route === "conflictos" && canAdvance && view && (
          <ConflictsStep view={view} algorithm={algorithm} setAlgorithm={setAlgorithm} onBack={() => go("tareas")} onNext={() => go("plan")} />
        )}
        {route === "plan" && canAdvance && view && (
          <PlanStep view={view} setAlgorithm={setAlgorithm} onBack={() => go("conflictos")} />
        )}
        {route === "estres" && <StressPage />}
      </main>
    </div>
  );
}
