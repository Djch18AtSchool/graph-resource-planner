// Paso 1: escribir (o elegir) las tareas y sus recursos.
import { AlertCircle, ArrowRight, Cpu, GraduationCap, ListTodo, LoaderCircle, ShoppingCart, Shuffle } from "lucide-react";
import type { ComponentType } from "react";
import { Editor, TOKEN_COLORS } from "../components/Editor";
import { Button, Card, ResourceChip, StepTitle } from "../components/ui";
import type { Meta, PlanView } from "../engine/types";
import { errorLine, num, plural } from "../lib/format";

const EXAMPLE_INFO: Record<string, { icon: ComponentType<{ className?: string }>; name: string; blurb: string }> = {
  microservicios: { icon: ShoppingCart, name: "E-commerce", blurb: "Mantenimiento nocturno de los servicios de una tienda en línea" },
  examenes: { icon: GraduationCap, name: "Exámenes finales", blurb: "Cursos que comparten estudiantes" },
  ml: { icon: Cpu, name: "Machine learning", blurb: "Entrenamientos que comparten GPU y discos" },
  corona: { icon: Shuffle, name: "Caso difícil", blurb: "Un grafo donde Welsh-Powell usa más lotes de los necesarios" },
};

const PLACEHOLDER = [
  "Escriba una tarea por línea, por ejemplo:",
  "",
  "Migrar base de datos [30]: db_pedidos",
  "Respaldo [20]: db_pedidos, disco",
  "Enviar reportes [10]: correo",
].join("\n");

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

function EmptyPreview() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <span className="grid size-11 place-items-center rounded-xl bg-sunken text-faint"><ListTodo className="size-5" /></span>
      <p className="text-sm font-medium text-ink-soft">Aquí aparecerán sus tareas</p>
      <p className="max-w-64 text-sm text-muted">Escriba en el editor o pruebe uno de los ejemplos de abajo.</p>
    </div>
  );
}

function Preview({ text, view, error, ready }: { text: string; view: PlanView | null; error: string | null; ready: boolean }) {
  if (!text.trim()) return <EmptyPreview />;
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

function ExamplePills({ meta, onPick }: { meta: Meta | null; onPick: (text: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="mr-1 text-sm text-muted">Probar con un ejemplo:</span>
      {(meta?.examples ?? Object.keys(EXAMPLE_INFO).map((key) => ({ key, title: "", text: "" }))).map((ex) => {
        const info = EXAMPLE_INFO[ex.key] ?? { icon: Shuffle, name: ex.title, blurb: ex.title };
        const Icon = info.icon;
        return (
          <button
            key={ex.key}
            type="button"
            disabled={!meta}
            title={info.blurb}
            onClick={() => onPick(ex.text)}
            className="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-surface py-1.5 pl-2.5 pr-3.5 text-sm text-ink-soft shadow-card transition-colors hover:border-ink/40 hover:text-ink disabled:opacity-50"
          >
            <Icon className="size-4 text-muted" />
            {info.name}
          </button>
        );
      })}
    </div>
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
  const shown = !text.trim() || error ? null : view;
  return (
    <section>
      <StepTitle
        number={1}
        title="¿Qué tareas hay que ejecutar?"
        info={<>
          Escriba una tarea por línea con los recursos que necesita, por ejemplo una base de datos o una GPU.
          <strong className="font-semibold text-ink"> Dos tareas que usan el mismo recurso no pueden ejecutarse al mismo tiempo</strong>:
          el planificador las pondrá en lotes distintos. La duración entre corchetes es opcional.
        </>}
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card className="flex h-[440px] flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Editor</h2>
            <span className="text-xs text-muted">Ctrl+Z para deshacer</span>
          </div>
          <div className="min-h-0 flex-1">
            <Editor value={text} onChange={setText} placeholderText={PLACEHOLDER}
              errorLine={error && text.trim() ? errorLine(error) : null} errorMessage={error} />
          </div>
          <SyntaxLegend />
        </Card>

        <Card className="flex h-[440px] flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Tareas reconocidas</h2>
            {shown && <span className="text-xs text-muted">{plural(shown.metrics.tasks, "tarea", "tareas")}, {plural(shown.resources.length, "recurso", "recursos")}</span>}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <Preview text={text} view={view} error={error} ready={meta !== null} />
          </div>
        </Card>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
        <ExamplePills meta={meta} onPick={setText} />
        <div className="ml-auto flex items-center gap-4">
          {shown && (
            <p className="text-sm text-muted">
              Se detectaron <strong className="font-semibold text-ink">{plural(shown.metrics.conflicts, "conflicto", "conflictos")}</strong> entre tareas.
            </p>
          )}
          <Button variant="primary" onClick={onNext} disabled={!shown}>
            Ver conflictos <ArrowRight className="size-4" />
          </Button>
        </div>
      </div>
    </section>
  );
}
