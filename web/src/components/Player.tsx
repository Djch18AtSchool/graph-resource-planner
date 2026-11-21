// Controles para recorrer el algoritmo paso a paso.
import { Pause, Play, RotateCcw, SkipBack, SkipForward } from "lucide-react";
import { useEffect } from "react";
import { Segmented } from "./ui";

const TOTAL_MS = 9000;
const MIN_DELAY_MS = 90;
const MAX_DELAY_MS = 900;
export type Speed = "0.5" | "1" | "2";

export function usePlayback(total: number, step: number, setStep: (k: number) => void, playing: boolean,
  setPlaying: (p: boolean) => void, speed: Speed) {
  useEffect(() => {
    if (!playing) return;
    if (step >= total) { setPlaying(false); return; }
    const delay = Math.min(MAX_DELAY_MS, Math.max(MIN_DELAY_MS, TOTAL_MS / Math.max(total, 1))) / Number(speed);
    const timer = window.setTimeout(() => setStep(step + 1), delay);
    return () => window.clearTimeout(timer);
  }, [playing, step, total, speed, setStep, setPlaying]);
}

export function Player({ total, step, setStep, playing, setPlaying, speed, setSpeed }: {
  total: number;
  step: number;
  setStep: (k: number) => void;
  playing: boolean;
  setPlaying: (p: boolean) => void;
  speed: Speed;
  setSpeed: (s: Speed) => void;
}) {
  const iconBtn = "grid size-9 place-items-center rounded-lg text-ink-soft hover:bg-sunken disabled:opacity-35";
  const togglePlay = () => {
    if (playing) { setPlaying(false); return; }
    if (step >= total) setStep(0);
    setPlaying(true);
  };
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-line bg-surface px-3 py-2.5">
      <button type="button" className={iconBtn} onClick={() => { setPlaying(false); setStep(0); }} disabled={step === 0} aria-label="Volver al inicio" title="Volver al inicio">
        <RotateCcw className="size-4" />
      </button>
      <button type="button" className={iconBtn} onClick={() => { setPlaying(false); setStep(Math.max(0, step - 1)); }} disabled={step === 0} aria-label="Paso anterior" title="Paso anterior">
        <SkipBack className="size-4" />
      </button>
      <button
        type="button"
        onClick={togglePlay}
        className="flex h-9 items-center gap-2 rounded-lg bg-ink px-4 text-sm font-medium text-white shadow-card hover:bg-ink-soft"
        aria-label={playing ? "Pausar" : "Reproducir"}
      >
        {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
        {playing ? "Pausar" : step >= total ? "Repetir" : "Reproducir"}
      </button>
      <button type="button" className={iconBtn} onClick={() => { setPlaying(false); setStep(Math.min(total, step + 1)); }} disabled={step >= total} aria-label="Paso siguiente" title="Paso siguiente">
        <SkipForward className="size-4" />
      </button>
      <input
        type="range" min={0} max={total} value={step}
        onChange={(e) => { setPlaying(false); setStep(Number(e.target.value)); }}
        aria-label="Paso del algoritmo"
        className="mx-2 h-1.5 min-w-32 flex-1 cursor-pointer accent-ink"
      />
      <span className="w-24 text-right text-sm tabular-nums text-muted" data-testid="step-label">Paso {step} de {total}</span>
      <Segmented<Speed> label="Velocidad" value={speed} onChange={setSpeed}
        options={[{ value: "0.5", label: "0.5×" }, { value: "1", label: "1×" }, { value: "2", label: "2×" }]} />
    </div>
  );
}
