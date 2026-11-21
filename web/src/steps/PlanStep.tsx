// Paso 3: el plan de ejecución. Cada lote es una etapa: sus tareas corren en paralelo y las etapas, en orden.
import { ArrowLeft, ChevronRight, Clock, Layers, Lightbulb, Users } from "lucide-react";
import { useState, type ReactNode } from "react";
import { BatchDot, Button, Card, ResourceChip, Segmented, StepTitle } from "../components/ui";
import type { Algorithm, PlanView } from "../engine/types";
import { batchColor, textOnBatch } from "../lib/colors";
import { ALGORITHM_NAMES, listNames, num, plural } from "../lib/format";

const PIPELINE_MAX_CARDS = 30;
const TIMELINE_MAX_TASKS = 80;
type PlanMode = "pipeline" | "timeline";

function explanation(view: PlanView): string {
  const m = view.metrics;
  if (m.conflicts === 0) return "No hay conflictos: todas las tareas pueden correr juntas.";
  if (m.exact_method === "clique") {
    return `Es el mínimo posible: ${listNames(view.clique)} chocan todas entre sí, así que cada una necesita su propio lote.`;
  }
  if (m.exact_method === "branch_and_bound") return "Es el mínimo posible: una búsqueda exhaustiva (branch & bound) lo confirma.";
  return `El mínimo está entre ${m.lower} y ${m.upper}. Calcularlo exacto en un grafo de este tamaño es NP-difícil, así que se acota con una clique y la mejor heurística.`;
}

