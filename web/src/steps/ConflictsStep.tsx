// Paso 2: el grafo de conflictos y el algoritmo coloreándolo paso a paso.
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { ConflictGraph, type GraphLayout } from "../components/ConflictGraph";
import { DecisionPanel } from "../components/DecisionPanel";
import { Matrix } from "../components/Matrix";
import { Player, usePlayback, type Speed } from "../components/Player";
import { Button, Card, Segmented, StepTitle } from "../components/ui";
import type { Algorithm, PlanView } from "../engine/types";
import { plural } from "../lib/format";

const DRAW_MAX_TASKS = 250;
type Mode = "graph" | "matrix";

export function ConflictsStep({ view, algorithm, setAlgorithm, onBack, onNext }: {
  view: PlanView;
  algorithm: Algorithm;
  setAlgorithm: (a: Algorithm) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const total = view.steps.length;
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>("1");
  const [layout, setLayout] = useState<GraphLayout>("free");
  const [mode, setMode] = useState<Mode>("graph");
  usePlayback(total, step, setStep, playing, setPlaying, speed);

  // Otro algoritmo u otro problema: la animación vuelve al inicio.
  useEffect(() => { setStep(0); setPlaying(false); }, [view]);

  const drawable = view.drawable && view.tasks.length <= DRAW_MAX_TASKS;
  const m = view.metrics;

  return (
    <section>
      <StepTitle number={2} title="¿Qué tareas chocan entre sí?">
        Cada línea une dos tareas que comparten un recurso: no pueden ir en el mismo lote. Presione
        <strong className="font-semibold text-ink"> Reproducir </strong> y vea cómo el algoritmo le asigna un lote (un color) a
        cada tarea sin que dos vecinas repitan color.
      </StepTitle>

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Segmented<Algorithm> label="Algoritmo" value={algorithm} onChange={setAlgorithm}
          options={[{ value: "dsatur", label: "DSatur" }, { value: "welsh_powell", label: "Welsh-Powell" }]} />
        <Segmented<Mode> label="Vista" value={mode} onChange={setMode}
          options={[{ value: "graph", label: "Grafo" }, { value: "matrix", label: "Matriz" }]} />
        {mode === "graph" && (
          <Segmented<GraphLayout> label="Disposición" value={layout} onChange={setLayout}
            options={[{ value: "free", label: "Libre" }, { value: "batches", label: "Agrupado por lote", disabled: step < total, title: "Disponible al terminar la coloración" }]} />
        )}
        <span className="ml-auto text-sm text-muted">
          {plural(m.tasks, "tarea", "tareas")}, {plural(m.conflicts, "conflicto", "conflictos")}, grado máximo {m.max_degree}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card className="flex h-[600px] flex-col overflow-hidden">
          <div className="min-h-0 flex-1">
            {mode === "matrix" ? <Matrix view={view} colored={step >= total} />
              : drawable ? <ConflictGraph key={`${step < total ? "free" : layout}:${view.algorithm}:${view.tasks.length}:${view.conflicts.length}`}
                  view={view} step={step} layout={step < total ? "free" : layout} />
              : <p className="grid h-full place-items-center p-8 text-center text-sm text-muted">Con {m.tasks} tareas el dibujo deja de ser legible. Use la matriz o vaya al plan.</p>}
          </div>
          <Player total={total} step={step} setStep={setStep} playing={playing} setPlaying={setPlaying} speed={speed} setSpeed={setSpeed} />
        </Card>
        <Card className="h-[600px] overflow-hidden">
          <DecisionPanel view={view} step={step} />
        </Card>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}><ArrowLeft className="size-4" /> Tareas</Button>
        <Button variant="primary" onClick={onNext}>Ver plan <ArrowRight className="size-4" /></Button>
      </div>
    </section>
  );
}
