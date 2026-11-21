// Editor del formato de tareas (CodeMirror 6): resaltado, números de línea y el error marcado en su línea.
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { setDiagnostics } from "@codemirror/lint";
import { EditorState } from "@codemirror/state";
import { EditorView, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers, placeholder } from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { useEffect, useRef } from "react";
import { taskLanguage } from "../lib/syntax";

export const TOKEN_COLORS = {
  name: "#0f172a",
  duration: "#b45309",
  resource: "#4f46e5",
  operator: "#dc2626",
  comment: "#94a3b8",
  title: "#059669",
} as const;

const highlight = HighlightStyle.define([
  { tag: tags.typeName, color: TOKEN_COLORS.name, fontWeight: "500" },
  { tag: tags.number, color: TOKEN_COLORS.duration },
  { tag: tags.variableName, color: TOKEN_COLORS.resource },
  { tag: tags.operator, color: TOKEN_COLORS.operator, fontWeight: "600" },
  { tag: tags.punctuation, color: "#94a3b8" },
  { tag: tags.comment, color: TOKEN_COLORS.comment, fontStyle: "italic" },
  { tag: tags.keyword, color: TOKEN_COLORS.title, fontWeight: "600" },
  { tag: tags.string, color: TOKEN_COLORS.title },
]);

export function Editor({ value, onChange, errorLine, errorMessage }: {
  value: string;
  onChange: (text: string) => void;
  errorLine: number | null;
  errorMessage: string | null;
}) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const editor = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value,
        extensions: [
          lineNumbers(), highlightActiveLineGutter(), highlightActiveLine(), history(),
          keymap.of([...defaultKeymap, ...historyKeymap]), taskLanguage, syntaxHighlighting(highlight),
          placeholder("Respaldo [20]: base_de_datos, disco"),
          EditorView.contentAttributes.of({ "aria-label": "Tareas, una por línea" }),
          EditorView.updateListener.of((u) => { if (u.docChanged) onChangeRef.current(u.state.doc.toString()); }),
        ],
      }),
    });
    view.current = editor;
    return () => editor.destroy();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- el editor se crea una sola vez
  }, []);

  // Texto cambiado desde afuera (ej.: al elegir un ejemplo).
  useEffect(() => {
    const editor = view.current;
    if (editor && editor.state.doc.toString() !== value) {
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value } });
    }
  }, [value]);

  useEffect(() => {
    const editor = view.current;
    if (!editor) return;
    const doc = editor.state.doc;
    const diagnostics = errorLine && errorLine <= doc.lines && errorMessage
      ? [{ from: doc.line(errorLine).from, to: Math.max(doc.line(errorLine).to, doc.line(errorLine).from), severity: "error" as const, message: errorMessage }]
      : [];
    editor.dispatch(setDiagnostics(editor.state, diagnostics));
  }, [errorLine, errorMessage, value]);

  return <div ref={host} className="h-full min-h-0 overflow-hidden" />;
}