function Stat({ icon, label, value, detail }: { icon: ReactNode; label: string; value: ReactNode; detail: ReactNode }) {
  return (
    <Card className="p-4">
      <p className="flex items-center gap-2 text-sm text-muted">{icon}{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      <p className="mt-1 text-sm text-muted">{detail}</p>
    </Card>
  );
}

function Verdict({ view, setAlgorithm }: { view: PlanView; setAlgorithm: (a: Algorithm) => void }) {
  const m = view.metrics;
  const suboptimal = m.exact !== null && m.colors > m.exact;
  const chi = m.exact !== null ? `χ(G) = ${m.exact}` : `${m.lower} ≤ χ(G) ≤ ${m.upper}`;
  return (
    <Card className="mb-4 overflow-hidden">
      <div className="flex flex-wrap items-center gap-6 p-6">
        <div className="flex items-baseline gap-3">
          <span className="text-6xl font-semibold tracking-tighter tabular-nums">{m.colors}</span>
          <span className="text-xl font-medium text-ink-soft">{m.colors === 1 ? "lote" : "lotes"}</span>
        </div>
        <div className="min-w-64 flex-1">
          <p className="text-[15px] leading-relaxed text-ink-soft">
            {ALGORITHM_NAMES[view.algorithm]} agrupa las {m.tasks} tareas en {plural(m.colors, "lote", "lotes")}.{" "}
            {suboptimal ? `Pero bastan ${m.exact}.` : explanation(view)}
          </p>
        </div>
        <div className="rounded-lg bg-sunken px-4 py-3 text-center ring-1 ring-line">
          <p className="font-mono text-lg font-medium" data-testid="chi">{chi}</p>
          <p className="text-xs text-muted">número cromático</p>
        </div>
      </div>
      {suboptimal && (
        <div className="flex flex-wrap items-center gap-3 border-t border-amber-200 bg-amber-50 px-6 py-3 text-sm text-amber-800">
          <Lightbulb className="size-4" />
          <span className="flex-1">{ALGORITHM_NAMES[view.alternative.algorithm]} encuentra un plan con {plural(view.alternative.colors, "lote", "lotes")} para este mismo problema.</span>
          <Button onClick={() => setAlgorithm(view.alternative.algorithm)}>Usar {ALGORITHM_NAMES[view.alternative.algorithm]}</Button>
        </div>
      )}
    </Card>
  );
}

function Pipeline({ view }: { view: PlanView }) {
  const byId = new Map(view.tasks.map((t) => [t.id, t]));
  return (
    <div className="flex items-start gap-1 overflow-x-auto pb-3">
      {view.batches.map((b, i) => (
        <div key={b.index} className="flex items-start gap-1">
          {i > 0 && <ChevronRight className="mt-5 size-5 shrink-0 text-faint" aria-hidden />}
          <div className="w-60 shrink-0 overflow-hidden rounded-xl border border-line bg-surface shadow-card">
            <div className="flex items-center justify-between px-3.5 py-2.5" style={{ background: batchColor(b.index), color: textOnBatch(b.index) }}>
              <span className="text-sm font-semibold">Lote {b.index}</span>
              <span className="text-xs opacity-90 tabular-nums">t {num(b.start)} → {num(b.start + b.duration)}</span>
            </div>
            <ul className="space-y-2 p-2.5">
              {b.tasks.slice(0, PIPELINE_MAX_CARDS).map((id) => {
                const t = byId.get(id)!;
                return (
                  <li key={id} className="rounded-lg border border-line p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">{id}</span>
                      <span className="shrink-0 text-xs text-muted tabular-nums">{num(t.duration)}</span>
                    </div>
                    <div className="mt-1.5 h-1 rounded-full bg-sunken">
                      <div className="h-full rounded-full" style={{ width: `${(t.duration / b.duration) * 100}%`, background: batchColor(b.index) }} />
                    </div>
                    {t.resources.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{t.resources.map((r) => <ResourceChip key={r} name={r} />)}</div>}
                  </li>
                );
              })}
              {b.tasks.length > PIPELINE_MAX_CARDS && <li className="px-1 text-xs text-muted">y {b.tasks.length - PIPELINE_MAX_CARDS} tareas más</li>}
            </ul>
          </div>
        </div>
      ))}
    </div>
  );
}

function Timeline({ view }: { view: PlanView }) {
  const total = view.metrics.makespan || 1;
  if (view.tasks.length > TIMELINE_MAX_TASKS) {
    return <p className="p-6 text-sm text-muted">El cronograma se muestra para hasta {TIMELINE_MAX_TASKS} tareas; use la vista de etapas.</p>;
  }
  const byId = new Map(view.tasks.map((t) => [t.id, t]));
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  return (
    <Card className="p-5">
      <div className="grid grid-cols-[minmax(120px,220px)_1fr] items-center gap-x-4 gap-y-1">
        {view.batches.map((b) => (
          <div key={b.index} className="contents">
            <p className="col-span-2 mt-3 flex items-center gap-2 text-sm font-semibold first:mt-0">
              <BatchDot batch={b.index} /> Lote {b.index}
              <span className="text-xs font-normal text-muted tabular-nums">t {num(b.start)} → {num(b.start + b.duration)}</span>
            </p>
            {b.tasks.map((id) => (
              <div key={id} className="contents">
                <span className="truncate text-sm text-ink-soft">{id}</span>
                <div className="relative h-5 rounded bg-sunken">
                  <div className="absolute inset-y-1 rounded" title={`${id}: ${num(byId.get(id)!.duration)}`}
                    style={{ left: `${(b.start / total) * 100}%`, width: `${Math.max((byId.get(id)!.duration / total) * 100, 0.8)}%`, background: batchColor(b.index) }} />
                </div>
              </div>
            ))}
          </div>
        ))}
        <span />
        <div className="mt-2 flex justify-between text-xs text-muted tabular-nums">
          {ticks.map((f) => <span key={f}>{num(total * f)}</span>)}
        </div>
      </div>
    </Card>
  );
}

export function PlanStep({ view, setAlgorithm, onBack }: { view: PlanView; setAlgorithm: (a: Algorithm) => void; onBack: () => void }) {
  const [mode, setMode] = useState<PlanMode>("pipeline");
  const m = view.metrics;
  return (
    <section>
      <StepTitle number={3} title="Plan de ejecución">
        Las tareas de un mismo lote corren al mismo tiempo porque no comparten ningún recurso. Los lotes se ejecutan
        uno después del otro, y cada uno termina cuando acaba su tarea más larga.
      </StepTitle>

      <Verdict view={view} setAlgorithm={setAlgorithm} />

      <div className="mb-8 grid gap-4 md:grid-cols-3">
        <Stat icon={<Clock className="size-4" />} label="Tiempo total" value={num(m.makespan)}
          detail={<>contra {num(m.sequential)} si todo fuera en fila ({m.speedup}× más rápido)</>} />
        <Stat icon={<Users className="size-4" />} label="Ejecutores necesarios" value={m.workers}
          detail="es el tamaño del lote más grande" />
        <Stat icon={<Layers className="size-4" />} label="Comparación" value={<>{m.colors} <span className="text-base font-normal text-muted">vs</span> {view.alternative.colors}</>}
          detail={<>lotes con {ALGORITHM_NAMES[view.algorithm]} y con {ALGORITHM_NAMES[view.alternative.algorithm]}</>} />
      </div>

      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Lotes en orden de ejecución</h2>
        <Segmented<PlanMode> label="Vista del plan" value={mode} onChange={setMode}
          options={[{ value: "pipeline", label: "Etapas" }, { value: "timeline", label: "Cronograma" }]} />
      </div>
      {mode === "pipeline" ? <Pipeline view={view} /> : <Timeline view={view} />}

      <div className="mt-8 flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}><ArrowLeft className="size-4" /> Conflictos</Button>
      </div>
    </section>
  );
}
