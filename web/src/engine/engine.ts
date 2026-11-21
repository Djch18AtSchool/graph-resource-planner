// Cliente del Web Worker: una sola instancia de Python para toda la app.
import type { AnalyzeRequest, AnalyzeResult, Meta } from "./types";

type Pending = { resolve: (value: unknown) => void; reject: (err: Error) => void };

class Engine {
  private worker: Worker | null = null;
  private pending = new Map<number, Pending>();
  private nextId = 1;
  private ready: Promise<Meta> | null = null;

  /** Arranca Python una sola vez; las llamadas siguientes reutilizan la misma promesa. */
  start(): Promise<Meta> {
    if (!this.ready) {
      this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
      this.worker.onmessage = (event: MessageEvent<{ id: number; ok: boolean; error?: string } & Record<string, unknown>>) => {
        const { id, ok, error, ...payload } = event.data;
        const entry = this.pending.get(id);
        if (!entry) return;
        this.pending.delete(id);
        if (ok) entry.resolve(payload); else entry.reject(new Error(error ?? "Error desconocido del motor"));
      };
      this.ready = this.call<{ meta: Meta }>({ type: "init", baseUrl: document.baseURI }).then((r) => r.meta);
    }
    return this.ready;
  }

  async analyze(request: AnalyzeRequest): Promise<AnalyzeResult> {
    await this.start();
    const { result } = await this.call<{ result: AnalyzeResult }>({ type: "analyze", request });
    return result;
  }

  private call<T>(message: Record<string, unknown>): Promise<T> {
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (value: unknown) => void, reject });
      this.worker!.postMessage({ id, ...message });
    });
  }
}

export const engine = new Engine();
