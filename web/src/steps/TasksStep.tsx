// Paso 1: escribir (o elegir) las tareas y sus recursos.
import clsx from "clsx";
import { AlertCircle, ArrowRight, Cpu, GraduationCap, LoaderCircle, ShoppingCart, Shuffle } from "lucide-react";
import type { ComponentType } from "react";
import { Editor, TOKEN_COLORS } from "../components/Editor";
import { Button, Card, ResourceChip, StepTitle } from "../components/ui";
import type { Meta, PlanView } from "../engine/types";
import { errorLine, num, plural } from "../lib/format";

const EXAMPLE_INFO: Record<string, { icon: ComponentType<{ className?: string }>; name: string; blurb: string }> = {
  microservicios: { icon: ShoppingCart, name: "E-commerce", blurb: "Mantenimiento nocturno de servicios" },
  examenes: { icon: GraduationCap, name: "Exámenes finales", blurb: "Cursos que comparten estudiantes" },
  ml: { icon: Cpu, name: "Machine learning", blurb: "Entrenamientos que comparten GPU" },
  corona: { icon: Shuffle, name: "Caso difícil", blurb: "Donde Welsh-Powell se equivoca" },
};

function SyntaxLegend() {
  const tok = (text: string, color: string) => <code className="font-mono" style={{ color }}>{text}</code>;
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line bg-sunken/60 px-4 py-2.5 text-xs text-muted">
      <span>{tok("Tarea", TOKEN_COLORS.name)} {tok("[20]", TOKEN_COLORS.duration)}{tok(":", "#94a3b8")} {tok("recurso1, recurso2", TOKEN_COLORS.resource)}</span>
      <span>{tok("A", TOKEN_COLORS.name)} {tok("--", TOKEN_COLORS.operator)} {tok("B", TOKEN_COLORS.name)} <span className="text-faint">choque directo</span></span>
      <span>{tok("# nota", TOKEN_COLORS.comment)}</span>
    </div>
  );
}

function Preview({ view, error, ready }: { view: PlanView | null; error: string | null; ready: boolean }) {
  if (!ready) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center text-sm text-muted">
        <LoaderCircle className="size-5 animate-spin text-faint" />
        Preparando el motor de grafos…
      </div>
    );
  }
  if (error) {
    const line = errorLine(error);
    return (
      <div className="m-4 flex gap-3 rounded-lg bg-danger-soft p-4 text-sm text-danger" role="alert">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        <div>
          <p className="font-medium">{line ? `Revise la línea ${line}` : "Revise el texto"}</p>
          <p className="mt-0.5 text-danger/85">{error.replace(/^línea \d+: /, "")}</p>
        </div>
      </div>
    );
  }
  if (!view) return null;
  return (
    <ul className="divide-y divide-line overflow-y-auto">
      {view.tasks.map((t) => (
        <li key={t.id} className="flex items-start gap-3 px-4 py-2.5">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink">{t.id}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {t.resources.length ? t.resources.map((r) => <ResourceChip key={r} name={r} />)
                : <span className="text-xs text-faint">sin recursos</span>}
            </div>
          </div>
          <span className="shrink-0 rounded-md bg-amber-50 px-1.5 py-0.5 font-mono text-xs text-amber-700 ring-1 ring-amber-200">
            {num(t.duration)}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function TasksStep({ meta, text, setText, view, error, onNext }: {
  meta: Meta | null;
  text: string;
  setText: (t: string) => void;
  view: PlanView | null;
  error: string | null;
  onNext: () => void;
}) {
  const shown = error ? null : view;
  return (
    <section>
      <StepTitle number={1} title="¿Qué tareas hay que ejecutar?">
        Escriba una tarea por línea con los recursos que necesita. Dos tareas que usan el mismo recurso no pueden
        ejecutarse al mismo tiempo. Puede empezar con un ejemplo.
      </StepTitle>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {(meta?.examples ?? []).map((ex) => {
          const info = EXAMPLE_INFO[ex.key] ?? { icon: Shuffle, name: ex.title, blurb: "" };
          const Icon = info.icon;
          const active = ex.text === text;
          return (
            <button
              key={ex.key}
              type="button"
              onClick={() => setText(ex.text)}
              aria-pressed={active}
              className={clsx(
                "flex items-start gap-3 rounded-xl border bg-surface p-3.5 text-left shadow-card transition-all",
                active ? "border-accent ring-2 ring-accent/15" : "border-line hover:border-line-strong",
              )}
            >
              <span className={clsx("grid size-9 shrink-0 place-items-center rounded-lg", active ? "bg-accent text-white" : "bg-sunken text-ink-soft")}>
                <Icon className="size-[18px]" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium" title={ex.title}>{info.name}</span>
                <span className="block truncate text-xs text-muted">{info.blurb}</span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card className="flex h-[460px] flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Editor</h2>
            <span className="text-xs text-muted">Ctrl+Z para deshacer</span>
          </div>
          <div className="min-h-0 flex-1">
            <Editor value={text} onChange={setText} errorLine={error ? errorLine(error) : null} errorMessage={error} />
          </div>
          <SyntaxLegend />
        </Card>

        <Card className="flex h-[460px] flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Tareas reconocidas</h2>
            {shown && <span className="text-xs text-muted">{plural(shown.metrics.tasks, "tarea", "tareas")}, {plural(shown.resources.length, "recurso", "recursos")}</span>}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <Preview view={view} error={error} ready={meta !== null} />
          </div>
        </Card>
      </div>

      <div className="mt-6 flex items-center justify-end gap-4">
        {shown && (
          <p className="text-sm text-muted">
            Se detectaron <strong className="font-semibold text-ink">{plural(shown.metrics.conflicts, "conflicto", "conflictos")}</strong> entre tareas.
          </p>
        )}
        <Button variant="primary" onClick={onNext} disabled={!shown}>
          Ver conflictos <ArrowRight className="size-4" />
        </Button>
      </div>
    </section>
  );
}
