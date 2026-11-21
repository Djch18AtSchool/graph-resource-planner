import clsx from "clsx";
import { Check, Gauge } from "lucide-react";
import type { Route } from "../state";

const STEPS: { route: Route; label: string }[] = [
  { route: "tareas", label: "Tareas" },
  { route: "conflictos", label: "Conflictos" },
  { route: "plan", label: "Plan" },
];

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-8 shrink-0" aria-hidden>
      <rect width="32" height="32" rx="8" className="fill-ink" />
      <path d="M10 11 22 11 16 22Z" fill="none" stroke="#475569" strokeWidth="1.6" />
      <circle cx="10" cy="11" r="4" fill="#3B82F6" />
      <circle cx="22" cy="11" r="4" fill="#F59E0B" />
      <circle cx="16" cy="22" r="4" fill="#10B981" />
    </svg>
  );
}

export function Header({ route, go, canAdvance }: { route: Route; go: (r: Route) => void; canAdvance: boolean }) {
  const current = STEPS.findIndex((s) => s.route === route);
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-6">
        <a href="#tareas" className="flex items-center gap-3" aria-label="Planificador de lotes, inicio">
          <Logo />
          <span className="hidden leading-tight sm:block">
            <span className="block text-[15px] font-semibold">Planificador de lotes</span>
            <span className="block text-xs text-muted">Coloración de grafos, Grupo 2</span>
          </span>
        </a>

        <nav aria-label="Pasos" className="mx-auto">
          <ol className="flex items-center gap-1 sm:gap-2">
            {STEPS.map((s, i) => {
              const done = current > i;
              const active = current === i;
              const reachable = i === 0 || canAdvance;
              return (
                <li key={s.route} className="flex items-center gap-1 sm:gap-2">
                  {i > 0 && <span aria-hidden className={clsx("h-px w-5 sm:w-10", done || active ? "bg-ink/40" : "bg-line-strong")} />}
                  <button
                    type="button"
                    disabled={!reachable}
                    onClick={() => go(s.route)}
                    aria-current={active ? "step" : undefined}
                    className={clsx(
                      "flex items-center gap-2 rounded-full py-1 pl-1 pr-3 text-sm transition-colors disabled:opacity-40",
                      active ? "bg-ink text-white" : "text-ink-soft hover:bg-sunken",
                    )}
                  >
                    <span className={clsx(
                      "grid size-6 place-items-center rounded-full text-xs font-semibold",
                      active ? "bg-white text-ink" : done ? "bg-ink text-white" : "bg-sunken text-muted ring-1 ring-line-strong",
                    )}>
                      {done ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
                    </span>
                    <span className="hidden font-medium sm:inline">{s.label}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        <button
          type="button"
          onClick={() => go("estres")}
          className={clsx(
            "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            route === "estres" ? "bg-accent-soft text-accent" : "text-ink-soft hover:bg-sunken",
          )}
        >
          <Gauge className="size-4" />
          <span className="hidden md:inline">Prueba de estrés</span>
        </button>
      </div>
    </header>
  );
}
