/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// base relativa: el sitio se publica en https://<usuario>.github.io/graph-resource-planner/
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  worker: { format: "es" },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
