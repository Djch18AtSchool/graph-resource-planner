// Resaltado del formato de tareas para CodeMirror:
//   titulo: Mi sistema
//   Tarea [duración]: recurso1, recurso2
//   Tarea A -- Tarea B
//   # comentario
import { StreamLanguage, type StringStream } from "@codemirror/language";

interface LineState {
  part: "start" | "name" | "resources" | "title";
}

/** Clasifica el siguiente token de la línea; los nombres coinciden con las etiquetas de @lezer/highlight. */
export function nextToken(stream: StringStream, state: LineState): string | null {
  if (stream.sol()) {
    state.part = "start";
    stream.eatSpace();
    if (stream.peek() === "#") { stream.skipToEnd(); return "comment"; }
    if (stream.match(/^t[ií]tulo\s*:/i)) { state.part = "title"; return "keyword"; }
    state.part = "name";
  }
  if (stream.eatSpace()) return null;
  if (state.part === "title") { stream.skipToEnd(); return "string"; }
  if (stream.match("--")) return "operator";
  if (stream.match(/^\[[^\]]*\]/)) return "number";
  if (stream.eat(":")) { state.part = "resources"; return "punctuation"; }
  if (stream.eat(",")) return "punctuation";
  if (state.part === "resources") { stream.match(/^[^,]+/); return "variableName"; }
  stream.match(/^(?:(?!--)[^[\]:])+/);
  return "typeName";
}

export const taskLanguage = StreamLanguage.define<LineState>({
  name: "tareas",
  startState: () => ({ part: "start" }),
  token: nextToken,
  copyState: (s) => ({ ...s }),
});
