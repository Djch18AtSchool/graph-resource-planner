// Contrato con el motor en Python (visualization/view_model.py y visualization/web_api.py).

export type Algorithm = "dsatur" | "welsh_powell";

export interface Example {
  key: string;
  title: string;
  text: string;
}

export interface Meta {
  examples: Example[];
  algorithms: Algorithm[];
  limits: { max_tasks: number; max_text_chars: number; max_conflicts: number };
}

export interface Metrics {
  tasks: number;
  conflicts: number;
  density: number;
  max_degree: number;
  colors: number;
  lower: number;
  upper: number;
  exact: number | null;
  exact_method: "clique" | "branch_and_bound" | null;
  greedy_bound: number;
  workers: number;
  makespan: number;
  sequential: number;
  speedup: number;
  max_resource_usage: number;
}

export interface TaskView {
  id: string;
  duration: number;
  resources: string[];
  degree: number;
  batch: number;
}

export interface ConflictView {
  source: string;
  target: string;
  resources: string[];
  explicit: boolean;
}

export interface BatchView {
  index: number;
  tasks: string[];
  start: number;
  duration: number;
}

export interface StepView {
  task: string;
  batch: number;
  saturation: number | null;
}

export interface PlanView {
  title: string;
  algorithm: Algorithm;
  alternative: { algorithm: Algorithm; colors: number };
  metrics: Metrics;
  tasks: TaskView[];
  conflicts: ConflictView[];
  drawable: boolean;
  batches: BatchView[];
  steps: StepView[];
  clique: string[];
  resources: { name: string; tasks: string[] }[];
  matrix: { labels: string[]; rows: number[][]; degrees: number[] } | null;
  timings_ms: Record<string, number>;
}

export type AnalyzeRequest =
  | { mode: "text"; text: string; algorithm: Algorithm }
  | { mode: "random"; n: number; p: number; seed: number; algorithm: Algorithm };

export type AnalyzeResult = { ok: true; view: PlanView } | { ok: false; error: string };
