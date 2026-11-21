import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { engine } from "./engine/engine";
import "./styles.css";

engine.start().catch(() => undefined);   // empieza a descargar Python mientras se dibuja la página

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
