import { StringStream } from "@codemirror/language";
import { describe, expect, it } from "vitest";
import coronaWp from "../__fixtures__/corona-welsh_powell.json";
import microDsatur from "../__fixtures__/microservicios-dsatur.json";
import microWp from "../__fixtures__/microservicios-welsh_powell.json";
import type { PlanView } from "../engine/types";
import { batchColor, PALETTE, textOnBatch } from "./colors";
import { adjacency, colorsAfter, dsaturCandidates, welshPowellOrder } from "./decisions";
import { errorLine, listNames, num } from "./format";
import { batchLayout, forceLayout } from "./layout";
import { nextToken } from "./syntax";

const views = [microDsatur, microWp, coronaWp] as unknown as PlanView[];

describe("tabla de decisión de DSatur", () => {
  it("la candidata que ordena la UI es la que Python elige en cada paso", () => {
    const view = microDsatur as unknown as PlanView;
    const adj = adjacency(view);
    view.steps.forEach((step, k) => {
      const [first] = dsaturCandidates(view, adj, k);
      expect(first.task).toBe(step.task);
      expect(first.chosen).toBe(true);
      expect(first.saturation).toBe(step.saturation);
    });
  });
});

describe("orden de Welsh-Powell", () => {
  it.each([["microservicios", microWp], ["corona", coronaWp]])("%s: la elegida es la primera libre y no bloqueada", (_, raw) => {
    const view = raw as unknown as PlanView;
    const adj = adjacency(view);
    view.steps.forEach((_step, k) => {
      const order = welshPowellOrder(view, adj, k);
      const firstFree = order.find((e) => e.batch === null && !e.blocked);
      expect(firstFree?.chosen).toBe(true);
    });
  });
});

describe("colorsAfter", () => {
  it("después de todos los pasos coincide con el lote de cada tarea", () => {
    for (const view of views) {
      const colors = colorsAfter(view, view.steps.length);
      view.tasks.forEach((t) => expect(colors.get(t.id)).toBe(t.batch));
    }
  });
});

describe("layouts", () => {
  it("por lotes: ninguna arista une dos tareas de la misma columna", () => {
    for (const view of views) {
      const pos = batchLayout(view);
      view.conflicts.forEach((c) => expect(pos.get(c.source)!.x).not.toBe(pos.get(c.target)!.x));
    }
  });
  it("de fuerzas: es determinista y no superpone vértices", () => {
    const view = views[0];
    const a = forceLayout(view);
    const b = forceLayout(view);
    expect([...a.entries()]).toEqual([...b.entries()]);
    const pts = [...a.values()];
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        expect(Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y)).toBeGreaterThan(40);
      }
    }
  });
});

describe("colores", () => {
  it("usa la paleta y luego tonos generados", () => {
    expect(batchColor(1)).toBe(PALETTE[0]);
    expect(batchColor(13)).toMatch(/^hsl/);
  });
  it("elige texto oscuro sobre amarillo y claro sobre azul", () => {
    expect(textOnBatch(6)).toBe("#0F172A");
    expect(textOnBatch(1)).toBe("#FFFFFF");
  });
});

describe("formato", () => {
  it("extrae la línea del error del motor", () => {
    expect(errorLine("línea 3: la tarea «A» aparece dos veces")).toBe(3);
    expect(errorLine("El problema no tiene tareas")).toBeNull();
  });
  it("lista nombres de forma legible", () => {
    expect(listNames(["A", "B", "C"])).toBe("«A», «B» y «C»");
    expect(listNames(["A", "B", "C", "D", "E", "F"], 4)).toBe("«A», «B», «C», «D» y 2 más");
    expect(num(2.5)).toBe("2.5");
  });
});

describe("resaltado del editor", () => {
  const tokens = (line: string) => {
    const stream = new StringStream(line, 2, 2);
    const state = { part: "start" as const } as { part: "start" | "name" | "resources" | "title" };
    const out: [string, string | null][] = [];
    while (!stream.eol()) {
      const start = stream.pos;
      const style = nextToken(stream, state);
      if (stream.pos === start) stream.next();
      out.push([line.slice(start, stream.pos).trim(), style]);
    }
    return out.filter(([text]) => text);
  };
  it("reconoce nombre, duración y recursos", () => {
    expect(tokens("Respaldo [20]: db, disco")).toEqual([
      ["Respaldo", "typeName"], ["[20]", "number"], [":", "punctuation"], ["db", "variableName"],
      [",", "punctuation"], ["disco", "variableName"],
    ]);
  });
  it("reconoce conflictos, títulos y comentarios", () => {
    expect(tokens("A -- B").map(([, s]) => s)).toEqual(["typeName", "operator", "typeName"]);
    expect(tokens("titulo: Plan")[0][1]).toBe("keyword");
    expect(tokens("# nota")).toEqual([["# nota", "comment"]]);
  });
});
